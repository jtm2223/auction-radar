import logging
import re
from typing import List, Dict, Any
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
from .base import BaseScraper
from ..utils import normalize_timezone

logger = logging.getLogger(__name__)

class GovDealsScraper(BaseScraper):
    """Scraper for GovDeals.com focusing on target vehicles in Northeast states."""
    
    def __init__(self):
        super().__init__('govdeals', 'https://www.govdeals.com')
    
    def crawl(self) -> List[Dict[str, Any]]:
        """Crawl GovDeals.com for target vehicles in Northeast states."""
        lots = []
        
        try:
            # Search for target vehicle categories in Northeast states
            northeast_states = ['NY', 'CT', 'MA', 'NH', 'VT', 'ME', 'RI', 'NJ', 'PA']
            
            # Focus on specific target vehicle searches
            search_terms = [
                'toyota land cruiser',
                'lexus lx',
                'toyota 4runner', 
                'toyota tacoma 4x4',
                'toyota tundra 4x4',
                'nissan frontier 4x4',
                'nissan titan 4x4',
                'camper',
                'rv motorhome',
                'travel trailer'
            ]
            
            for state in northeast_states[:4]:  # Limit to prevent too many requests
                for term in search_terms[:6]:  # Focus on highest priority terms
                    search_lots = self._search_govdeals(term, state)
                    lots.extend(search_lots)
                    
                    # Add delay to be respectful
                    import time
                    time.sleep(1)
            
            logger.info(f"Found {len(lots)} lots from GovDeals")
            
        except Exception as e:
            logger.error(f"Error fetching GovDeals data: {e}")
        
        return lots[:100]  # Limit results
    
    def _search_govdeals(self, search_term: str, state: str) -> List[Dict[str, Any]]:
        """Search GovDeals for specific term in specific state."""
        lots = []
        
        try:
            # GovDeals search URL format - search in vehicles category
            search_url = f"https://www.govdeals.com/index.cfm?fa=Main.AdvSearchResultsNew&searchPg=Category&additionalParams=true&sortOption=ad&timing=bySimple&timingType=&locationType=state&locationParamState={state}&categoryTypeValue=4&additionalParamsTypeValue=additional&searchValue={search_term.replace(' ', '+')}"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = self.safe_get(search_url, headers=headers)
            if not response:
                logger.debug(f"Could not fetch GovDeals search for '{search_term}' in {state}")
                return lots
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for auction items in search results
            item_containers = soup.find_all(['div', 'tr', 'td'], class_=re.compile(r'auction|item|listing|result', re.I))
            if not item_containers:
                # Try different selectors
                item_containers = soup.find_all(['div', 'article'], attrs={'data-auctionid': True})
            if not item_containers:
                # Try table rows with auction links
                item_containers = soup.find_all('tr')
            
            for container in item_containers[:5]:  # Limit per search
                # Look for auction links
                auction_links = container.find_all('a', href=re.compile(r'auctionID=\d+', re.I))
                if auction_links:
                    for link in auction_links[:1]:  # One per container
                        lot_data = self._parse_govdeals_item(container, link, search_term, state)
                        if lot_data:
                            lots.append(lot_data)
            
            logger.debug(f"Found {len(lots)} items for '{search_term}' in {state}")
            
        except Exception as e:
            logger.debug(f"Error searching GovDeals for '{search_term}' in {state}: {e}")
        
        return lots
    
    def _parse_govdeals_item(self, item, link, search_term: str, state: str) -> Dict[str, Any]:
        """Parse a GovDeals auction item."""
        try:
            text_content = item.get_text(strip=True)
            
            # Skip if too short or no relevant keywords
            if len(text_content) < 20:
                return None
            
            # Must contain vehicle-related keywords
            vehicle_keywords = ['vehicle', 'car', 'truck', 'van', 'suv', 'rv', 'camper', 'motorhome', 
                              'trailer', 'toyota', 'nissan', 'lexus', 'ford', 'chevy', 'honda', 
                              'cruiser', 'runner', 'tacoma', 'tundra', 'frontier', 'titan']
            
            if not any(keyword in text_content.lower() for keyword in vehicle_keywords):
                return None
            
            # Extract auction ID and URL
            href = link.get('href', '')
            auction_id_match = re.search(r'auctionID=(\d+)', href, re.I)
            auction_id = auction_id_match.group(1) if auction_id_match else hash(text_content[:50]) % 100000
            
            lot_url = href
            if href.startswith('/'):
                lot_url = f"https://www.govdeals.com{href}"
            elif not href.startswith('http'):
                lot_url = f"https://www.govdeals.com/{href}"
            
            # Extract title
            title_elem = link or item.find(['h1', 'h2', 'h3', 'h4', 'strong', 'b'])
            title = title_elem.get_text().strip() if title_elem else text_content[:100]
            
            # Try to extract vehicle details
            year, make, model, vin = None, None, None, None
            
            # Look for year make model patterns
            vehicle_patterns = [
                r'(\d{4})\s+(toyota|nissan|ford|chevrolet|chevy|honda|lexus)\s+([^,\n\-()]+)',
                r'(toyota|nissan|ford|chevrolet|chevy|honda|lexus)\s+([^,\n\-()]+)\s+(\d{4})',
                r'(land\s*cruiser|4\s*runner|tacoma|tundra|frontier|titan|lx\s*\d+)',
            ]
            
            for pattern in vehicle_patterns:
                match = re.search(pattern, text_content, re.IGNORECASE)
                if match:
                    groups = match.groups()
                    if len(groups) >= 3:
                        if groups[0].isdigit():  # Year first
                            year = int(groups[0])
                            make = groups[1].strip()
                            model = groups[2].strip()
                        elif groups[2].isdigit():  # Year last
                            make = groups[0].strip()
                            model = groups[1].strip()
                            year = int(groups[2])
                    else:
                        # Model only pattern (like land cruiser)
                        model_parts = groups[0].split()
                        if len(model_parts) >= 2:
                            make = "Toyota" if "cruiser" in groups[0].lower() or "runner" in groups[0].lower() else "Unknown"
                            model = groups[0].strip()
                    break
            
            # Look for VIN
            vin_match = re.search(r'\b[A-HJ-NPR-Z0-9]{17}\b', text_content, re.IGNORECASE)
            vin = vin_match.group().upper() if vin_match else None
            
            # Extract auction end dates
            sale_date_utc, tz_name = None, "America/New_York"
            sale_local_time = "TBD"
            
            date_patterns = [
                r'end[s]?\s*:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
                r'closing\s*:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
                r'(\d{1,2}[/-]\d{1,2}[/-]\d{4})\s*[\s@]\s*(\d{1,2}:\d{2})',
                r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+(\d{1,2}),?\s*(\d{4})',
                r'(\d+)\s*day[s]?\s*(\d+)\s*hour[s]?',  # "5 days 3 hours" remaining
                r'(\d+)\s*hour[s]?\s*(\d+)\s*min'  # "3 hours 45 min" remaining
            ]
            
            for pattern in date_patterns:
                date_match = re.search(pattern, text_content, re.I)
                if date_match:
                    try:
                        if 'day' in pattern or 'hour' in pattern:
                            # Handle relative time (days/hours remaining)
                            if 'day' in pattern:
                                days = int(date_match.group(1))
                                hours = int(date_match.group(2)) if len(date_match.groups()) > 1 else 0
                                end_date = datetime.now() + timedelta(days=days, hours=hours)
                            else:
                                hours = int(date_match.group(1))
                                minutes = int(date_match.group(2)) if len(date_match.groups()) > 1 else 0
                                end_date = datetime.now() + timedelta(hours=hours, minutes=minutes)
                            
                            sale_local_time = end_date.strftime("%m/%d/%Y %I:%M %p")
                            sale_date_utc, tz_name = normalize_timezone(sale_local_time, "America/New_York")
                        else:
                            # Handle absolute dates
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
            
            # Create lot ID
            lot_id = f"govdeals_{auction_id}"
            
            # Determine location
            location_city = "Unknown"
            location_name = f"GovDeals - {state}"
            
            # Look for city/agency in text
            agency_patterns = [
                r'(city|town|county|dept|department|police|fire|sheriff)\s+of\s+([^,\n]+)',
                r'([^,\n]+)\s+(police|fire|sheriff|dept|department)',
                r'([A-Z][a-z]+),?\s*' + state  # City, STATE pattern
            ]
            
            for pattern in agency_patterns:
                agency_match = re.search(pattern, text_content, re.I)
                if agency_match:
                    if 'of' in pattern:
                        location_city = agency_match.group(2).strip()
                        location_name = f"{agency_match.group(1).title()} of {location_city}"
                    else:
                        location_city = agency_match.group(1).strip()
                        if len(agency_match.groups()) > 1:
                            location_name = f"{location_city} {agency_match.group(2).title()}"
                    break
            
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
                'condition_notes': f'GovDeals {search_term} - {title}',
                'raw_text': text_content[:500]
            }
            
            # Enhance with VIN decoding if available
            if vin:
                lot_data = self.enhance_vehicle_data(lot_data)
            
            return lot_data
            
        except Exception as e:
            logger.debug(f"Error parsing GovDeals item: {e}")
            return None