import logging
import re
from typing import List, Dict, Any
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
from .base import BaseScraper
from ..utils import normalize_timezone

logger = logging.getLogger(__name__)

class PAStateSurplusScraper(BaseScraper):
    """Scraper for Pennsylvania state surplus auctions via PA DGS and Municibid."""
    
    def __init__(self):
        super().__init__('pa_state_surplus', 'https://www.pa.gov')
    
    def crawl(self) -> List[Dict[str, Any]]:
        """Crawl Pennsylvania state surplus auctions."""
        lots = []
        
        try:
            # Check PA state vehicle management page
            state_lots = self._crawl_pa_state_page()
            lots.extend(state_lots)
            
            # Also check Municibid for PA auctions
            municibid_lots = self._crawl_pa_municibid()
            lots.extend(municibid_lots)
            
            logger.info(f"Found {len(lots)} Pennsylvania state surplus lots")
                    
        except Exception as e:
            logger.error(f"Error fetching Pennsylvania surplus data: {e}")
        
        return lots
    
    def _crawl_pa_state_page(self) -> List[Dict[str, Any]]:
        """Crawl PA state vehicle management page."""
        lots = []
        
        try:
            # Check PA DGS vehicle auction page
            url = "https://www.pa.gov/agencies/dgs/programs-and-services/vehicle-management/public-information"
            response = self.safe_get(url)
            
            if not response:
                logger.debug("Could not fetch PA state vehicle management page")
                return lots
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for auction announcements and vehicle mentions
            page_text = soup.get_text().lower()
            if any(keyword in page_text for keyword in ['auction', 'vehicle', 'truck', 'car', 'fleet']):
                # Create a general lot entry for PA state auctions
                lot_data = {
                    'source': self.source_name,
                    'source_lot_id': 'pa_state_general',
                    'lot_url': url,
                    'sale_date_utc': None,
                    'sale_local_time': 'Check PA DGS for auction dates',
                    'tz_name': 'America/New_York',
                    'location_name': 'Pennsylvania State Surplus',
                    'location_city': 'Harrisburg',
                    'location_state': 'PA',
                    'year': None,
                    'make': None,
                    'model': None,
                    'vin': None,
                    'title_status': 'unknown',
                    'condition_notes': 'Pennsylvania state surplus vehicles - up to 6 auctions per year with 375+ vehicles',
                    'raw_text': 'Pennsylvania Commonwealth fleet vehicle auctions through PA DGS'
                }
                lots.append(lot_data)
                
        except Exception as e:
            logger.debug(f"Error crawling PA state page: {e}")
        
        return lots
    
    def _crawl_pa_municibid(self) -> List[Dict[str, Any]]:
        """Crawl Pennsylvania Municibid auctions."""
        lots = []
        
        try:
            # Check Municibid for PA auctions
            url = "https://municibid.com/Browse/R3777835/Pennsylvania"
            response = self.safe_get(url)
            
            if not response:
                logger.debug("Could not fetch PA Municibid page")
                return lots
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find auction item containers - Municibid uses /Listing/Details/ pattern
            auction_links = soup.find_all('a', href=re.compile(r'/Listing/Details/\d+'))
            
            logger.debug(f"Found {len(auction_links)} auction links on PA Municibid page")
            
            # Process auction links
            for link in auction_links[:15]:  # PA is large state, get more items
                href = link.get('href', '')
                auction_id = re.search(r'/Listing/Details/(\d+)', href)
                if auction_id:
                    container = link.find_parent(['div', 'article', 'td', 'li', 'tr'])
                    lot_data = self._parse_pa_item(container or link, href)
                    if lot_data:
                        # Filter for vehicles only
                        text = lot_data.get('raw_text', '').upper()
                        vehicle_keywords = ['FORD', 'CHEVY', 'GMC', 'TOYOTA', 'HONDA', 'NISSAN', 'LEXUS',
                                          'TRUCK', 'CAR', 'VAN', 'SUV', 'POLICE', 'FIRE', 'AMBULANCE',
                                          'PICKUP', 'VEHICLE', 'AUTO', '4RUNNER', 'LAND CRUISER',
                                          'TACOMA', 'TUNDRA', 'FRONTIER', 'TITAN', 'CAMPER', 'RV']
                        if any(keyword in text for keyword in vehicle_keywords):
                            lots.append(lot_data)
                            
        except Exception as e:
            logger.debug(f"Error crawling PA Municibid: {e}")
        
        return lots
    
    def _parse_pa_item(self, item, href=None) -> Dict[str, Any]:
        """Parse a Pennsylvania auction item."""
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
            vehicle_desc = lines[0] if lines else "Pennsylvania surplus item"
            
            # Extract year, make, model
            year, make, model = self._extract_vehicle_info(vehicle_desc)
            
            # Extract location - Pennsylvania cities
            city = "Harrisburg"  # Default to state capital
            pa_cities = ['Philadelphia', 'Pittsburgh', 'Allentown', 'Erie', 'Reading', 'Scranton', 
                        'Bethlehem', 'Lancaster', 'Harrisburg', 'Altoona', 'York', 'State College',
                        'Wilkes-Barre', 'Chester', 'Williamsport', 'Easton', 'Lebanon', 'Norristown']
            
            for pa_city in pa_cities:
                if pa_city.upper() in text_content.upper():
                    city = pa_city
                    break
            
            # Extract current bid
            current_bid = None
            bid_match = re.search(r'\$([0-9,]+\.?\d*)', text_content)
            if bid_match:
                try:
                    current_bid = float(bid_match.group(1).replace(',', ''))
                except:
                    pass
            
            # Build lot URL
            lot_url = f"https://municibid.com{href}" if href and href.startswith('/') else href or self.base_url
            
            lot_id = f"pa_surplus_{auction_id}" if auction_id else f"pa_surplus_{hash(vehicle_desc[:50]) % 100000}"
            
            lot_data = {
                'source': self.source_name,
                'source_lot_id': lot_id,
                'lot_url': lot_url,
                'sale_date_utc': None,
                'sale_local_time': 'TBD',
                'tz_name': 'America/New_York',
                'location_name': 'Pennsylvania Municipal Surplus',
                'location_city': city,
                'location_state': 'PA',
                'year': year,
                'make': make,
                'model': model,
                'vin': None,
                'title_status': 'unknown',
                'condition_notes': f'{vehicle_desc} - Current bid: ${current_bid:.2f}' if current_bid else vehicle_desc,
                'current_bid': current_bid,
                'raw_text': text_content[:500]
            }
            
            return lot_data
            
        except Exception as e:
            logger.debug(f"Error parsing PA item: {e}")
            return None
    
    def _extract_vehicle_info(self, description: str) -> tuple:
        """Extract year, make, model from vehicle description."""
        year, make, model = None, None, None
        
        # Common patterns for vehicle descriptions
        patterns = [
            r'(\d{4})\s+([A-Za-z]+)\s+([A-Za-z0-9\s\-]+)',
            r'([A-Za-z]+)\s+([A-Za-z0-9\s\-]+)\s+(\d{4})',
            r'(\d{4})\s+([A-Z][a-z]+)\s+(.+)',
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
                break
        
        return year, make, model