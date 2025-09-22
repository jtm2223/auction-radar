"""GSA Auctions scraper for federal government vehicle auctions."""

import logging
import re
from typing import List, Dict, Any
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
from .base import BaseScraper
from ..utils import normalize_timezone

logger = logging.getLogger(__name__)

class GSAAuctionsScraper(BaseScraper):
    """Scraper for GSA Federal vehicle auctions - very reliable source."""
    
    def __init__(self):
        super().__init__('gsa_auctions', 'https://gsaauctions.gov')
    
    def crawl(self) -> List[Dict[str, Any]]:
        """Crawl GSA Auctions for vehicles in Northeast states."""
        lots = []
        
        try:
            # Northeast zip codes for major cities
            northeast_zips = [
                '10001',  # NYC
                '02101',  # Boston
                '06101',  # Hartford
                '07101',  # Newark
                '02901',  # Providence
                '12210',  # Albany
            ]
            
            for zip_code in northeast_zips[:3]:  # Limit to prevent too many requests
                page_lots = self._search_gsa_vehicles(zip_code)
                lots.extend(page_lots)
                
                # Rate limiting
                import time
                time.sleep(2)
            
            # Remove duplicates by auction ID
            seen_ids = set()
            unique_lots = []
            for lot in lots:
                lot_id = lot.get('source_lot_id')
                if lot_id not in seen_ids:
                    seen_ids.add(lot_id)
                    unique_lots.append(lot)
            
            logger.info(f"Found {len(unique_lots)} unique GSA vehicle lots")
            
        except Exception as e:
            logger.error(f"Error fetching GSA Auctions data: {e}")
        
        return unique_lots[:50]  # Limit results
    
    def _search_gsa_vehicles(self, zip_code: str) -> List[Dict[str, Any]]:
        """Search GSA for vehicles near zip code."""
        lots = []
        
        try:
            # GSA vehicle search URL
            search_url = f"https://gsaauctions.gov/gsaauctions/gsaauctions/"
            
            # Use their search form
            search_params = {
                'option': 'com_vehicle',
                'view': 'searchresults',
                'zip': zip_code,
                'radius': '100',
                'category': 'vehicle',
                'subcategory': '',
                'sale_method': 'online',
                'Itemid': '29'
            }
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = self.safe_get(search_url, params=search_params, headers=headers)
            if not response:
                logger.debug(f"Could not fetch GSA search for zip {zip_code}")
                return lots
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for vehicle listings
            vehicle_items = soup.find_all(['div', 'tr', 'article'], class_=re.compile(r'auction|item|listing|vehicle', re.I))
            
            # Also try different selectors
            if not vehicle_items:
                vehicle_items = soup.find_all('div', attrs={'data-auction-id': True})
            if not vehicle_items:
                # Look for table rows with vehicle data
                vehicle_items = soup.find_all('tr')
            
            for item in vehicle_items[:10]:  # Limit per zip code
                lot_data = self._parse_gsa_vehicle(item, zip_code)
                if lot_data:
                    lots.append(lot_data)
            
            logger.debug(f"Found {len(lots)} GSA vehicles for zip {zip_code}")
            
        except Exception as e:
            logger.debug(f"Error searching GSA for zip {zip_code}: {e}")
        
        return lots
    
    def _parse_gsa_vehicle(self, item, zip_code: str) -> Dict[str, Any]:
        """Parse a GSA vehicle auction item."""
        try:
            text_content = item.get_text(strip=True)
            
            # Skip if too short or not vehicle-related
            if len(text_content) < 30:
                return None
            
            # Must contain vehicle keywords
            vehicle_keywords = ['vehicle', 'car', 'truck', 'van', 'suv', 'sedan', 'pickup']
            if not any(keyword in text_content.lower() for keyword in vehicle_keywords):
                return None
            
            # Extract auction ID and URL
            auction_link = item.find('a', href=True)
            if not auction_link:
                return None
            
            href = auction_link.get('href', '')
            
            # Extract auction ID from URL
            auction_id_match = re.search(r'auction[_-]?id[=:](\d+)', href, re.I)
            if not auction_id_match:
                auction_id_match = re.search(r'/(\d+)/?$', href)
            
            auction_id = auction_id_match.group(1) if auction_id_match else hash(text_content[:50]) % 100000
            
            # Build full URL
            lot_url = href
            if href.startswith('/'):
                lot_url = f"https://gsaauctions.gov{href}"
            elif not href.startswith('http'):
                lot_url = f"https://gsaauctions.gov/{href}"
            
            # Extract title
            title_elem = auction_link or item.find(['h1', 'h2', 'h3', 'h4', 'strong'])
            title = title_elem.get_text().strip() if title_elem else text_content[:100]
            
            # Try to extract vehicle details
            year, make, model, vin = None, None, None, None
            
            # Look for year make model patterns
            vehicle_patterns = [
                r'(\d{4})\s+(ford|chevrolet|chevy|gmc|dodge|toyota|nissan|honda)\s+([^,\n\-()]+)',
                r'(ford|chevrolet|chevy|gmc|dodge|toyota|nissan|honda)\s+([^,\n\-()]+)\s+(\d{4})',
                r'(explorer|f-150|f150|tahoe|suburban|equinox|malibu|impala|fusion|escape)',
            ]
            
            for pattern in vehicle_patterns:
                match = re.search(pattern, text_content, re.IGNORECASE)
                if match:
                    groups = match.groups()
                    if len(groups) >= 3:
                        if groups[0].isdigit():  # Year first
                            year = int(groups[0])
                            make = groups[1].strip().title()
                            model = groups[2].strip().title()
                        elif groups[2].isdigit():  # Year last
                            make = groups[0].strip().title()
                            model = groups[1].strip().title()
                            year = int(groups[2])
                    else:
                        # Model only pattern
                        model_name = groups[0].strip().title()
                        if 'explorer' in model_name.lower() or 'escape' in model_name.lower():
                            make = "Ford"
                        elif 'tahoe' in model_name.lower() or 'suburban' in model_name.lower():
                            make = "Chevrolet"
                        elif 'equinox' in model_name.lower() or 'malibu' in model_name.lower():
                            make = "Chevrolet"
                        model = model_name
                    break
            
            # Look for VIN
            vin_match = re.search(r'\b[A-HJ-NPR-Z0-9]{17}\b', text_content, re.IGNORECASE)
            vin = vin_match.group().upper() if vin_match else None
            
            # Extract auction end dates
            sale_date_utc, tz_name = None, "America/New_York"
            sale_local_time = "TBD"
            
            date_patterns = [
                r'end[s]?\s*:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
                r'closing\s*:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
                r'(\d{1,2}[/-]\d{1,2}[/-]\d{4})\s*[\s@]\s*(\d{1,2}:\d{2})',
                r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+(\d{1,2}),?\s*(\d{4})',
                r'(\d+)\s*day[s]?\s*left',
                r'(\d+)\s*hour[s]?\s*left'
            ]
            
            for pattern in date_patterns:
                date_match = re.search(pattern, text_content, re.I)
                if date_match:
                    try:
                        if 'day' in pattern or 'hour' in pattern:
                            # Handle relative time
                            if 'day' in pattern:
                                days = int(date_match.group(1))
                                end_date = datetime.now() + timedelta(days=days)
                            else:
                                hours = int(date_match.group(1))
                                end_date = datetime.now() + timedelta(hours=hours)
                            
                            sale_local_time = end_date.strftime("%m/%d/%Y %I:%M %p")
                            sale_date_utc, tz_name = normalize_timezone(sale_local_time, "America/New_York")
                        else:
                            # Handle absolute dates
                            date_str = date_match.group(0)
                            sale_date_utc, tz_name = normalize_timezone(date_str, "America/New_York")
                            sale_local_time = date_str
                        break
                    except Exception as e:
                        logger.debug(f"Could not parse date '{date_match.group()}': {e}")
                        continue
            
            # Create lot ID
            lot_id = f"gsa_{auction_id}"
            
            # Determine location - GSA auctions are nationwide but we searched by zip
            location_city = "Federal Lot"
            location_state = "Unknown"
            location_name = "GSA Federal Auction"
            
            # Try to extract location from text
            state_patterns = [
                r'\b(CT|MA|NY|NJ|RI|PA|VT|NH|ME)\b',
                r'(Connecticut|Massachusetts|New York|New Jersey|Rhode Island)',
                r'(Hartford|Boston|Albany|Newark|Providence)',
            ]
            
            for pattern in state_patterns:
                location_match = re.search(pattern, text_content, re.I)
                if location_match:
                    found_text = location_match.group().upper()
                    if len(found_text) == 2:  # State abbreviation
                        location_state = found_text
                    else:  # City or full state name
                        location_city = found_text.title()
                        if 'connecticut' in found_text.lower():
                            location_state = 'CT'
                        elif 'massachusetts' in found_text.lower() or 'boston' in found_text.lower():
                            location_state = 'MA'
                        elif 'new york' in found_text.lower() or 'albany' in found_text.lower():
                            location_state = 'NY'
                        elif 'new jersey' in found_text.lower() or 'newark' in found_text.lower():
                            location_state = 'NJ'
                        elif 'rhode island' in found_text.lower() or 'providence' in found_text.lower():
                            location_state = 'RI'
                    break
            
            lot_data = {
                'source': self.source_name,
                'source_lot_id': lot_id,
                'lot_url': lot_url,
                'sale_date_utc': sale_date_utc.isoformat() if sale_date_utc else None,
                'sale_local_time': sale_local_time,
                'tz_name': tz_name,
                'location_name': location_name,
                'location_city': location_city,
                'location_state': location_state,
                'year': year,
                'make': make,
                'model': model,
                'vin': vin,
                'title_status': 'clean',  # GSA vehicles typically have clean titles
                'condition_notes': f'GSA Federal Auction - {title}',
                'raw_text': text_content[:500]
            }
            
            # Enhance with VIN decoding if available
            if vin:
                lot_data = self.enhance_vehicle_data(lot_data)
            
            return lot_data
            
        except Exception as e:
            logger.debug(f"Error parsing GSA item: {e}")
            return None