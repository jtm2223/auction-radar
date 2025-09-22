import logging
import re
from typing import List, Dict, Any
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
from .base import BaseScraper
from ..utils import normalize_timezone

logger = logging.getLogger(__name__)

class NJStateSurplusScraper(BaseScraper):
    """Scraper for New Jersey State Surplus auctions via NJ Treasury DSS."""
    
    def __init__(self):
        super().__init__('nj_state_surplus', 'https://municibid.com')
    
    def crawl(self) -> List[Dict[str, Any]]:
        """Crawl New Jersey government surplus auction listings from Municibid."""
        lots = []
        
        try:
            # Get NJ government auctions from Municibid
            nj_url = 'https://municibid.com/Browse/R3777827/New_Jersey'
            response = self.safe_get(nj_url)
            if not response:
                logger.warning("Could not fetch Municibid NJ page")
                return lots
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract auction items from the page
            auction_items = self._extract_municibid_items(soup)
            
            # Create lots for each auction item
            for item in auction_items:
                lot_data = self._parse_municibid_item(item, nj_url)
                if lot_data:
                    lots.append(lot_data)
            
            logger.info(f"Found {len(lots)} New Jersey government surplus lots")
            
        except Exception as e:
            logger.error(f"Error fetching NJ Municibid data: {e}")
        
        return lots
    
    def _extract_municibid_items(self, soup: BeautifulSoup):
        """Extract auction items from Municibid page."""
        items = []
        
        # Look for common auction item containers
        item_selectors = [
            'div[class*="auction"]',
            'div[class*="item"]',
            'div[class*="listing"]',
            'div[class*="lot"]',
            'article',
            '.card',
            '.product'
        ]
        
        for selector in item_selectors:
            found_items = soup.select(selector)
            items.extend(found_items)
        
        # Also look for links that might be auction items
        auction_links = soup.find_all('a', href=True)
        for link in auction_links:
            if any(keyword in link.get('href', '').lower() for keyword in ['auction', 'item', 'lot', 'bid']):
                items.append(link)
        
        logger.debug(f"Found {len(items)} potential auction items")
        return items[:20]  # Limit to prevent too many items
    
    def _parse_municibid_item(self, item, base_url: str) -> Dict[str, Any]:
        """Parse a Municibid auction item for NJ."""
        try:
            # Extract text content
            text_content = item.get_text(strip=True)
            
            # Skip if too short
            if len(text_content) < 10:
                return None
                
            # Look for vehicle-related keywords
            if not any(keyword in text_content.lower() for keyword in 
                      ['vehicle', 'car', 'truck', 'van', 'suv', 'sedan', 'police', 'ford', 'chevrolet', 'toyota', 'honda']):
                return None
            
            # Extract title/description
            title_elem = item.find(['h1', 'h2', 'h3', 'h4', 'strong', 'b'])
            title = title_elem.get_text().strip() if title_elem else text_content[:100]
            
            # Try to extract vehicle details
            year, make, model, vin = None, None, None, None
            vehicle_match = re.search(r'(\d{4})\s+(\w+)\s+([^-\n,()]+)', title)
            if vehicle_match:
                year = int(vehicle_match.group(1))
                make = vehicle_match.group(2).strip()
                model = vehicle_match.group(3).strip()
            
            # Try to find VIN in text
            vin_match = re.search(r'[A-HJ-NPR-Z0-9]{17}', text_content, re.IGNORECASE)
            vin = vin_match.group().upper() if vin_match else None
            
            # Look for auction end dates
            date_patterns = [
                r'end[s]?\s*:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
                r'closing\s*:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
                r'(\d{1,2}[/-]\d{1,2}[/-]\d{4})\s*at\s*(\d{1,2}:\d{2})',
                r'(\w+\s+\d{1,2}),?\s*(\d{4})'
            ]
            
            sale_date_utc, tz_name = None, "America/New_York"
            sale_local_time = "TBD"
            
            for pattern in date_patterns:
                date_match = re.search(pattern, text_content, re.I)
                if date_match:
                    try:
                        if len(date_match.groups()) >= 2:
                            date_str = f"{date_match.group(1)} {date_match.group(2)}"
                        else:
                            date_str = date_match.group(1)
                        
                        # Default time if not specified
                        if 'at' not in date_str.lower():
                            date_str += " 10:00 AM"
                            
                        sale_date_utc, tz_name = normalize_timezone(date_str, "America/New_York")
                        sale_local_time = date_str
                        break
                    except Exception as e:
                        logger.debug(f"Could not parse date '{date_match.group()}': {e}")
                        continue
            
            # Extract URL if available
            lot_url = base_url
            if item.name == 'a' and item.get('href'):
                href = item.get('href')
                if href.startswith('/'):
                    lot_url = f"https://municibid.com{href}"
                elif href.startswith('http'):
                    lot_url = href
            
            # Create lot ID
            lot_id = f"nj_municibid_{hash(title) % 100000}"
            
            # Extract location/agency
            agency_match = re.search(r'(city|town|county|township|dept|department|police|fire)\s+of\s+([^,\n]+)', text_content, re.I)
            city = "Trenton"  # Default
            location_name = "New Jersey Government Surplus"
            
            if agency_match:
                city = agency_match.group(2).strip()
                location_name = f"{agency_match.group(1).title()} of {city}"
            
            lot_data = {
                'source': self.source_name,
                'source_lot_id': lot_id,
                'lot_url': lot_url,
                'sale_date_utc': sale_date_utc.isoformat() if sale_date_utc else None,
                'sale_local_time': sale_local_time,
                'tz_name': tz_name,
                'location_name': location_name,
                'location_city': city,
                'location_state': 'NJ',
                'year': year,
                'make': make,
                'model': model,
                'vin': vin,
                'title_status': 'unknown',
                'condition_notes': f'New Jersey government surplus - {title}',
                'raw_text': text_content[:500]
            }
            
            # Enhance with VIN decoding if VIN is available

            
            if vin:

            
                lot_data = self.enhance_vehicle_data(lot_data)

            
            

            
            return lot_data
            
        except Exception as e:
            logger.debug(f"Error parsing Municibid item: {e}")
            return None
