import logging
import re
from typing import List, Dict, Any
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
from .base import BaseScraper
from ..utils import normalize_timezone

logger = logging.getLogger(__name__)

class VTStateSurplusScraper(BaseScraper):
    """Scraper for Vermont state surplus auctions via VTAuction.com (Auctions International)."""
    
    def __init__(self):
        super().__init__('vt_state_surplus', 'https://www.vtauction.com')
    
    def crawl(self) -> List[Dict[str, Any]]:
        """Crawl Vermont state surplus auctions from VTAuction.com."""
        lots = []
        
        try:
            # Fetch Vermont state auctions
            url = "https://www.vtauction.com"
            response = self.safe_get(url)
            
            if not response:
                logger.warning("Could not fetch VT Auction page")
                return []
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find auction item containers - VTAuction.com structure
            auction_links = soup.find_all('a', href=re.compile(r'/auction.*\d+', re.I))
            if not auction_links:
                # Try different pattern
                auction_links = soup.find_all('a', href=re.compile(r'auction|lot', re.I))
            
            logger.debug(f"Found {len(auction_links)} auction links on VT page")
            
            # Process auction links
            all_items = []
            processed_ids = set()
            
            for link in auction_links:
                href = link.get('href', '')
                # Extract auction/lot ID
                auction_id_match = re.search(r'(\d+)', href)
                if auction_id_match:
                    aid = auction_id_match.group(1)
                    if aid not in processed_ids:
                        processed_ids.add(aid)
                        # Find parent container with more info
                        container = link.find_parent(['div', 'article', 'td', 'li', 'tr'])
                        all_items.append((container or link, href))
            
            logger.debug(f"Found {len(all_items)} potential VT auction items")
            
            for item, href in all_items:
                try:
                    lot_data = self._parse_vt_auction_item(item, href)
                    if lot_data:
                        # Filter for vehicles only - expanded keywords to catch more
                        text = lot_data.get('raw_text', '').upper()
                        vehicle_keywords = ['FORD', 'CHEVY', 'GMC', 'TOYOTA', 'HONDA', 'NISSAN', 'LEXUS', 
                                          'TRUCK', 'CAR', 'VAN', 'SUV', 'PICKUP', 'VEHICLE', 'AUTO', 
                                          'SEDAN', 'COUPE', 'WAGON', 'JEEP', 'DODGE', 'CHRYSLER', 
                                          '4RUNNER', 'LAND CRUISER', 'TACOMA', 'TUNDRA', 'FRONTIER', 
                                          'TITAN', 'CAMPER', 'TRAILER', 'RV', 'MOTORHOME', 'SILVERADO']
                        if any(keyword in text for keyword in vehicle_keywords):
                            lots.append(lot_data)
                except Exception as e:
                    logger.debug(f"Error parsing VT auction item: {e}")
                    continue
                    
            logger.info(f"Found {len(lots)} Vermont state surplus lots")
                    
        except Exception as e:
            logger.error(f"Error fetching VT Auction data: {e}")
        
        return lots
    
    def _parse_vt_auction_item(self, item, href=None) -> Dict[str, Any]:
        """Parse a VT Auction item."""
        try:
            text_content = item.get_text().strip()
            
            # Extract auction ID from href
            auction_id = ""
            if href:
                auction_match = re.search(r'(\d+)', href)
                if auction_match:
                    auction_id = auction_match.group(1)
            
            # Parse vehicle details from text and href
            lines = [line.strip() for line in text_content.split('\n') if line.strip()]
            
            # Find the main vehicle description - check both text and href
            vehicle_desc = ""
            
            # First try to get description from href URL
            if href:
                url_parts = href.split('/')
                for part in url_parts:
                    if any(word in part.upper() for word in ['FORD', 'CHEVY', 'GMC', 'TOYOTA', 'HONDA', 'NISSAN', 'TRUCK', 'CAR', 'VAN', 'SILVERADO']):
                        vehicle_desc = part.replace('-', ' ').replace('_', ' ')
                        break
            
            # If not found in URL, check text lines
            if not vehicle_desc:
                for line in lines:
                    if any(word in line.upper() for word in ['FORD', 'CHEVY', 'GMC', 'TOYOTA', 'HONDA', 'NISSAN', 'TRUCK', 'CAR', 'VAN', 'SILVERADO']):
                        vehicle_desc = line
                        break
            
            if not vehicle_desc and lines:
                vehicle_desc = lines[0]  # Use first line as fallback
            
            # Extract year, make, model
            year, make, model = self._extract_vehicle_info(vehicle_desc)
            
            # Extract location - Vermont towns/cities
            city = "Montpelier"  # Default to state capital
            vt_cities = ['Montpelier', 'Burlington', 'South Burlington', 'Rutland', 'Barre', 'Essex', 
                        'Colchester', 'Bennington', 'Brattleboro', 'Milton', 'Hartford', 'Middlebury', 
                        'St. Albans', 'Newport', 'Vergennes', 'Winooski', 'St. Johnsbury', 'Bellows Falls']
            
            for vt_city in vt_cities:
                if vt_city.upper() in text_content.upper():
                    city = vt_city
                    break
            
            # Extract current bid/price
            current_bid = None
            bid_patterns = [
                r'current\s*bid\s*:?\s*\$([0-9,]+\.?\d*)',
                r'high\s*bid\s*:?\s*\$([0-9,]+\.?\d*)',
                r'\$([0-9,]+\.?\d*)',
            ]
            
            for pattern in bid_patterns:
                bid_match = re.search(pattern, text_content, re.I)
                if bid_match:
                    try:
                        current_bid = float(bid_match.group(1).replace(',', ''))
                        break
                    except:
                        pass
            
            # Extract bid count
            bid_count_match = re.search(r'(\d+)\s*bids?', text_content, re.I)
            bid_count = int(bid_count_match.group(1)) if bid_count_match else None
            
            # Extract auction end date
            sale_date_utc, tz_name = None, "America/New_York"
            sale_local_time = "TBD"
            
            # Look for various date patterns
            date_patterns = [
                r'end[s]?\s*:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
                r'closing\s*:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
                r'(\d{1,2}[/-]\d{1,2}[/-]\d{4})\s*[\s@]\s*(\d{1,2}:\d{2})',
                r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+(\d{1,2}),?\s*(\d{4})',
                r'(\d+)\s*day[s]?\s*(\d+)\s*hour[s]?',  # "5 days 3 hours" remaining
            ]
            
            for pattern in date_patterns:
                date_match = re.search(pattern, text_content, re.I)
                if date_match:
                    try:
                        if 'day' in pattern:
                            # Handle relative time (days/hours remaining)
                            days = int(date_match.group(1))
                            hours = int(date_match.group(2)) if len(date_match.groups()) > 1 else 0
                            end_date = datetime.now() + timedelta(days=days, hours=hours)
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
            
            # Build lot URL
            lot_url = href if href and href.startswith('http') else f"https://www.vtauction.com{href}" if href else self.base_url
            
            lot_id = f"vt_auction_{auction_id}" if auction_id else f"vt_auction_{hash(vehicle_desc[:50]) % 100000}"
            
            lot_data = {
                'source': self.source_name,
                'source_lot_id': lot_id,
                'lot_url': lot_url,
                'sale_date_utc': sale_date_utc.isoformat() if sale_date_utc else None,
                'sale_local_time': sale_local_time,
                'tz_name': tz_name,
                'location_name': 'Vermont State Surplus',
                'location_city': city,
                'location_state': 'VT',
                'year': year,
                'make': make,
                'model': model,
                'vin': None,  # VINs not typically shown on listing pages
                'title_status': 'unknown',
                'condition_notes': f'{vehicle_desc} - Current bid: ${current_bid:.2f}' if current_bid else vehicle_desc,
                'current_bid': current_bid,
                'bid_count': bid_count,
                'raw_text': text_content[:500]  # First 500 chars
            }
            
            return lot_data
            
        except Exception as e:
            logger.debug(f"Error parsing VT auction item: {e}")
            return None
    
    def _extract_vehicle_info(self, description: str) -> tuple:
        """Extract year, make, model from vehicle description."""
        year, make, model = None, None, None
        
        # Common patterns for vehicle descriptions
        patterns = [
            r'(\d{4})\s+([A-Za-z]+(?:\s+[A-Za-z]+)?)\s+([A-Za-z0-9\s\-]+)',  # 2016 Chevy Silverado
            r'([A-Za-z]+(?:\s+[A-Za-z]+)?)\s+([A-Za-z0-9\s\-]+)\s+(\d{4})',  # Chevy Silverado 2016
            r'(\d{4})\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(.+)',            # 2016 Chevy Silverado 1500
        ]
        
        for pattern in patterns:
            match = re.search(pattern, description)
            if match:
                groups = match.groups()
                if groups[0].isdigit():  # Year first
                    year = int(groups[0])
                    make = groups[1].strip()
                    model = groups[2].strip()
                elif len(groups) >= 3 and groups[2].isdigit():  # Year last
                    make = groups[0].strip()
                    model = groups[1].strip()
                    year = int(groups[2])
                else:  # Year first, flexible model
                    year = int(groups[0]) if groups[0].isdigit() else None
                    make = groups[1].strip()
                    model = groups[2].strip()
                break
        
        # Clean up model (remove extra words)
        if model:
            model = re.sub(r'\s+(Truck|Van|Car|Vehicle|Pickup).*$', '', model, flags=re.I).strip()
        
        return year, make, model