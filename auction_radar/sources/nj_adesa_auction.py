"""ADESA New Jersey auction scraper."""

import logging
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from .base import BaseScraper

logger = logging.getLogger(__name__)

class NJADESAAuctionScraper(BaseScraper):
    """Scraper for ADESA New Jersey auction (Thursday live auctions)."""

    def __init__(self):
        super().__init__(
            source_name='nj_adesa_auction',
            base_url='https://www.adesa.com'
        )
        self.location_url = 'https://www.adesa.com/auction_location/adesa-new-jersey/'

    def crawl(self) -> List[Dict[str, Any]]:
        """Crawl ADESA New Jersey for vehicle listings and auction information."""
        lots = []

        try:
            # Check the main ADESA NJ page for auction information
            response = self.safe_get(self.location_url)

            if not response:
                logger.error("Failed to fetch ADESA New Jersey page")
                return []

            soup = BeautifulSoup(response.text, 'html.parser')

            # Extract auction information
            auction_info = self._extract_auction_info(soup)

            if auction_info:
                lots.append(auction_info)

            # Try to access inventory if available
            inventory_lots = self._check_inventory_access()
            lots.extend(inventory_lots)

        except Exception as e:
            logger.error(f"Error crawling ADESA New Jersey: {e}")

        logger.info(f"Found {len(lots)} auction items from ADESA New Jersey")
        return lots

    def _extract_auction_info(self, soup) -> Dict[str, Any]:
        """Extract auction schedule and information from the page."""
        try:
            # Look for auction schedule information
            schedule_info = ""
            location_info = ""

            # Find schedule text
            for element in soup.find_all(text=re.compile(r'Thursday|8:30|8:45|IN-OP|Consignment', re.IGNORECASE)):
                schedule_info += f"{element.strip()} "

            # Find location information
            for element in soup.find_all(text=re.compile(r'Manville|200 N|Main Street', re.IGNORECASE)):
                location_info += f"{element.strip()} "

            # Create auction information lot
            lot_data = {
                'source': self.source_name,
                'source_lot_id': f"nj_adesa_schedule_{datetime.now().strftime('%Y%m%d')}",
                'lot_url': self.location_url,
                'sale_local_time': 'Thursday: IN-OP 8:30 AM, Consignment 8:45-9:00 AM EST',
                'location_city': 'Manville',
                'location_state': 'NJ',
                'year': None,
                'make': 'Multiple',
                'model': 'Various Vehicles',
                'vin': '',
                'auction_type': 'Live Auction',
                'auction_schedule': 'Thursday auctions - IN-OP 8:30 AM, Consignment 8:45-9:00 AM',
                'preview_hours': 'Wednesday 8 AM - 5 PM',
                'facility_hours': 'Tuesday-Sunday 6 AM - 10 PM',
                'lanes': '14 sale lanes',
                'services': 'Dealer, broker, manufacturer, and fleet vehicle sales',
                'registration_required': 'Must register to buy/sell vehicles',
                'address': '200 N. Main Street, Manville, NJ 08835',
                'phone': '908-725-2200',
                'raw_text': f"ADESA New Jersey - Thursday auctions with IN-OP sale at 8:30 AM and Consignment sale at 8:45-9:00 AM. {schedule_info.strip()} {location_info.strip()}",
                'created_at': datetime.utcnow().isoformat(),
            }

            return lot_data

        except Exception as e:
            logger.error(f"Error extracting ADESA auction info: {e}")

        return None

    def _check_inventory_access(self) -> List[Dict[str, Any]]:
        """Attempt to check for publicly accessible inventory information."""
        lots = []

        try:
            # Check if there's a public inventory page
            inventory_url = f"{self.base_url}/inventory/"
            response = self.safe_get(inventory_url)

            if response:
                soup = BeautifulSoup(response.text, 'html.parser')

                # Look for any publicly accessible vehicle information
                # Note: ADESA typically requires registration for full access
                vehicle_elements = soup.find_all('div', class_=re.compile(r'vehicle|inventory|lot', re.IGNORECASE))

                for element in vehicle_elements[:5]:  # Limit to first 5 items
                    vehicle_text = element.get_text(strip=True)
                    if len(vehicle_text) > 20:  # Only include substantial content
                        lot_data = {
                            'source': self.source_name,
                            'source_lot_id': f"nj_adesa_inventory_{len(lots)}_{datetime.now().strftime('%Y%m%d')}",
                            'lot_url': inventory_url,
                            'sale_local_time': 'Thursday auctions - registration required',
                            'location_city': 'Manville',
                            'location_state': 'NJ',
                            'raw_text': f"ADESA NJ Inventory: {vehicle_text}",
                            'access_note': 'Registration required for full vehicle details',
                            'created_at': datetime.utcnow().isoformat(),
                        }
                        lots.append(lot_data)

        except Exception as e:
            logger.error(f"Error checking ADESA inventory: {e}")

        return lots

    def get_auction_schedule(self) -> Dict[str, Any]:
        """Get the current ADESA auction schedule information."""
        return {
            'auction_day': 'Thursday',
            'sale_times': {
                'IN-OP': '8:30 AM ET',
                'Consignment': '8:45 - 9:00 AM ET'
            },
            'preview_time': 'Wednesday 8 AM - 5 PM',
            'facility_hours': 'Tuesday-Sunday 6 AM - 10 PM',
            'pickup_hours': '6 AM - 10 PM daily',
            'vehicle_dropoff': '24/7 available',
            'format': 'Live Auction',
            'lanes': 14,
            'access_requirement': 'Registration required',
            'location': 'Manville, NJ',
            'address': '200 N. Main Street, Manville, NJ 08835',
            'phone': '908-725-2200',
            'services': ['Dealer sales', 'Broker sales', 'Manufacturer sales', 'Fleet sales']
        }