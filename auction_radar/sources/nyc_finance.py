import logging
from typing import List, Dict, Any
from datetime import datetime, timedelta
import re
from bs4 import BeautifulSoup
from .base import BaseScraper
from ..utils import safe_get_text, normalize_timezone
from pdfminer.high_level import extract_text
from io import BytesIO
import json
import time

logger = logging.getLogger(__name__)

class NYCFinanceScraper(BaseScraper):
    """Scraper for NYC Finance Department vehicle auctions."""
    
    def __init__(self):
        super().__init__('nyc_finance', 'https://www.nyc.gov')
    
    def crawl(self) -> List[Dict[str, Any]]:
        """Crawl NYC Finance vehicle auction listings."""
        lots = []
        
        try:
            # Get the auction page
            auction_url = f"{self.base_url}/site/finance/vehicles/auctions.page"
            response = self.safe_get(auction_url)
            if not response:
                logger.warning("Could not fetch NYC Finance auction page")
                return lots
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for PDF links on the page
            pdf_links = self._find_pdf_links(soup)
            logger.info(f"Found {len(pdf_links)} PDF links")
            
            # Parse each PDF for vehicle details
            all_vehicles = []
            for pdf_url in pdf_links:
                pdf_lots = self._parse_pdf_auction(pdf_url)
                lots.extend(pdf_lots)
                # Collect all vehicles for batch VIN decoding
                for lot in pdf_lots:
                    if lot.get('vin'):
                        all_vehicles.append(lot)
            
            # Batch decode VINs for better performance
            if all_vehicles:
                logger.info(f"Batch decoding {len(all_vehicles)} VINs...")
                vin_results = self.decode_vins_batch(all_vehicles)
                
                # Update lots with batch decoded data
                for lot in lots:
                    vin = lot.get('vin')
                    if vin and vin in vin_results:
                        vin_data = vin_results[vin]
                        if vin_data.get('model') and not lot.get('model'):
                            lot['model'] = vin_data['model']
                        if vin_data.get('make'):
                            lot['make'] = vin_data['make']  # Use more accurate NHTSA make
                        
                        # Add VIN-decoded specs to condition notes
                        if lot.get('condition_notes') and vin_data:
                            specs = []
                            if vin_data.get('body_class'):
                                specs.append(f"Body: {vin_data['body_class']}")
                            if vin_data.get('fuel_type'):
                                specs.append(f"Fuel: {vin_data['fuel_type']}")
                            if vin_data.get('engine_cylinders'):
                                specs.append(f"Engine: {vin_data['engine_cylinders']} cyl")
                            
                            if specs:
                                lot['condition_notes'] += f". {', '.join(specs)}"
                        
                        # Update vehicle description
                        if lot.get('year') and lot.get('make'):
                            vehicle_desc = f"{lot['year']} {lot['make']}"
                            if lot.get('model'):
                                vehicle_desc += f" {lot['model']}"
                            if vin_data.get('trim'):
                                vehicle_desc += f" {vin_data['trim']}"
                            lot['raw_text'] = f"Lot #{lot.get('lot_number', '')}: {vehicle_desc} (VIN: {vin}, Plate: {lot.get('license_plate', '')})"
            
            # If no PDFs found, fall back to general auction info
            if not lots:
                lots = self._parse_auction_page(soup, auction_url)
        
        except Exception as e:
            logger.error(f"Error crawling NYC Finance: {e}")
        
        return lots
    
    def _parse_auction_page(self, soup: BeautifulSoup, page_url: str) -> List[Dict[str, Any]]:
        """Parse the main auction page."""
        lots = []
        
        # Extract auction dates and information from the page
        auction_info = self._extract_auction_info(soup)
        
        # Create lots based on found auction information
        for auction in auction_info:
            lot_data = self._create_auction_lot(auction, page_url)
            lots.append(lot_data)
        
        return lots
    
    def _extract_auction_info(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Extract auction information from the page."""
        auctions = []
        
        # Get all text and look for auction dates after "Upcoming Auction(s):"
        text = soup.get_text()
        lines = text.split('\n')
        
        in_auction_section = False
        for line in lines:
            line = line.strip()
            if 'Upcoming Auction(s):' in line:
                in_auction_section = True
                continue
            elif in_auction_section and line:
                # Look for date patterns like "September 4, 2025 - Bronx"
                date_match = re.match(r'(\w+\s+\d{1,2},\s+\d{4})\s*-\s*(.+)', line)
                if date_match:
                    date_str, location = date_match.groups()
                    # Clean up location names (remove numbers/suffixes like "2 - Queens")
                    location = re.sub(r'^\d+\s*-\s*', '', location.strip())
                    auctions.append({
                        'date': date_str.strip(),
                        'location': location.strip()
                    })
                elif line and not any(keyword in line.lower() for keyword in ['bidding', 'after', 'property']):
                    # Stop when we hit other sections
                    break
        
        logger.info(f"Found {len(auctions)} upcoming auctions")
        return auctions
    
    def _create_auction_lot(self, auction_info: Dict[str, str], page_url: str) -> Dict[str, Any]:
        """Create a lot entry for an NYC auction."""
        
        auction_date = auction_info['date']
        location = auction_info['location']
        
        # Parse auction date (NYC auctions typically start at 11:00 AM)
        sale_date_utc, tz_name = normalize_timezone(f"{auction_date} 11:00 AM", "America/New_York")
        
        # Create unique lot ID based on date and location
        lot_id = f"nyc_{auction_date.replace(' ', '_').replace(',', '')}_{location.lower().replace(' ', '_')}"
        
        lot_data = {
            'source': self.source_name,
            'source_lot_id': lot_id,
            'sale_date_utc': sale_date_utc.isoformat() if sale_date_utc else None,
            'sale_local_time': f"{auction_date} 11:00 AM",
            'tz_name': tz_name,
            'location_name': f'NYC Sheriff Vehicle Auction - {location}',
            'location_city': location,
            'location_state': 'NY',
            'lot_url': page_url,
            'condition_notes': 'Seized/abandoned vehicles sold as-is, no warranty',
            'title_status': 'unknown',
            'raw_text': f'NYC vehicle auction in {location}. Vehicles are seized or abandoned cars sold as-is. Must pay cash in full immediately after winning bid.',
            # These fields are unknown for general auction announcements
            'year': None,
            'make': None,
            'model': None,
            'vin': None
        }
        
        return lot_data
    
    def _find_pdf_links(self, soup: BeautifulSoup) -> List[str]:
        """Find PDF links on the auction page."""
        pdf_links = []
        
        # Look for links to PDF files
        for link in soup.find_all('a', href=True):
            href = link['href']
            if href.lower().endswith('.pdf') and 'auction' in href.lower():
                # Make absolute URL
                if href.startswith('/'):
                    pdf_url = f"{self.base_url}{href}"
                elif not href.startswith('http'):
                    pdf_url = f"{self.base_url}/{href}"
                else:
                    pdf_url = href
                pdf_links.append(pdf_url)
                logger.info(f"Found PDF: {pdf_url}")
        
        return pdf_links
    
    def _parse_pdf_auction(self, pdf_url: str) -> List[Dict[str, Any]]:
        """Parse a PDF auction document for vehicle details."""
        lots = []
        
        try:
            # Download PDF
            response = self.safe_get(pdf_url)
            if not response:
                logger.warning(f"Could not download PDF: {pdf_url}")
                return lots
            
            # Extract text from PDF
            pdf_text = extract_text(BytesIO(response.content))
            
            # Parse the PDF text for auction details
            lots = self._parse_pdf_text(pdf_text, pdf_url)
            
        except Exception as e:
            logger.error(f"Error parsing PDF {pdf_url}: {e}")
        
        return lots
    
    
    def _parse_pdf_text(self, text: str, pdf_url: str) -> List[Dict[str, Any]]:
        """Parse extracted PDF text for vehicle information."""
        lots = []
        
        try:
            # Extract auction date and location
            auction_info = self._extract_auction_details_from_pdf(text)
            
            # Extract vehicle table data
            vehicles = self._extract_vehicle_table(text)
            
            # Create lot entries for each vehicle
            for vehicle in vehicles:
                lot_data = self._create_vehicle_lot(vehicle, auction_info, pdf_url)
                lots.append(lot_data)
                
            logger.info(f"Extracted {len(lots)} vehicles from PDF")
            
        except Exception as e:
            logger.error(f"Error parsing PDF text: {e}")
        
        return lots
    
    def _extract_auction_details_from_pdf(self, text: str) -> Dict[str, Any]:
        """Extract auction date, time, and location from PDF text."""
        auction_info = {
            'date': None,
            'time': None,
            'location': None,
            'address': None
        }
        
        # Look for auction date and time pattern - handle multiline
        date_pattern = r'on (\w+day)\s+(\w+ \d{1,2}, \d{4})\s*\n?\s*at\s+([^\n]*)'
        date_match = re.search(date_pattern, text, re.MULTILINE)
        if date_match:
            _, date, time_location = date_match.groups()
            auction_info['date'] = date
            
            # Extract time - handle both "9:30" and "9:30 o'clock" formats
            time_match = re.search(r'(\d{1,2}):(\d{2})\s*(?:o\'?clock)?\s*(?:in\s+the\s+)?(morning|afternoon|evening)', time_location)
            if time_match:
                hour, minute, period = time_match.groups()
                hour = int(hour)
                if period == 'morning':
                    if hour == 12:
                        hour = 0
                    time_str = f"{hour}:{minute} AM"
                elif period == 'afternoon' or period == 'evening':
                    if hour != 12:
                        hour += 12
                    time_str = f"{hour}:{minute}"
                    if hour > 12:
                        time_str = f"{hour-12}:{minute} PM"
                    else:
                        time_str = f"{hour}:{minute} PM"
                else:
                    time_str = f"{hour}:{minute} AM"  # Default to AM
                auction_info['time'] = time_str
        
        # Look for location/address
        address_pattern = r'at ([A-Z][A-Z ]+(?:TOWING|INC|LLC)[^\n]*[\d]+ [^\n]+ NY [\d]+)'
        address_match = re.search(address_pattern, text)
        if address_match:
            address = address_match.group(1).strip()
            auction_info['address'] = address
            # Extract location name (first part before address)
            location_match = re.match(r'([A-Z][A-Z ]+(?:TOWING|INC|LLC))', address)
            if location_match:
                auction_info['location'] = location_match.group(1).strip()
        
        return auction_info
    
    def _extract_vehicle_table(self, text: str) -> List[Dict[str, Any]]:
        """Extract vehicle data from the PDF table."""
        vehicles = []
        
        # Split text into lines
        lines = text.split('\n')
        
        # Look for table data - lines that start with a number followed by year
        vehicle_pattern = r'^(\d+)\s+(\d{4})\s+(\w+)\s+([A-Z0-9]+)\s+([A-Z]{2})\s+([A-Z0-9]{17})(?:\s+(.+))?'
        
        for line in lines:
            line = line.strip()
            match = re.match(vehicle_pattern, line)
            if match:
                lot_num, year, make, plate, state, vin = match.groups()[:6]
                lienholder = match.group(7) if match.group(7) else None
                
                # Clean up make names
                make_mapping = {
                    'NISSA': 'NISSAN',
                    'CHEVR': 'CHEVROLET', 
                    'TOYOT': 'TOYOTA',
                    'VOLKS': 'VOLKSWAGEN',
                    'ME/BE': 'MERCEDES-BENZ',
                    'INFIN': 'INFINITI',
                    'CHRYSLER': 'CHRYSLER',
                    'PORSC': 'PORSCHE'
                }
                make = make_mapping.get(make, make)
                
                # Clean up lienholder
                if lienholder:
                    lienholder = lienholder.replace(';', ' ').strip()
                
                vehicle = {
                    'lot_number': int(lot_num),
                    'year': int(year),
                    'make': make,
                    'model': None,  # Model not provided in this format
                    'vin': vin,
                    'plate': plate,
                    'state': state,
                    'lienholder': lienholder
                }
                vehicles.append(vehicle)
        
        return vehicles
    
    def _create_vehicle_lot(self, vehicle: Dict[str, Any], auction_info: Dict[str, Any], pdf_url: str) -> Dict[str, Any]:
        """Create a lot entry for a specific vehicle."""
        
        # Use vehicle data as-is (VIN decoding will be done in batch)
        make = vehicle['make']
        model = vehicle.get('model', 'Unknown')
        
        # Build sale date/time
        if auction_info.get('date') and auction_info.get('time'):
            sale_datetime_str = f"{auction_info['date']} {auction_info['time']}"
        elif auction_info.get('date'):
            sale_datetime_str = f"{auction_info['date']} 9:30 AM"
        else:
            sale_datetime_str = None
        
        # Parse date/time
        sale_date_utc, tz_name = normalize_timezone(sale_datetime_str, "America/New_York") if sale_datetime_str else (None, None)
        
        # Create unique lot ID
        lot_id = f"nyc_{vehicle['vin']}_{vehicle['lot_number']}"
        
        # Determine location details
        location_name = auction_info.get('location', 'NYC Sheriff Vehicle Auction')
        location_city = 'Brooklyn'  # Default, could be parsed from address
        if auction_info.get('address'):
            if 'BROOKLYN' in auction_info['address'].upper():
                location_city = 'Brooklyn'
            elif 'QUEENS' in auction_info['address'].upper():
                location_city = 'Queens'
            elif 'BRONX' in auction_info['address'].upper():
                location_city = 'Bronx'
            elif 'STATEN' in auction_info['address'].upper():
                location_city = 'Staten Island'
        
        # Build basic condition notes (VIN details added in batch processing)
        condition_notes = 'Seized/abandoned vehicle sold as-is, no warranty'
        if vehicle.get('lienholder'):
            condition_notes += f'. Lienholder: {vehicle["lienholder"]}'
        
        # Build basic raw text (enhanced later in batch processing)
        vehicle_description = f"{vehicle['year']} {make}"
        if model and model != 'Unknown':
            vehicle_description += f" {model}"
        
        lot_data = {
            'source': self.source_name,
            'source_lot_id': lot_id,
            'sale_date_utc': sale_date_utc.isoformat() if sale_date_utc else None,
            'sale_local_time': sale_datetime_str,
            'tz_name': tz_name,
            'location_name': f'NYC Sheriff Vehicle Auction - {location_name}',
            'location_city': location_city,
            'location_state': 'NY',
            'lot_url': pdf_url,
            'condition_notes': condition_notes,
            'title_status': 'lienholder' if vehicle.get('lienholder') else 'unknown',
            'raw_text': f'Lot #{vehicle["lot_number"]}: {vehicle_description} (VIN: {vehicle["vin"]}, Plate: {vehicle["plate"]})',
            'year': vehicle['year'],
            'make': make,
            'model': model,
            'vin': vehicle['vin'],
            'lot_number': vehicle['lot_number'],
            'license_plate': vehicle['plate'],
            'license_state': vehicle['state']
        }
        
        return lot_data
    
