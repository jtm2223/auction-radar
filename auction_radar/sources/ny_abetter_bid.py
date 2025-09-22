import logging
from typing import List, Dict, Any
from datetime import datetime, timedelta
import re
from bs4 import BeautifulSoup
from .base import BaseScraper
from ..utils import safe_get_text, normalize_timezone
import json
import time

logger = logging.getLogger(__name__)

class NYABetterBidScraper(BaseScraper):
    """Scraper for A Better Bid auction listings targeting specific vehicles in Northeast states."""

    def __init__(self):
        super().__init__('abetter_bid_northeast', 'https://abetter.bid')

        # Target vehicle search URLs for NY, CT, MA, RI, NJ
        self.target_searches = {
            # New York
            'toyota_4runner_ny': '/en/car-finder/type-automobiles/make-toyota/model-4runner/state-ny',
            'toyota_land_cruiser_ny': '/en/car-finder/type-automobiles/make-toyota/model-land_cruiser/state-ny',
            'toyota_tacoma_ny': '/en/car-finder/type-automobiles/make-toyota/model-tacoma/state-ny',
            'toyota_tundra_ny': '/en/car-finder/type-automobiles/make-toyota/model-tundra/state-ny',
            'nissan_frontier_ny': '/en/car-finder/type-automobiles/make-nissan/model-frontier/state-ny',

            # Connecticut
            'toyota_4runner_ct': '/en/car-finder/type-automobiles/make-toyota/model-4runner/state-ct',
            'toyota_land_cruiser_ct': '/en/car-finder/type-automobiles/make-toyota/model-land_cruiser/state-ct',
            'toyota_tacoma_ct': '/en/car-finder/type-automobiles/make-toyota/model-tacoma/state-ct',
            'toyota_tundra_ct': '/en/car-finder/type-automobiles/make-toyota/model-tundra/state-ct',
            'nissan_frontier_ct': '/en/car-finder/type-automobiles/make-nissan/model-frontier/state-ct',

            # Massachusetts
            'toyota_4runner_ma': '/en/car-finder/type-automobiles/make-toyota/model-4runner/state-ma',
            'toyota_land_cruiser_ma': '/en/car-finder/type-automobiles/make-toyota/model-land_cruiser/state-ma',
            'toyota_tacoma_ma': '/en/car-finder/type-automobiles/make-toyota/model-tacoma/state-ma',
            'toyota_tundra_ma': '/en/car-finder/type-automobiles/make-toyota/model-tundra/state-ma',
            'nissan_frontier_ma': '/en/car-finder/type-automobiles/make-nissan/model-frontier/state-ma',

            # Rhode Island
            'toyota_4runner_ri': '/en/car-finder/type-automobiles/make-toyota/model-4runner/state-ri',
            'toyota_land_cruiser_ri': '/en/car-finder/type-automobiles/make-toyota/model-land_cruiser/state-ri',
            'toyota_tacoma_ri': '/en/car-finder/type-automobiles/make-toyota/model-tacoma/state-ri',
            'toyota_tundra_ri': '/en/car-finder/type-automobiles/make-toyota/model-tundra/state-ri',
            'nissan_frontier_ri': '/en/car-finder/type-automobiles/make-nissan/model-frontier/state-ri',

            # New Jersey
            'toyota_4runner_nj': '/en/car-finder/type-automobiles/make-toyota/model-4runner/state-nj',
            'toyota_land_cruiser_nj': '/en/car-finder/type-automobiles/make-toyota/model-land_cruiser/state-nj',
            'toyota_tacoma_nj': '/en/car-finder/type-automobiles/make-toyota/model-tacoma/state-nj',
            'toyota_tundra_nj': '/en/car-finder/type-automobiles/make-toyota/model-tundra/state-nj',
            'nissan_frontier_nj': '/en/car-finder/type-automobiles/make-nissan/model-frontier/state-nj'
        }

    def crawl(self) -> List[Dict[str, Any]]:
        """Crawl A Better Bid for target vehicles in Northeast states."""
        all_lots = []

        for vehicle_type, search_url in self.target_searches.items():
            try:
                logger.info(f"Searching for {vehicle_type}...")

                # Get the search results page
                full_url = f"{self.base_url}{search_url}"
                response = self.safe_get(full_url, headers=self.get_headers())
                if not response:
                    logger.warning(f"Could not fetch {vehicle_type} search page")
                    continue

                soup = BeautifulSoup(response.text, 'html.parser')

                # Parse vehicles from this search page
                vehicles = self._parse_vehicle_search_page(soup, full_url, vehicle_type)
                all_lots.extend(vehicles)

                logger.info(f"Found {len(vehicles)} {vehicle_type} vehicles")

                # Be respectful with requests
                time.sleep(2)

            except Exception as e:
                logger.error(f"Error searching for {vehicle_type}: {e}")
                continue

        logger.info(f"Total target vehicles found: {len(all_lots)}")
        return all_lots

    def _parse_vehicle_search_page(self, soup: BeautifulSoup, page_url: str, vehicle_type: str) -> List[Dict[str, Any]]:
        """Parse individual vehicles from a search results page."""
        vehicles = []

        # Look for vehicle cards/listings in the HTML - A Better Bid uses car-card class
        vehicle_containers = soup.find_all(['div', 'article'], class_=re.compile(r'(car-card|vehicle|card|item|listing|result)', re.IGNORECASE))

        processed_vehicles = set()

        # Parse structured vehicle containers first (this is the main method for A Better Bid)
        for container in vehicle_containers:
            vehicle_data = self._parse_vehicle_container(container, page_url, vehicle_type)
            if vehicle_data:
                # Check for duplicates
                vehicle_id = f"{vehicle_data.get('year', '')}_{vehicle_data.get('make', '')}_{vehicle_data.get('model', '')}"
                if vehicle_id not in processed_vehicles:
                    vehicles.append(vehicle_data)
                    processed_vehicles.add(vehicle_id)

        # Fallback: look for data-title attributes which contain vehicle info
        if not vehicles:
            title_elements = soup.find_all(attrs={'data-title': re.compile(r'20\d{2}.*(?:Toyota|Nissan|Lexus)', re.IGNORECASE)})

            # Also look for direct vehicle data patterns in text
            page_text = soup.get_text()

            # Extract year make model patterns - look for both text and HTML patterns
            vehicle_patterns = [
                r'(20\d{2})\s+(Toyota|Nissan|Lexus)\s+([^\\n]*?)(?=\\n|Sale|Location|Odometer|$)',
                r'data-title="(20\d{2})\s+(Toyota|Nissan|Lexus)\s+([^"]*)"',
                r'>\s*(20\d{2})\s+(Toyota|Nissan|Lexus)\s+([^<]*?)\s*<'
            ]

            vehicle_matches = []
            for pattern in vehicle_patterns:
                matches = list(re.finditer(pattern, soup.get_text() + str(soup), re.IGNORECASE))
                vehicle_matches.extend(matches)

            for match in vehicle_matches:
                year, make, model_raw = match.groups()

                # Clean up model
                model = model_raw.strip()
                model = re.sub(r'\\s+', ' ', model)

                # Create unique ID to avoid duplicates
                vehicle_id = f"{year}_{make}_{model}".lower().replace(' ', '_')
                if vehicle_id in processed_vehicles:
                    continue
                processed_vehicles.add(vehicle_id)

                # Extract additional details from surrounding context
                context_start = max(0, match.start() - 1000)
                context_end = min(len(page_text), match.end() + 2000)
                context = page_text[context_start:context_end]

                vehicle_data = self._extract_vehicle_details(context, year, make, model, page_url, vehicle_type)
                if vehicle_data:
                    vehicles.append(vehicle_data)

        return vehicles

    def _extract_vehicle_details(self, context: str, year: str, make: str, model: str, page_url: str, vehicle_type: str) -> Dict[str, Any]:
        """Extract detailed vehicle information from context text."""

        # Extract location and determine state - try multiple patterns
        location_patterns = [
            r'Location:?\\s*([A-Z]{2}\\s*-\\s*[A-Z\\s]+)',
            r'Location:?\\s*\\n\\s*([A-Z]{2}\\s*-\\s*[A-Z\\s]+)',
            r'Location[:\\s]*\\n?\\s*([A-Z]{2}\\s*-\\s*[A-Z\\s]+)'
        ]

        location = None
        for pattern in location_patterns:
            location_match = re.search(pattern, context, re.IGNORECASE | re.MULTILINE)
            if location_match:
                location = location_match.group(1).strip()
                break

        # Determine state and city from vehicle_type
        if '_ny' in vehicle_type:
            location_state = 'NY'
            location_city = 'New York'
            if location:
                if 'ROCHESTER' in location:
                    location_city = 'Rochester'
                elif 'LONG ISLAND' in location:
                    location_city = 'Long Island'
                elif 'ALBANY' in location:
                    location_city = 'Albany'
                elif 'BUFFALO' in location:
                    location_city = 'Buffalo'
                elif 'SYRACUSE' in location:
                    location_city = 'Syracuse'
                elif 'NEWBURGH' in location:
                    location_city = 'Newburgh'
        elif '_ct' in vehicle_type:
            location_state = 'CT'
            location_city = 'Hartford'
            if location:
                if 'BRIDGEPORT' in location:
                    location_city = 'Bridgeport'
                elif 'NEW HAVEN' in location:
                    location_city = 'New Haven'
                elif 'WATERBURY' in location:
                    location_city = 'Waterbury'
                elif 'STAMFORD' in location:
                    location_city = 'Stamford'
        elif '_ma' in vehicle_type:
            location_state = 'MA'
            location_city = 'Boston'
            if location:
                if 'WORCESTER' in location:
                    location_city = 'Worcester'
                elif 'SPRINGFIELD' in location:
                    location_city = 'Springfield'
                elif 'LOWELL' in location:
                    location_city = 'Lowell'
                elif 'CAMBRIDGE' in location:
                    location_city = 'Cambridge'
        elif '_ri' in vehicle_type:
            location_state = 'RI'
            location_city = 'Providence'
            if location:
                if 'WARWICK' in location:
                    location_city = 'Warwick'
                elif 'CRANSTON' in location:
                    location_city = 'Cranston'
                elif 'PAWTUCKET' in location:
                    location_city = 'Pawtucket'
                elif 'NEWPORT' in location:
                    location_city = 'Newport'
        elif '_nj' in vehicle_type:
            location_state = 'NJ'
            location_city = 'Newark'
            if location:
                if 'JERSEY CITY' in location:
                    location_city = 'Jersey City'
                elif 'PATERSON' in location:
                    location_city = 'Paterson'
                elif 'ELIZABETH' in location:
                    location_city = 'Elizabeth'
                elif 'TRENTON' in location:
                    location_city = 'Trenton'
                elif 'CAMDEN' in location:
                    location_city = 'Camden'
        else:
            location_state = 'NY'  # default
            location_city = 'New York'

        # Extract sale date - try multiple patterns
        date_patterns = [
            r'Sale Date:?\\s*(\\d{2}/\\d{2}/\\d{4})',
            r'Sale Date:?\\s*\\n\\s*(\\d{2}/\\d{2}/\\d{4})',
            r'Sale Date[:\\s]*\\n?\\s*(\\d{1,2}/\\d{1,2}/\\d{4})',
            r'(?:Sale Date|Date):?[\\s\\n]+(\\d{1,2}/\\d{1,2}/\\d{4})'
        ]

        sale_date = None
        for pattern in date_patterns:
            date_match = re.search(pattern, context, re.IGNORECASE | re.MULTILINE)
            if date_match:
                sale_date = date_match.group(1)
                break

        # Extract lot number
        lot_match = re.search(r'Lot\\s*#?\\s*(\\d+)', context, re.IGNORECASE)
        lot_number = lot_match.group(1) if lot_match else None

        # Extract odometer - try multiple patterns
        odo_patterns = [
            r'Odometer:?\\s*(\\d{1,3}(?:,\\d{3})*)\\s*miles',
            r'Odometer:?\\s*\\n\\s*(\\d{1,3}(?:,\\d{3})*)\\s*miles',
            r'Odometer[:\\s]*\\n?\\s*(\\d{1,3}(?:,\\d{3})*)\\s*miles'
        ]

        mileage = None
        for pattern in odo_patterns:
            odo_match = re.search(pattern, context, re.IGNORECASE | re.MULTILINE)
            if odo_match:
                mileage = odo_match.group(1).replace(',', '')
                break

        # Extract damage - try multiple patterns
        damage_patterns = [
            r'Damage:?\\s*([A-Z\\s]+?)(?=Location|Sale|Transmission|Odometer|$)',
            r'Damage:?\\s*\\n\\s*([A-Z\\s]+?)(?=\\n|$)',
            r'Damage[:\\s]*\\n?\\s*([A-Z\\s]+?)(?=\\n|$)'
        ]

        damage = 'Unknown'
        for pattern in damage_patterns:
            damage_match = re.search(pattern, context, re.IGNORECASE | re.MULTILINE)
            if damage_match:
                damage = damage_match.group(1).strip()
                break

        # Extract current bid
        bid_match = re.search(r'Current bid:?\\s*\\$([\\d,]+)', context)
        current_bid = bid_match.group(1).replace(',', '') if bid_match else None

        # Extract buy it now price
        bin_match = re.search(r'Buy It Now:?\\s*\\$([\\d,]+)', context)
        buy_it_now = bin_match.group(1).replace(',', '') if bin_match else None

        # Extract VIN if available
        vin_match = re.search(r'VIN:?\\s*([A-Z0-9]{17})', context)
        vin = vin_match.group(1) if vin_match else None

        # Parse sale date
        sale_date_utc = None
        tz_name = None
        sale_local_time = None

        if sale_date:
            try:
                date_obj = datetime.strptime(sale_date, '%m/%d/%Y')
                sale_local_time = f"{date_obj.strftime('%B %d, %Y')} 2:00 PM"
                sale_date_utc, tz_name = normalize_timezone(sale_local_time, "America/New_York")
            except:
                sale_local_time = sale_date

        # Create lot ID
        lot_id = f"abetter_bid_{vehicle_type}_{year}_{make}_{model.replace(' ', '_')}_{location_city.replace(' ', '_')}"
        if lot_number:
            lot_id += f"_lot{lot_number}"

        # Build condition notes
        condition_notes = f"Damage: {damage}"
        if mileage:
            condition_notes += f", Mileage: {mileage} miles"

        # Build description
        description = f"{year} {make} {model}"
        if damage and damage != 'UNKNOWN':
            description += f" - {damage} damage"
        if current_bid:
            description += f", Current bid: ${current_bid}"
        if buy_it_now:
            description += f", Buy It Now: ${buy_it_now}"

        return {
            'source': self.source_name,
            'source_lot_id': lot_id,
            'sale_date_utc': sale_date_utc.isoformat() if sale_date_utc else None,
            'sale_local_time': sale_local_time,
            'tz_name': tz_name,
            'location_name': f'A Better Bid Auction - {location_city}',
            'location_city': location_city,
            'location_state': location_state,
            'lot_url': page_url,
            'year': int(year),
            'make': make.upper(),
            'model': model,
            'vin': vin,
            'raw_text': description
        }

    def _parse_vehicle_container(self, container, page_url: str, vehicle_type: str) -> Dict[str, Any]:
        """Parse vehicle data from HTML container element."""
        try:
            container_text = container.get_text()

            # Look for year make model in container
            vehicle_match = re.search(r'(20\d{2})\s+(Toyota|Nissan|Lexus)\s+([^\n]+)', container_text, re.IGNORECASE)
            if not vehicle_match:
                return None

            year, make, model = vehicle_match.groups()

            # Extract sale date from car-card structure
            sale_date = None
            sale_date_elem = container.find('div', class_='car-card__details-name', string=re.compile(r'Sale Date', re.IGNORECASE))
            if sale_date_elem:
                # Look for the next sibling with the actual date
                date_elem = sale_date_elem.find_next_sibling('div', class_='car-card__details-text')
                if date_elem:
                    sale_date = date_elem.get_text().strip()
                else:
                    # Try looking in the parent container
                    parent = sale_date_elem.parent
                    if parent:
                        date_elem = parent.find('div', class_='car-card__details-text')
                        if date_elem:
                            sale_date = date_elem.get_text().strip()

            # Extract location from car-card structure
            location = None
            location_elem = container.find('div', class_='car-card__details-name', string=re.compile(r'Location', re.IGNORECASE))
            if location_elem:
                location_text_elem = location_elem.find_next_sibling('div', class_='car-card__details-text')
                if location_text_elem:
                    location = location_text_elem.get_text().strip()

            # Extract mileage from car-card structure
            mileage = None
            odo_elem = container.find('div', class_='car-card__details-name', string=re.compile(r'Odometer', re.IGNORECASE))
            if odo_elem:
                odo_text_elem = odo_elem.find_next_sibling('div', class_='car-card__details-text')
                if odo_text_elem:
                    odo_text = odo_text_elem.get_text().strip()
                    odo_match = re.search(r'(\d{1,3}(?:,\d{3})*)\s*miles', odo_text)
                    if odo_match:
                        mileage = odo_match.group(1).replace(',', '')

            # Extract damage from car-card structure
            damage = 'Unknown'
            damage_elem = container.find('div', class_='car-card__details-name', string=re.compile(r'Damage', re.IGNORECASE))
            if damage_elem:
                damage_text_elem = damage_elem.find_next_sibling('div', class_='car-card__details-text')
                if damage_text_elem:
                    damage = damage_text_elem.get_text().strip()

            # Build the vehicle data directly instead of using _extract_vehicle_details
            return self._build_vehicle_data(year, make, model.strip(), page_url, vehicle_type,
                                          sale_date, location, mileage, damage)

        except Exception as e:
            logger.debug(f"Error parsing vehicle container: {e}")
            return None

    def _build_vehicle_data(self, year: str, make: str, model: str, page_url: str, vehicle_type: str,
                           sale_date: str = None, location: str = None, mileage: str = None, damage: str = None) -> Dict[str, Any]:
        """Build vehicle data dictionary from extracted components."""

        # Determine state and city from vehicle_type
        if '_ny' in vehicle_type:
            location_state = 'NY'
            location_city = 'New York'
            if location and 'ALBANY' in location.upper():
                location_city = 'Albany'
            elif location and 'ROCHESTER' in location.upper():
                location_city = 'Rochester'
        elif '_ct' in vehicle_type:
            location_state = 'CT'
            location_city = 'Hartford'
            if location and 'BRIDGEPORT' in location.upper():
                location_city = 'Bridgeport'
        elif '_ma' in vehicle_type:
            location_state = 'MA'
            location_city = 'Boston'
            if location and 'WORCESTER' in location.upper():
                location_city = 'Worcester'
        elif '_ri' in vehicle_type:
            location_state = 'RI'
            location_city = 'Providence'
        elif '_nj' in vehicle_type:
            location_state = 'NJ'
            location_city = 'Newark'
        else:
            location_state = 'NY'
            location_city = 'New York'

        # Parse sale date
        sale_date_utc = None
        tz_name = None
        sale_local_time = None

        if sale_date:
            try:
                from datetime import datetime
                from ..utils import normalize_timezone

                date_obj = datetime.strptime(sale_date, '%m/%d/%Y')
                sale_local_time = f"{date_obj.strftime('%B %d, %Y')} 2:00 PM"
                sale_date_utc, tz_name = normalize_timezone(sale_local_time, "America/New_York")
            except:
                sale_local_time = sale_date

        # Create lot ID
        lot_id = f"abetter_bid_{vehicle_type}_{year}_{make}_{model.replace(' ', '_')}_{location_city.replace(' ', '_')}"

        # Build description
        description = f"{year} {make} {model}"
        if damage and damage != 'Unknown':
            description += f" - {damage} damage"
        if mileage:
            description += f", {mileage} miles"

        return {
            'source': self.source_name,
            'source_lot_id': lot_id,
            'sale_date_utc': sale_date_utc.isoformat() if sale_date_utc else None,
            'sale_local_time': sale_local_time,
            'tz_name': tz_name,
            'location_name': f'A Better Bid Auction - {location_city}',
            'location_city': location_city,
            'location_state': location_state,
            'lot_url': page_url,
            'year': int(year),
            'make': make.upper(),
            'model': model,
            'vin': None,  # VIN not typically available on search page
            'raw_text': description
        }

    def get_headers(self) -> Dict[str, str]:
        """Get headers for A Better Bid requests."""
        headers = super().get_headers()
        headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none'
        })
        return headers