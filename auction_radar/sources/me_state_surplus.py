import logging
import re
from typing import List, Dict, Any
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
from .base import BaseScraper
from ..utils import normalize_timezone

logger = logging.getLogger(__name__)

class MEStateSurplusScraper(BaseScraper):
    """Scraper for Maine state surplus auctions via GovPlanet and direct state sales."""
    
    def __init__(self):
        super().__init__('me_state_surplus', 'https://www.maine.gov')
    
    def crawl(self) -> List[Dict[str, Any]]:
        """Crawl Maine state surplus auctions."""
        lots = []
        
        try:
            # First check Maine state surplus page for current auctions
            state_lots = self._crawl_maine_state_page()
            lots.extend(state_lots)
            
            # Also check Municibid for Maine auctions
            municibid_lots = self._crawl_maine_municibid()
            lots.extend(municibid_lots)
            
            logger.info(f"Found {len(lots)} Maine state surplus lots")
                    
        except Exception as e:
            logger.error(f"Error fetching Maine surplus data: {e}")
        
        return lots
    
    def _crawl_maine_state_page(self) -> List[Dict[str, Any]]:
        """Crawl Maine state surplus page."""
        lots = []
        
        try:
            # Check Maine state surplus auction page
            url = "https://www.maine.gov/dafs/bbm/centralservices/surplus-property/state-auctions"
            response = self.safe_get(url)
            
            if not response:
                logger.debug("Could not fetch Maine state surplus page")
                return lots
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for auction announcements and vehicle mentions
            page_text = soup.get_text().lower()
            if any(keyword in page_text for keyword in ['govplanet', 'auction', 'vehicle', 'truck', 'car']):
                # Create a general lot entry for Maine state auctions
                lot_data = {
                    'source': self.source_name,
                    'source_lot_id': 'me_state_general',
                    'lot_url': url,
                    'sale_date_utc': None,
                    'sale_local_time': 'Check GovPlanet for current auctions',
                    'tz_name': 'America/New_York',
                    'location_name': 'Maine State Surplus',
                    'location_city': 'Augusta',
                    'location_state': 'ME',
                    'year': None,
                    'make': None,
                    'model': None,
                    'vin': None,
                    'title_status': 'unknown',
                    'condition_notes': 'Maine state surplus vehicles available through GovPlanet - Wednesday auctions',
                    'raw_text': 'Maine surplus vehicles sold through GovPlanet platform'
                }
                lots.append(lot_data)
                
        except Exception as e:
            logger.debug(f"Error crawling Maine state page: {e}")
        
        return lots
    
    def _crawl_maine_municibid(self) -> List[Dict[str, Any]]:
        """Crawl Maine Municibid auctions."""
        lots = []
        
        try:
            # Check Municibid for Maine auctions
            url = "https://municibid.com/Browse/R3777816/Maine"
            response = self.safe_get(url)
            
            if not response:
                logger.debug("Could not fetch Maine Municibid page")
                return lots
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find auction item containers - Municibid uses /Listing/Details/ pattern
            auction_links = soup.find_all('a', href=re.compile(r'/Listing/Details/\d+'))
            
            logger.debug(f"Found {len(auction_links)} auction links on Maine Municibid page")
            
            # Process auction links
            for link in auction_links[:10]:  # Limit to prevent too many
                href = link.get('href', '')
                auction_id = re.search(r'/Listing/Details/(\d+)', href)
                if auction_id:
                    container = link.find_parent(['div', 'article', 'td', 'li', 'tr'])
                    lot_data = self._parse_maine_item(container or link, href)
                    if lot_data:
                        # Filter for vehicles only
                        text = lot_data.get('raw_text', '').upper()
                        vehicle_keywords = ['FORD', 'CHEVY', 'GMC', 'TOYOTA', 'HONDA', 'NISSAN', 'TRUCK', 'CAR', 'VAN', 'SUV', 'VEHICLE']
                        if any(keyword in text for keyword in vehicle_keywords):
                            lots.append(lot_data)
                            
        except Exception as e:
            logger.debug(f"Error crawling Maine Municibid: {e}")
        
        return lots
    
    def _parse_maine_item(self, item, href=None) -> Dict[str, Any]:
        """Parse a Maine auction item."""
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
            vehicle_desc = lines[0] if lines else "Maine surplus item"
            
            # Extract year, make, model
            year, make, model = self._extract_vehicle_info(vehicle_desc)
            
            # Extract location - Maine cities
            city = "Augusta"  # Default to state capital
            me_cities = ['Portland', 'Lewiston', 'Bangor', 'South Portland', 'Auburn', 'Biddeford', 
                        'Sanford', 'Saco', 'Augusta', 'Westbrook', 'Waterville', 'Presque Isle']
            
            for me_city in me_cities:
                if me_city.upper() in text_content.upper():
                    city = me_city
                    break
            
            # Build lot URL
            lot_url = f"https://municibid.com{href}" if href and href.startswith('/') else href or self.base_url
            
            lot_id = f"me_surplus_{auction_id}" if auction_id else f"me_surplus_{hash(vehicle_desc[:50]) % 100000}"
            
            lot_data = {
                'source': self.source_name,
                'source_lot_id': lot_id,
                'lot_url': lot_url,
                'sale_date_utc': None,
                'sale_local_time': 'TBD',
                'tz_name': 'America/New_York',
                'location_name': 'Maine Municipal Surplus',
                'location_city': city,
                'location_state': 'ME',
                'year': year,
                'make': make,
                'model': model,
                'vin': None,
                'title_status': 'unknown',
                'condition_notes': vehicle_desc,
                'raw_text': text_content[:500]
            }
            
            return lot_data
            
        except Exception as e:
            logger.debug(f"Error parsing Maine item: {e}")
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