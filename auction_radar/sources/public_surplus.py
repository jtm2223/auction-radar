import logging
import re
from typing import List, Dict, Any
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
from .base import BaseScraper
from ..utils import normalize_timezone

logger = logging.getLogger(__name__)

class PublicSurplusScraper(BaseScraper):
    """Scraper for PublicSurplus.com focusing on RVs, campers, and target vehicles in Northeast."""
    
    def __init__(self):
        super().__init__('public_surplus', 'https://www.publicsurplus.com')
    
    def crawl(self) -> List[Dict[str, Any]]:
        """Crawl PublicSurplus.com for target vehicles in Northeast states."""
        lots = []
        
        try:
            # Search for target vehicle categories in Northeast states
            northeast_states = ['CT', 'MA', 'NH', 'VT', 'ME', 'RI', 'NY', 'NJ']
            
            search_terms = [
                'land cruiser',
                '4runner', 
                'toyota 4x4',
                'nissan 4x4',
                'camper',
                'rv',
                'motorhome',
                'travel trailer'
            ]
            
            for state in northeast_states[:3]:  # Limit to prevent too many requests
                for term in search_terms[:4]:  # Focus on highest priority terms
                    search_lots = self._search_publicsurplus(term, state)
                    lots.extend(search_lots)
            
            logger.info(f"Found {len(lots)} lots from PublicSurplus")
            
        except Exception as e:
            logger.error(f"Error fetching PublicSurplus data: {e}")
        
        return lots[:50]  # Limit results
    
    def _search_publicsurplus(self, search_term: str, state: str) -> List[Dict[str, Any]]:
        """Search PublicSurplus for specific term in specific state."""
        lots = []
        
        try:
            # PublicSurplus state-specific URL format (corrected)
            state_url = f"https://www.publicsurplus.com/sms/all,{state.lower()}/browse/home"
            
            response = self.safe_get(state_url)
            if not response:
                logger.debug(f"Could not fetch PublicSurplus state page for {state}")
                return lots
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for auction items that contain our search term
            page_text = soup.get_text().lower()
            if search_term.lower() not in page_text:
                logger.debug(f"No matches for '{search_term}' found on {state} page")
                return lots
            
            # Look for auction items
            item_containers = soup.find_all(['div', 'tr', 'td', 'article'], class_=re.compile(r'auction|item|listing|row', re.I))
            if not item_containers:
                # Try different selectors
                item_containers = soup.find_all(['a'], href=re.compile(r'auction', re.I))
            
            for container in item_containers[:10]:  # Limit per search
                container_text = container.get_text().lower()
                if search_term.lower() in container_text:
                    lot_data = self._parse_publicsurplus_item(container, search_term, state)
                    if lot_data:
                        lots.append(lot_data)
            
            logger.debug(f"Found {len(lots)} items for '{search_term}' in {state}")
            
        except Exception as e:
            logger.debug(f"Error searching PublicSurplus for '{search_term}' in {state}: {e}")
        
        return lots
    
    def _parse_publicsurplus_item(self, item, search_term: str, state: str) -> Dict[str, Any]:
        """Parse a PublicSurplus auction item."""
        try:
            text_content = item.get_text(strip=True)
            
            # Skip if too short or no relevant keywords
            if len(text_content) < 20:
                return None
            
            # Must contain vehicle-related keywords
            vehicle_keywords = ['vehicle', 'car', 'truck', 'van', 'suv', 'rv', 'camper', 'motorhome', 
                              'trailer', 'toyota', 'nissan', 'ford', 'chevy', 'honda', 'cruiser', 'runner']
            
            if not any(keyword in text_content.lower() for keyword in vehicle_keywords):
                return None
            
            # Extract title
            title_elem = item.find(['h1', 'h2', 'h3', 'h4', 'strong', 'b', 'a'])
            title = title_elem.get_text().strip() if title_elem else text_content[:100]
            
            # Try to extract vehicle details
            year, make, model, vin = None, None, None, None
            
            # Look for year make model patterns
            vehicle_patterns = [
                r'(\d{4})\s+(toyota|nissan|ford|chevrolet|chevy|honda|lexus)\s+([^,\n\-()]+)',
                r'(toyota|nissan|ford|chevrolet|chevy|honda|lexus)\s+([^,\n\-()]+)\s+(\d{4})',
                r'(land\s*cruiser|4\s*runner|tacoma|tundra|frontier|titan)',
            ]
            
            for pattern in vehicle_patterns:
                match = re.search(pattern, text_content, re.IGNORECASE)
                if match:
                    groups = match.groups()
                    if groups[0].isdigit():  # Year first
                        year = int(groups[0])
                        make = groups[1].strip() if len(groups) > 1 else None
                        model = groups[2].strip() if len(groups) > 2 else None
                    elif len(groups) >= 3 and groups[2].isdigit():  # Year last
                        make = groups[0].strip()
                        model = groups[1].strip()
                        year = int(groups[2])
                    else:
                        make = groups[0].strip()
                        model = search_term  # Use search term as model
                    break
            
            # Look for VIN
            vin_match = re.search(r'\b[A-HJ-NPR-Z0-9]{17}\b', text_content, re.IGNORECASE)
            vin = vin_match.group().upper() if vin_match else None
            
            # Extract auction dates
            sale_date_utc, tz_name = None, "America/New_York"
            sale_local_time = "TBD"
            
            date_patterns = [
                r'end[s]?\s*:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
                r'closing\s*:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
                r'(\d{1,2}[/-]\d{1,2}[/-]\d{4})\s*[\s@]\s*(\d{1,2}:\d{2})',
                r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+(\d{1,2}),?\s*(\d{4})'
            ]
            
            for pattern in date_patterns:
                date_match = re.search(pattern, text_content, re.I)
                if date_match:
                    try:
                        if len(date_match.groups()) >= 2:
                            date_str = f"{date_match.group(1)} {date_match.group(2)}"
                        else:
                            date_str = date_match.group(0)
                        
                        sale_date_utc, tz_name = normalize_timezone(date_str, "America/New_York")
                        sale_local_time = date_str
                        break
                    except Exception as e:
                        logger.debug(f"Could not parse date '{date_match.group()}': {e}")
                        continue
            
            # Extract URL
            lot_url = self.base_url
            link_elem = item.find('a', href=True)
            if link_elem:
                href = link_elem.get('href')
                if href.startswith('/'):
                    lot_url = f"https://www.publicsurplus.com{href}"
                elif href.startswith('http'):
                    lot_url = href
            
            # Create lot ID
            lot_id = f"publicsurplus_{hash(title + state) % 100000}"
            
            # Determine location
            location_city = "Unknown"
            location_name = f"Public Surplus - {state}"
            
            # Look for city/agency in text
            city_match = re.search(r'(city|town|county|dept|department)\s+of\s+([^,\n]+)', text_content, re.I)
            if city_match:
                location_city = city_match.group(2).strip()
                location_name = f"{city_match.group(1).title()} of {location_city}"
            
            lot_data = {
                'source': self.source_name,
                'source_lot_id': lot_id,
                'lot_url': lot_url,
                'sale_date_utc': sale_date_utc.isoformat() if sale_date_utc else None,
                'sale_local_time': sale_local_time,
                'tz_name': tz_name,
                'location_name': location_name,
                'location_city': location_city,
                'location_state': state,
                'year': year,
                'make': make,
                'model': model,
                'vin': vin,
                'title_status': 'unknown',
                'condition_notes': f'Public Surplus {search_term} - {title}',
                'raw_text': text_content[:500]
            }
            
            # Enhance with VIN decoding if available
            if vin:
                lot_data = self.enhance_vehicle_data(lot_data)
            
            return lot_data
            
        except Exception as e:
            logger.debug(f"Error parsing PublicSurplus item: {e}")
            return None