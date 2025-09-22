import logging
import re
from typing import List, Dict, Any
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
from .base import BaseScraper
from ..utils import normalize_timezone

logger = logging.getLogger(__name__)

class NYStateSurplusScraper(BaseScraper):
    """Scraper for New York State surplus auctions via Municibid (counties) and OGS."""
    
    def __init__(self):
        super().__init__('ny_state_surplus', 'https://municibid.com')
    
    def crawl(self) -> List[Dict[str, Any]]:
        """Crawl New York State and county surplus auction listings from Municibid."""
        lots = []
        
        try:
            # Get NY state/county auctions from Municibid
            ny_url = 'https://municibid.com/Browse/R3777829/New_York'
            response = self.safe_get(ny_url)
            if not response:
                logger.warning("Could not fetch Municibid NY page")
                return lots
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract auction items from the page
            auction_items = self._extract_municibid_items(soup)
            
            # Create lots for each auction item
            for item in auction_items:
                lot_data = self._parse_municibid_item(item, ny_url)
                if lot_data:
                    # Skip NYC items (we have a separate scraper for those)
                    if not any(nyc_keyword in lot_data['raw_text'].lower() 
                             for nyc_keyword in ['new york city', 'nyc', 'brooklyn', 'bronx', 'queens', 'manhattan', 'staten island']):
                        lots.append(lot_data)
            
            logger.info(f"Found {len(lots)} New York State/county surplus lots")
            
        except Exception as e:
            logger.error(f"Error fetching NY State Municibid data: {e}")
        
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
        """Parse a Municibid auction item for NY State."""
        try:
            # Extract text content with better formatting
            text_content = item.get_text(separator=' ', strip=True)
            
            # Skip if too short or doesn't contain useful info
            if len(text_content) < 10:
                return None
                
            # Look for vehicle-related keywords (expanded list)
            vehicle_keywords = ['vehicle', 'car', 'truck', 'van', 'suv', 'sedan', 'police', 'fire', 'ambulance',
                               'ford', 'chevrolet', 'chevy', 'toyota', 'honda', 'nissan', 'gmc', 'dodge',
                               'f350', 'f250', 'f150', 'silverado', 'camry', 'plow', 'aerial', 'lift']
            if not any(keyword in text_content.lower() for keyword in vehicle_keywords):
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
            
            # Look for auction times - Municibid uses relative time
            sale_local_time = "TBD"
            sale_date_utc, tz_name = None, "America/New_York"
            
            # Look for time remaining indicators
            time_patterns = [
                r'(\d+)\s*days?\s*(\d+)?\s*hours?',  # "2 days 5 hours"
                r'(\d+)\s*hours?\s*(\d+)?\s*minutes?',  # "5 hours 30 minutes"
                r'ends\s*in\s*:?\s*([^<\n]+)',  # "Ends in: 2 days"
                r'closing\s*in\s*:?\s*([^<\n]+)',  # "Closing in: 5 hours"
                r'time\s*left\s*:?\s*([^<\n]+)',  # "Time left: 1 day"
            ]
            
            for pattern in time_patterns:
                time_match = re.search(pattern, text_content, re.I)
                if time_match:
                    try:
                        if 'days' in time_match.group(0).lower():
                            days_match = re.search(r'(\d+)\s*days?', time_match.group(0))
                            hours_match = re.search(r'(\d+)\s*hours?', time_match.group(0))
                            
                            days = int(days_match.group(1)) if days_match else 0
                            hours = int(hours_match.group(1)) if hours_match else 0
                            
                            end_date = datetime.now() + timedelta(days=days, hours=hours)
                            sale_local_time = end_date.strftime("%B %d, %Y %I:%M %p")
                            sale_date_utc, tz_name = normalize_timezone(sale_local_time, "America/New_York")
                            break
                        elif 'hours' in time_match.group(0).lower():
                            hours_match = re.search(r'(\d+)\s*hours?', time_match.group(0))
                            minutes_match = re.search(r'(\d+)\s*minutes?', time_match.group(0))
                            
                            hours = int(hours_match.group(1)) if hours_match else 0
                            minutes = int(minutes_match.group(1)) if minutes_match else 0
                            
                            end_date = datetime.now() + timedelta(hours=hours, minutes=minutes)
                            sale_local_time = end_date.strftime("%B %d, %Y %I:%M %p")
                            sale_date_utc, tz_name = normalize_timezone(sale_local_time, "America/New_York")
                            break
                    except Exception as e:
                        logger.debug(f"Could not parse time remaining '{time_match.group()}': {e}")
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
            lot_id = f"ny_state_{hash(title) % 100000}"
            
            # Extract location/agency - improved parsing for NY locations
            city = "Albany"  # Default for NY State
            location_name = "New York State/County Surplus"
            
            # Clean up text to better parse location
            clean_text = re.sub(r'\s+', ' ', text_content.replace('\n', ' '))
            
            # Look for NY cities and counties
            ny_locations = {
                'Albany': 'Albany',
                'Buffalo': 'Buffalo', 
                'Rochester': 'Rochester',
                'Yonkers': 'Yonkers',
                'Syracuse': 'Syracuse',
                'New Rochelle': 'New Rochelle',
                'Mount Vernon': 'Mount Vernon',
                'Schenectady': 'Schenectady',
                'Utica': 'Utica',
                'White Plains': 'White Plains',
                'Sea Cliff': 'Sea Cliff',
                'Nassau': 'Nassau County',
                'Suffolk': 'Suffolk County',
                'Westchester': 'Westchester County',
                'Erie': 'Erie County',
                'Monroe': 'Monroe County',
                'Onondaga': 'Onondaga County'
            }
            
            # Try to match NY locations
            for location_key, location_full in ny_locations.items():
                if location_key.upper() in clean_text.upper():
                    if 'County' in location_full:
                        city = location_key
                        location_name = f"{location_full} Surplus"
                    else:
                        city = location_key
                        location_name = f"City of {location_key}"
                    break
                    
            # Try to extract specific department/agency info
            agency_patterns = [
                r'([A-Za-z\s]+)\s+(Police|Sheriff|Fire|DPW|Department)',
                r'(County|City|Town|Village)\s+of\s+([A-Za-z\s]+)',
                r'([A-Za-z\s]+)\s+(County|City)'
            ]
            
            for pattern in agency_patterns:
                agency_match = re.search(pattern, clean_text, re.I)
                if agency_match:
                    groups = agency_match.groups()
                    if 'County' in groups[1] or 'City' in groups[1]:
                        city = groups[1] if len(groups) > 1 else groups[0]
                        location_name = f"{groups[0]} {groups[1]}"
                    else:
                        location_name = f"{groups[0]} {groups[1]}"
                        # Keep existing city unless we find a better one
                    break
            
            lot_data = {
                'source': self.source_name,
                'source_lot_id': lot_id,
                'lot_url': lot_url,
                'sale_date_utc': sale_date_utc.isoformat() if sale_date_utc else None,
                'sale_local_time': sale_local_time,
                'tz_name': tz_name,
                'location_name': location_name,
                'location_city': city,
                'location_state': 'NY',
                'year': year,
                'make': make,
                'model': model,
                'vin': vin,
                'title_status': 'unknown',
                'condition_notes': f'New York State/county surplus - {title}',
                'raw_text': text_content[:500]
            }
            
            # Enhance with VIN decoding if VIN is available

            
            if vin:

            
                lot_data = self.enhance_vehicle_data(lot_data)

            
            

            
            return lot_data
            
        except Exception as e:
            logger.debug(f"Error parsing Municibid item: {e}")
            return None