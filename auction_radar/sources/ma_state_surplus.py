import logging
import re
from typing import List, Dict, Any
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from .base import BaseScraper
from ..utils import normalize_timezone

logger = logging.getLogger(__name__)

class MAStateSurplusScraper(BaseScraper):
    """Scraper for Massachusetts municipal surplus auctions via Municibid."""
    
    def __init__(self):
        super().__init__('ma_state_surplus', 'https://municibid.com')
    
    def crawl(self) -> List[Dict[str, Any]]:
        """Crawl Massachusetts municipal surplus auctions from Municibid."""
        lots = []
        
        try:
            # Fetch Massachusetts municipal auctions from Municibid
            url = "https://municibid.com/Browse/R3777818/Massachusetts"
            response = self.safe_get(url)
            
            if not response:
                logger.warning("Could not fetch MA Municibid page")
                return []
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find auction item containers - Municibid uses /Listing/Details/ pattern
            auction_links = soup.find_all('a', href=re.compile(r'/Listing/Details/\d+'))
            
            logger.debug(f"Found {len(auction_links)} auction links on MA page")
            
            # Process auction links
            all_items = []
            processed_ids = set()
            
            for link in auction_links:
                href = link.get('href', '')
                auction_id = re.search(r'/Listing/Details/(\d+)', href)
                if auction_id:
                    aid = auction_id.group(1)
                    if aid not in processed_ids:
                        processed_ids.add(aid)
                        # Find parent container with more info
                        container = link.find_parent(['div', 'article'], class_=re.compile(r'auction|item|listing|card'))
                        if not container:
                            container = link.find_parent(['div', 'td', 'li'])
                        all_items.append((container or link, link.get('href')))
            
            logger.debug(f"Found {len(all_items)} potential MA auction items")
            
            for item, href in all_items:
                try:
                    lot_data = self._parse_municibid_item(item, href)
                    if lot_data:
                        # Filter for vehicles only - check if it has vehicle-related keywords
                        text = lot_data.get('raw_text', '').upper()
                        vehicle_keywords = ['FORD', 'CHEVY', 'GMC', 'TOYOTA', 'HONDA', 'NISSAN', 'TRUCK', 'CAR', 'VAN', 'SUV', 'POLICE', 'FIRE', 'AMBULANCE']
                        if any(keyword in text for keyword in vehicle_keywords):
                            lots.append(lot_data)
                except Exception as e:
                    logger.debug(f"Error parsing MA auction item: {e}")
                    continue
                    
            logger.info(f"Found {len(lots)} Massachusetts municipal surplus lots")
                    
        except Exception as e:
            logger.error(f"Error fetching MA Municibid data: {e}")
        
        return lots
    
    def _parse_municibid_item(self, item, href=None) -> Dict[str, Any]:
        """Parse a Municibid auction item for Massachusetts."""
        try:
            text_content = item.get_text().strip()
            
            # Extract auction ID from href
            auction_id = ""
            if href:
                auction_match = re.search(r'/Listing/Details/(\d+)', href)
                if auction_match:
                    auction_id = auction_match.group(1)
            
            # Parse vehicle details from text
            lines = [line.strip() for line in text_content.split('\n') if line.strip()]
            
            # Find the main vehicle description line
            vehicle_desc = ""
            for line in lines:
                if any(word in line.upper() for word in ['FORD', 'CHEVY', 'GMC', 'TOYOTA', 'HONDA', 'NISSAN', 'TRUCK', 'CAR', 'VAN']):
                    vehicle_desc = line
                    break
            
            if not vehicle_desc and lines:
                vehicle_desc = lines[0]  # Use first line as fallback
            
            # Extract year, make, model
            year, make, model = self._extract_vehicle_info(vehicle_desc)
            
            # Extract location
            city = "Boston"  # Default
            location_match = re.search(r'([A-Za-z\s]+),?\s*MA\b', text_content)
            if location_match:
                city = location_match.group(1).strip()
            else:
                # Look for city names in the text
                ma_cities = ['Boston', 'Cambridge', 'Springfield', 'Worcester', 'Lowell', 'Brockton', 'New Bedford', 'Quincy', 'Lynn', 'Newton', 'Lawrence', 'Somerville', 'Framingham', 'Haverhill', 'Waltham', 'Malden', 'Brookline', 'Plymouth', 'Medford', 'Taunton', 'Chicopee', 'Weymouth', 'Revere', 'Peabody', 'Methuen', 'Barnstable', 'Pittsfield', 'Attleboro', 'Mill River', 'Merrimac', 'Berlin']
                for ma_city in ma_cities:
                    if ma_city.upper() in text_content.upper():
                        city = ma_city
                        break
            
            # Extract current bid
            current_bid = None
            bid_match = re.search(r'\$([0-9,]+\.?\d*)', text_content)
            if bid_match:
                try:
                    current_bid = float(bid_match.group(1).replace(',', ''))
                except:
                    pass
            
            # Extract bid count
            bid_count_match = re.search(r'(\d+)\s*bids?', text_content, re.I)
            bid_count = int(bid_count_match.group(1)) if bid_count_match else None
            
            # Build lot URL
            lot_url = f"https://municibid.com{href}" if href and href.startswith('/') else href or self.base_url
            
            lot_id = f"ma_municibid_{auction_id}" if auction_id else f"ma_municibid_{hash(vehicle_desc[:50]) % 100000}"
            
            lot_data = {
                'source': self.source_name,
                'source_lot_id': lot_id,
                'lot_url': lot_url,
                'sale_date_utc': None,
                'sale_local_time': 'TBD',  # Municibid shows relative time
                'tz_name': 'America/New_York',
                'location_name': 'Massachusetts Municipal Surplus',
                'location_city': city,
                'location_state': 'MA',
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
            logger.debug(f"Error parsing MA Municibid item: {e}")
            return None
    
    def _extract_vehicle_info(self, description: str) -> tuple:
        """Extract year, make, model from vehicle description."""
        year, make, model = None, None, None
        
        # Common patterns for vehicle descriptions
        patterns = [
            r'(\d{4})\s+([A-Za-z]+)\s+([A-Za-z0-9\s\-]+)',  # 2015 Ford F550
            r'([A-Za-z]+)\s+([A-Za-z0-9\s\-]+)\s+(\d{4})',  # Ford F550 2015
            r'(\d{4})\s+([A-Z][a-z]+)\s+(.+)',              # 2006 Ford Econoline Van
        ]
        
        for pattern in patterns:
            match = re.search(pattern, description)
            if match:
                groups = match.groups()
                if groups[0].isdigit():  # Year first
                    year = int(groups[0])
                    make = groups[1].strip()
                    model = groups[2].strip()
                elif groups[2].isdigit():  # Year last
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
            model = re.sub(r'\s+(Truck|Van|Car|Vehicle).*$', '', model, flags=re.I).strip()
        
        return year, make, model