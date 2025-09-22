"""Connecticut Statewide Auto Auction scraper."""

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from .base import BaseScraper

logger = logging.getLogger(__name__)

class CTStatewideAuctionScraper(BaseScraper):
    """Scraper for Connecticut Statewide Auto Auction (OtoCore platform)."""

    def __init__(self):
        super().__init__(
            source_name='ct_statewide_auction',
            base_url='https://www.statewideauction.com'
        )
        self.otocore_base = 'https://app.otocore.com'

    def crawl(self) -> List[Dict[str, Any]]:
        """Crawl CT Statewide Auto Auction for vehicle listings."""
        lots = []

        # Get both Tuesday (schedule_id=5) and Thursday (schedule_id=6) auctions
        schedule_ids = [5, 6]  # Tuesday=5, Thursday=6

        for schedule_id in schedule_ids:
            auction_lots = self._get_auction_lots(schedule_id)
            lots.extend(auction_lots)

        logger.info(f"Found {len(lots)} total lots from CT Statewide Auto Auction")
        return lots

    def _get_auction_lots(self, schedule_id: int) -> List[Dict[str, Any]]:
        """Get lots for a specific auction schedule."""
        lots = []

        # OtoCore runlist URL
        runlist_url = f"{self.otocore_base}/lib/iframe_runlist.cgi?auction_id=2&auction_schedule_id={schedule_id}"

        logger.info(f"Fetching runlist from: {runlist_url}")
        response = self.safe_get(runlist_url)

        if not response:
            logger.error(f"Failed to fetch runlist for schedule_id {schedule_id}")
            return []

        try:
            soup = BeautifulSoup(response.text, 'html.parser')

            # Extract the specific auction date and time from the page
            auction_datetime_info = self._extract_auction_datetime(soup)

            # Find the main table containing vehicle data
            table = soup.find('table', {'id': 'runlist_table'}) or soup.find('table')

            if not table:
                logger.warning(f"No table found in runlist for schedule_id {schedule_id}")
                return []

            # Get table rows (skip header row)
            rows = table.find_all('tr')[1:]  # Skip header

            for row in rows:
                lot_data = self._parse_table_row(row, schedule_id, auction_datetime_info)
                if lot_data:
                    lots.append(lot_data)

        except Exception as e:
            logger.error(f"Error parsing runlist for schedule_id {schedule_id}: {e}")

        logger.info(f"Parsed {len(lots)} lots for schedule_id {schedule_id}")
        return lots

    def _extract_auction_datetime(self, soup) -> Dict[str, str]:
        """Extract the precise auction date and time from the page."""
        auction_info = {
            'date_text': 'Next Tuesday/Thursday',  # fallback
            'formatted_date': None
        }

        try:
            # Look for the "Next Auction is on" text
            page_text = soup.get_text()

            # Search for pattern like "Next Auction is on : Tue Sep, 23 15:50 PM"
            date_pattern = r'Next Auction is on\s*:\s*([A-Za-z]{3}\s+[A-Za-z]{3},?\s+\d{1,2}\s+\d{1,2}:\d{2}\s+[AP]M)'
            match = re.search(date_pattern, page_text)

            if match:
                date_text = match.group(1).strip()
                auction_info['date_text'] = date_text

                # Try to parse and format the date
                try:
                    # Parse the date format like "Tue Sep, 23 15:50 PM"
                    # Remove the comma and adjust format for parsing
                    clean_date = date_text.replace(',', '')

                    # Convert to datetime for better formatting
                    parsed_date = datetime.strptime(clean_date, '%a %b %d %H:%M %p')

                    # Add current year since it's not specified
                    current_year = datetime.now().year
                    parsed_date = parsed_date.replace(year=current_year)

                    # Format as a cleaner string
                    auction_info['formatted_date'] = parsed_date.strftime('%A, %B %d at %I:%M %p EST')

                except ValueError as e:
                    logger.warning(f"Could not parse date '{date_text}': {e}")

            else:
                logger.warning("Could not find 'Next Auction is on' date pattern")

        except Exception as e:
            logger.error(f"Error extracting auction datetime: {e}")

        return auction_info

    def _parse_table_row(self, row, schedule_id: int, auction_datetime_info: Dict[str, str] = None) -> Dict[str, Any]:
        """Parse a table row into lot data."""
        try:
            cells = row.find_all('td')

            if len(cells) < 6:
                return None

            # Extract data from cells
            car_num = cells[0].get_text(strip=True) if len(cells) > 0 else ''
            year = cells[2].get_text(strip=True) if len(cells) > 2 else ''
            make = cells[3].get_text(strip=True) if len(cells) > 3 else ''
            model = cells[4].get_text(strip=True) if len(cells) > 4 else ''
            vin = cells[5].get_text(strip=True) if len(cells) > 5 else ''
            mileage = cells[6].get_text(strip=True) if len(cells) > 6 else ''

            # Clean and validate data
            year_int = None
            if year and year.isdigit():
                year_int = int(year)

            # Build raw text description
            raw_text_parts = []
            if year:
                raw_text_parts.append(year)
            if make:
                raw_text_parts.append(make)
            if model:
                raw_text_parts.append(model)
            if mileage:
                raw_text_parts.append(f"{mileage} miles")
            if vin:
                raw_text_parts.append(f"VIN: {vin}")

            raw_text = ' '.join(raw_text_parts)

            # Set default auction day and time for fallback
            auction_day = 'Tuesday' if schedule_id == 5 else 'Thursday'
            auction_time = '3:45 PM' if schedule_id == 5 else '9:50 AM'

            # Use extracted auction datetime info if available
            if auction_datetime_info and auction_datetime_info.get('formatted_date'):
                sale_local_time = auction_datetime_info['formatted_date']
            elif auction_datetime_info and auction_datetime_info.get('date_text'):
                sale_local_time = auction_datetime_info['date_text']
            else:
                # Fallback to the old method
                sale_local_time = f"Next {auction_day} at {auction_time} EST"

            # Create lot URL pointing to main site
            lot_url = f"{self.base_url}/"

            lot_data = {
                'source': self.source_name,
                'source_lot_id': f"ct_statewide_{schedule_id}_{car_num}",
                'lot_url': lot_url,
                'sale_local_time': sale_local_time,
                'location_city': 'Meriden',
                'location_state': 'CT',
                'year': year_int,
                'make': make.title() if make else '',
                'model': model.title() if model else '',
                'vin': vin.upper() if vin else '',
                'mileage': mileage,
                'car_number': car_num,
                'auction_day': auction_day,
                'auction_time': auction_time,
                'raw_text': raw_text,
                'created_at': datetime.now(timezone.utc).isoformat(),
            }

            return lot_data

        except Exception as e:
            logger.error(f"Error parsing table row: {e}")
            return None