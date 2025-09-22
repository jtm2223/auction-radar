import logging
import re
from typing import List, Dict, Any
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from .base import BaseScraper
from ..utils import normalize_timezone

logger = logging.getLogger(__name__)

class CTStateSurplusScraper(BaseScraper):
    """Scraper for Connecticut State Surplus auctions via Public Surplus."""
    
    def __init__(self):
        super().__init__('ct_state_surplus', 'https://www.publicsurplus.com')
    
    def crawl(self) -> List[Dict[str, Any]]:
        """Crawl Connecticut State Surplus auctions from Public Surplus."""
        lots = []
        
        try:
            # Fetch Connecticut vehicle auctions directly from the vehicle category
            url = "https://www.publicsurplus.com/sms/all,ct/browse/search?posting=y&slth=&page=0&sortBy=&sortDesc=N&keyWord=&catId=4&endHours=-1&startHours=-1&lowerPrice=0&higherPrice=0&milesLocation=-1&zipCode=&region=all%2Cct&search="
            response = self.safe_get(url)
            if not response:
                logger.warning("Could not fetch CT vehicle auctions page")
                return lots
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for auction listings with better structure
            # Public Surplus uses table rows for listings
            auction_rows = soup.find_all('tr', class_=re.compile(r'item|listing|row'))
            if not auction_rows:
                # Fallback to any table rows with links
                auction_rows = soup.find_all('tr')
                auction_rows = [row for row in auction_rows if row.find('a', href=re.compile(r'/auction/view'))]
            
            # Also look for div containers with auction data
            auction_divs = soup.find_all('div', class_=re.compile(r'item|listing|auction'))
            
            all_items = auction_rows + auction_divs
            
            for item in all_items:
                try:
                    # Find auction link in this item
                    auction_link = item.find('a', href=re.compile(r'/auction/view\?auc=\d+'))
                    if auction_link:
                        lot_data = self._parse_public_surplus_item(item, auction_link.get('href'))
                        if lot_data and lot_data.get('year'):  # Only add if we parsed vehicle details
                            lots.append(lot_data)
                except Exception as e:
                    logger.debug(f"Error parsing auction item: {e}")
                    continue
            
            logger.info(f"Found {len(lots)} Connecticut state surplus lots")
            
        except Exception as e:
            logger.error(f"Error fetching CT Public Surplus data: {e}")
        
        return lots
    
    def _parse_public_surplus_item(self, item, href=None) -> Dict[str, Any]:
        """Parse a Public Surplus auction item."""
        try:
            text_content = item.get_text()
            
            # Look for vehicle description - Public Surplus uses specific patterns
            # Try to find auction ID and vehicle description
            auction_id_match = re.search(r'#(\d+)\s*-\s*([^$\n]+)', text_content)
            
            description = ""
            auction_id = ""
            
            if auction_id_match:
                auction_id = auction_id_match.group(1)
                description = auction_id_match.group(2).strip()
            else:
                # Fallback - look for any vehicle-like description
                lines = text_content.strip().split('\n')
                for line in lines:
                    if any(keyword in line.upper() for keyword in ['CHEVY', 'FORD', 'TOYOTA', 'GMC', 'HONDA', 'NISSAN', 'PICKUP', 'CAMRY', 'CORVETTE']):
                        description = line.strip()
                        break
                
                if not description:
                    description = text_content[:100].strip()
            
            # Enhanced vehicle parsing for Public Surplus format
            year, make, model = None, None, None
            
            # Try multiple patterns for year/make/model - enhanced patterns
            patterns = [
                r'(\d{4})\s+([A-Z][A-Z]+)\s+([A-Z][A-Z0-9\s]+)',  # 2005 CHEVY PICKUP
                r'([A-Z][A-Z]+)\s+([A-Z][A-Z0-9\s]+)\s+(\d{4})',  # CHEVY PICKUP 2005
                r'(\d{4})\s+([A-Z][a-z]+)\s+([A-Za-z0-9\s]+)',    # 2007 Chevy Pickup
                r'(\d{4})\s+(TOYOTA|HONDA|NISSAN|FORD|CHEVY|GMC|CHEVROLET)\s+(\w+)',  # 2010 TOYOTA CAMRY
                r'#\d+\s*-\s*(\d{4})?\s*([A-Z]+)\s+([A-Z0-9\s]+)',  # #3829168 - 2005 CHEVY PICKUP
                r'(\d{4})\s+([A-Za-z]+)\s+([A-Za-z0-9\-\s]+)',     # Flexible case matching
            ]
            
            for pattern in patterns:
                match = re.search(pattern, description.upper())
                if match:
                    groups = match.groups()
                    if groups[0].isdigit():
                        year = int(groups[0])
                        make = groups[1].strip()
                        model = groups[2].strip()
                    elif groups[2].isdigit():
                        make = groups[0].strip()
                        model = groups[1].strip()
                        year = int(groups[2])
                    else:
                        year = int(groups[0]) if groups[0].isdigit() else None
                        make = groups[1].strip()
                        model = groups[2].strip()
                    break
            
            # Try to find VIN in text
            vin_match = re.search(r'\b[A-HJ-NPR-Z0-9]{17}\b', text_content, re.IGNORECASE)
            vin = vin_match.group().upper() if vin_match else None
            
            # Extract location - CT is default since we're on CT page
            city = "Hartford"
            location_match = re.search(r'([A-Za-z\s]+),?\s*CT\b', text_content)
            if location_match:
                city = location_match.group(1).strip()
            
            # Build lot URL from href or auction ID
            lot_url = self.base_url
            if href:
                if href.startswith('/'):
                    lot_url = f"https://www.publicsurplus.com{href}"
                elif href.startswith('http'):
                    lot_url = href
            elif auction_id:
                lot_url = f"https://www.publicsurplus.com/sms/all,ct/auction/view?auc={auction_id}"
            
            # Generate lot ID
            lot_id = f"ct_surplus_{auction_id}" if auction_id else f"ct_surplus_{hash(description[:50]) % 100000}"
            
            # Try to find current bid and time left
            bid_match = re.search(r'\$([0-9,]+\.?\d*)', text_content)
            current_bid = None
            if bid_match:
                try:
                    current_bid = float(bid_match.group(1).replace(',', ''))
                except:
                    pass
            
            # Look for time remaining
            time_match = re.search(r'(\d+)\s*days?\s*(\d+)?\s*hours?', text_content, re.I)
            sale_local_time = "TBD"
            if time_match:
                days = int(time_match.group(1))
                hours = int(time_match.group(2)) if time_match.group(2) else 0
                # Estimate end date
                from datetime import datetime, timedelta
                end_date = datetime.now() + timedelta(days=days, hours=hours)
                sale_local_time = end_date.strftime("%m/%d/%Y %I:%M %p")
            
            sale_date_utc, tz_name = None, "America/New_York"
            if sale_local_time != "TBD":
                try:
                    sale_date_utc, tz_name = normalize_timezone(sale_local_time, "America/New_York")
                except:
                    pass
            
            lot_data = {
                'source': self.source_name,
                'source_lot_id': lot_id,
                'lot_url': lot_url,
                'sale_date_utc': sale_date_utc.isoformat() if sale_date_utc else None,
                'sale_local_time': sale_local_time,
                'tz_name': tz_name,
                'location_name': 'Connecticut State Surplus',
                'location_city': city,
                'location_state': 'CT',
                'year': year,
                'make': make,
                'model': model,
                'vin': vin,
                'title_status': 'unknown',
                'condition_notes': f'Connecticut state surplus - {description}',
                'current_bid': current_bid,
                'raw_text': text_content[:500]  # First 500 chars
            }
            
            # Enhance with VIN decoding if VIN is available
            if vin:
                lot_data = self.enhance_vehicle_data(lot_data)
            
            return lot_data
            
        except Exception as e:
            logger.debug(f"Error parsing Public Surplus item: {e}")
            return None
