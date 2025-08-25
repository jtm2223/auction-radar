"""Data normalization for auction lots."""

import re
import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class LotNormalizer:
    """Normalizes lot data to common schema."""
    
    def __init__(self):
        # Common make/model mappings
        self.make_mappings = {
            'toyota': 'Toyota',
            'lexus': 'Lexus',
            'nissan': 'Nissan',
            'ford': 'Ford',
            'chevrolet': 'Chevrolet',
            'chevy': 'Chevrolet',
            'gmc': 'GMC',
            'honda': 'Honda',
            'acura': 'Acura',
        }
        
        # Title status normalization
        self.title_patterns = {
            'clean': re.compile(r'\b(?:clean|clear|good)\b', re.IGNORECASE),
            'rebuilt': re.compile(r'\b(?:rebuilt|reconstructed|repaired)\b', re.IGNORECASE),
            'salvage': re.compile(r'\b(?:salvage|salvaged|total|totaled)\b', re.IGNORECASE),
            'parts_only': re.compile(r'\b(?:parts\s*only|scrap|junk|non\s*runner)\b', re.IGNORECASE),
        }
        
        # VIN pattern
        self.vin_pattern = re.compile(r'\b[A-HJ-NPR-Z0-9]{17}\b', re.IGNORECASE)
        
        # Year pattern
        self.year_pattern = re.compile(r'\b(19|20)\d{2}\b')
    
    def normalize_lot(self, raw_lot: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a raw lot dictionary to standard schema."""
        normalized = {
            # Required fields
            'source': raw_lot.get('source', '').strip(),
            'source_lot_id': str(raw_lot.get('source_lot_id', '')).strip(),
            'lot_url': raw_lot.get('lot_url', '').strip(),
            
            # Date/time fields
            'sale_date_utc': self._normalize_datetime(raw_lot.get('sale_date_utc')),
            'sale_local_time': raw_lot.get('sale_local_time', '').strip(),
            'tz_name': raw_lot.get('tz_name', 'America/New_York'),
            
            # Location fields
            'location_name': raw_lot.get('location_name', '').strip(),
            'location_city': raw_lot.get('location_city', '').strip(),
            'location_state': raw_lot.get('location_state', '').strip(),
            
            # Vehicle fields
            'vin': self._normalize_vin(raw_lot.get('vin', '').strip()),
            'year': self._normalize_year(raw_lot.get('year')),
            'make': self._normalize_make(raw_lot.get('make', '').strip()),
            'model': self._normalize_model(raw_lot.get('model', '').strip()),
            'trim': raw_lot.get('trim', '').strip(),
            'drivetrain': raw_lot.get('drivetrain', '').strip(),
            'odometer': self._normalize_odometer(raw_lot.get('odometer')),
            'title_status': self._normalize_title_status(raw_lot.get('title_status', ''), raw_lot.get('raw_text', '')),
            'condition_notes': raw_lot.get('condition_notes', '').strip(),
            
            # Raw data
            'raw_text': raw_lot.get('raw_text', '').strip(),
        }
        
        # Auto-extract missing fields from raw text if available
        if raw_lot.get('raw_text'):
            normalized = self._extract_from_raw_text(normalized, raw_lot['raw_text'])
        
        return normalized
    
    def _normalize_datetime(self, dt_value: Any) -> Optional[str]:
        """Normalize datetime to ISO format."""
        if not dt_value:
            return None
        
        if isinstance(dt_value, datetime):
            return dt_value.isoformat()
        
        if isinstance(dt_value, str):
            try:
                from dateutil import parser
                parsed_dt = parser.parse(dt_value)
                return parsed_dt.isoformat()
            except:
                return None
        
        return None
    
    def _normalize_vin(self, vin: str) -> str:
        """Normalize VIN format."""
        if not vin:
            return ''
        
        vin = re.sub(r'[^A-HJ-NPR-Z0-9]', '', vin.upper())
        return vin if len(vin) == 17 else ''
    
    def _normalize_year(self, year: Any) -> Optional[int]:
        """Normalize year to integer."""
        if isinstance(year, int) and 1900 <= year <= 2030:
            return year
        
        if isinstance(year, str):
            try:
                year_int = int(re.sub(r'[^\d]', '', year))
                return year_int if 1900 <= year_int <= 2030 else None
            except:
                pass
        
        return None
    
    def _normalize_make(self, make: str) -> str:
        """Normalize vehicle make."""
        if not make:
            return ''
        
        make_lower = make.lower().strip()
        return self.make_mappings.get(make_lower, make.title())
    
    def _normalize_model(self, model: str) -> str:
        """Normalize vehicle model."""
        if not model:
            return ''
        
        # Common model normalizations
        model = model.strip()
        model = re.sub(r'\s+', ' ', model)  # Normalize whitespace
        return model.title()
    
    def _normalize_odometer(self, odometer: Any) -> Optional[int]:
        """Normalize odometer reading."""
        if isinstance(odometer, int) and 0 <= odometer <= 1000000:
            return odometer
        
        if isinstance(odometer, str):
            # Extract numbers from string
            numbers = re.findall(r'\d+', odometer)
            if numbers:
                try:
                    odo = int(numbers[0])
                    return odo if 0 <= odo <= 1000000 else None
                except:
                    pass
        
        return None
    
    def _normalize_title_status(self, title_status: str, raw_text: str) -> str:
        """Normalize title status."""
        search_text = f"{title_status} {raw_text}".lower()
        
        for status, pattern in self.title_patterns.items():
            if pattern.search(search_text):
                return status
        
        return 'unknown'
    
    def _extract_from_raw_text(self, lot: Dict[str, Any], raw_text: str) -> Dict[str, Any]:
        """Extract missing fields from raw text."""
        
        # Extract VIN if missing
        if not lot.get('vin'):
            vin_match = self.vin_pattern.search(raw_text)
            if vin_match:
                lot['vin'] = vin_match.group()
        
        # Extract year if missing
        if not lot.get('year'):
            year_matches = self.year_pattern.findall(raw_text)
            if year_matches:
                try:
                    lot['year'] = int(year_matches[-1])  # Take the last year found
                except:
                    pass
        
        # Extract make/model if missing
        if not lot.get('make') or not lot.get('model'):
            make, model = self._extract_make_model(raw_text)
            if make and not lot.get('make'):
                lot['make'] = make
            if model and not lot.get('model'):
                lot['model'] = model
        
        return lot
    
    def _extract_make_model(self, text: str) -> tuple[Optional[str], Optional[str]]:
        """Extract make and model from text."""
        text_lower = text.lower()
        
        # Common patterns
        patterns = [
            r'\b(toyota|lexus|nissan|ford|chevrolet|chevy|gmc|honda|acura)\s+([a-z0-9\-\s]+)',
            r'\b(\d{4})\s+(toyota|lexus|nissan|ford|chevrolet|chevy|gmc|honda|acura)\s+([a-z0-9\-\s]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text_lower)
            if match:
                groups = match.groups()
                if len(groups) >= 2:
                    # Check if first group is a year
                    if groups[0].isdigit():
                        make = groups[1] if len(groups) > 1 else None
                        model = groups[2] if len(groups) > 2 else None
                    else:
                        make = groups[0]
                        model = groups[1] if len(groups) > 1 else None
                    
                    if make:
                        make = self._normalize_make(make)
                    if model:
                        model = model.split()[0].title()  # Take first word
                    
                    return make, model
        
        return None, None

# Global normalizer instance
lot_normalizer = LotNormalizer()