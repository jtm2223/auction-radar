import logging
import requests
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from urllib.robotparser import RobotFileParser
import time
import json
from ..config import config
from ..utils import create_session, retry_with_backoff

logger = logging.getLogger(__name__)

class BaseScraper(ABC):
    """Base class for auction source scrapers."""
    
    def __init__(self, source_name: str, base_url: str):
        self.source_name = source_name
        self.base_url = base_url
        self.session = create_session(config.USER_AGENT, config.REQUEST_DELAY)
    
    def get_headers(self) -> Dict[str, str]:
        """Get standard headers for requests."""
        return {
            'User-Agent': config.USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
    @abstractmethod
    def crawl(self) -> List[Dict[str, Any]]:
        """
        Crawl the source and return list of lot dictionaries.
        
        Each dict must contain:
        - source: str
        - source_lot_id: str
        - lot_url: str (optional)
        - sale_local_time or sale_date_utc: str
        - location_city: str
        - location_state: str
        - raw_text: str
        
        Optional fields:
        - vin, year, make, model, title_status, condition_notes, etc.
        """
        pass
    
    def check_robots_txt(self, url: str) -> bool:
        """Check if URL is allowed by robots.txt."""
        if not config.RESPECT_ROBOTS:
            return True
        
        try:
            import socket
            socket.setdefaulttimeout(10)  # 10 second timeout
            rp = RobotFileParser()
            rp.set_url(f"{self.base_url}/robots.txt")
            rp.read()
            return rp.can_fetch(config.USER_AGENT, url)
        except Exception as e:
            logger.warning(f"Could not check robots.txt for {url}: {e}")
            return True  # Allow if robots.txt check fails
    
    @retry_with_backoff(max_retries=3)
    def safe_get(self, url: str, **kwargs) -> Optional[requests.Response]:
        """Safely get a URL with retries and robots.txt checking."""
        # Set default timeout if not provided
        kwargs.setdefault('timeout', 15)
        
        if not self.check_robots_txt(url):
            logger.warning(f"URL blocked by robots.txt: {url}")
            return None
        
        try:
            response = self.session.get(url, **kwargs)
            response.raise_for_status()
            return response
        except requests.exceptions.Timeout:
            logger.error(f"Timeout fetching {url}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed for {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching {url}: {e}")
            return None
    
    def extract_common_fields(self, text: str, lot_url: str = None) -> Dict[str, Any]:
        """Extract common fields from text."""
        import re
        from datetime import datetime
        
        # Extract year
        year_match = re.search(r'\b(19|20)\d{2}\b', text)
        year = int(year_match.group()) if year_match else None
        
        # Extract VIN
        vin_match = re.search(r'\b[A-HJ-NPR-Z0-9]{17}\b', text, re.IGNORECASE)
        vin = vin_match.group().upper() if vin_match else ''
        
        # Extract make/model (common patterns)
        make_model_match = re.search(
            r'\b(Toyota|Lexus|Nissan|Ford|Chevrolet|Chevy|GMC|Honda|Acura)\s+([A-Za-z0-9\-\s]+)',
            text, re.IGNORECASE
        )
        
        make = make_model_match.group(1).title() if make_model_match else ''
        model = make_model_match.group(2).strip().title() if make_model_match else ''
        
        return {
            'lot_url': lot_url or '',
            'year': year,
            'vin': vin,
            'make': make,
            'model': model,
            'raw_text': text.strip(),
            'created_at': datetime.utcnow().isoformat(),
        }
    
    # VIN decoding cache to avoid repeated API calls
    _vin_cache = {}
    
    def decode_vins_batch(self, vin_data_list: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Batch decode VINs using NHTSA API (up to 50 VINs per batch)."""
        if not vin_data_list:
            return {}
        
        # Filter out VINs that don't need decoding or are already cached
        vins_to_decode = []
        results = {}
        
        for item in vin_data_list:
            vin = item.get('vin', '')
            if not vin or len(vin) != 17:
                continue
                
            # Check cache first
            if vin in self._vin_cache:
                results[vin] = self._vin_cache[vin]
                continue
            
            # Only decode if model is missing or unknown
            current_model = item.get('model')
            if current_model is not None:
                model_str = str(current_model).strip().lower()
                if model_str and model_str not in ['unknown', 'none', '', 'null']:
                    results[vin] = {}  # Already have model, no need to decode
                    continue
                
            vins_to_decode.append(item)
        
        if not vins_to_decode:
            return results
        
        # Process in batches of 50 (NHTSA API limit)
        batch_size = 50
        for i in range(0, len(vins_to_decode), batch_size):
            batch = vins_to_decode[i:i + batch_size]
            batch_results = self._decode_vin_batch(batch)
            results.update(batch_results)
        
        return results
    
    def _decode_vin_batch(self, vin_batch: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Decode a batch of VINs using NHTSA batch API."""
        try:
            # Prepare batch data: "VIN,ModelYear;VIN,ModelYear;..."
            batch_data = []
            for item in vin_batch:
                vin = item['vin']
                year = item.get('year', '')
                batch_data.append(f"{vin},{year}" if year else vin)
            
            post_data = ';'.join(batch_data)
            
            # Use batch API endpoint
            api_url = "https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVINValuesBatch/"
            
            response = self.session.post(
                api_url,
                data={'format': 'json', 'data': post_data},
                timeout=30,
                headers=self.get_headers()
            )
            response.raise_for_status()
            
            data = response.json()
            results = {}
            
            # Process batch results
            for result in data.get('Results', []):
                vin = result.get('VIN', '').strip()
                if not vin:
                    continue
                
                # Extract relevant fields
                decoded_info = {}
                fields_map = {
                    'Make': 'make',
                    'Model': 'model', 
                    'Series': 'series',
                    'Trim': 'trim',
                    'Body Class': 'body_class',
                    'Vehicle Type': 'vehicle_type',
                    'Engine Number of Cylinders': 'engine_cylinders',
                    'Fuel Type - Primary': 'fuel_type',
                    'Transmission Style': 'transmission'
                }
                
                for nhtsa_field, our_field in fields_map.items():
                    value = result.get(nhtsa_field, '').strip()
                    if value and value.lower() not in ['not applicable', '', 'null', 'not available', 'n/a']:
                        decoded_info[our_field] = value
                
                results[vin] = decoded_info
                # Cache the result
                self._vin_cache[vin] = decoded_info
            
            logger.info(f"Successfully batch decoded {len(results)} VINs")
            return results
            
        except Exception as e:
            logger.warning(f"Error in batch VIN decoding: {e}")
            return {}
    
    def decode_vin(self, vin: str, year: int = None) -> Dict[str, Any]:
        """Decode single VIN - now just calls batch method for consistency."""
        if not vin or len(vin) != 17:
            return {}
        
        # Check cache first
        if vin in self._vin_cache:
            return self._vin_cache[vin]
        
        # Use batch method with single VIN
        batch_result = self.decode_vins_batch([{'vin': vin, 'year': year}])
        return batch_result.get(vin, {})
    
    def enhance_vehicle_data(self, vehicle_data: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance vehicle data with VIN decoding if VIN is available."""
        if not vehicle_data.get('vin'):
            return vehicle_data
        
        # Get VIN decoded data
        vin_data = self.decode_vin(vehicle_data['vin'], vehicle_data.get('year'))
        
        # Create enhanced copy
        enhanced = vehicle_data.copy()
        
        # Use VIN data when available, keeping original as fallback
        if vin_data.get('make') and not enhanced.get('make'):
            enhanced['make'] = vin_data['make']
        if vin_data.get('model') and not enhanced.get('model'):
            enhanced['model'] = vin_data['model']
        
        # Add additional VIN-decoded fields
        for field in ['series', 'body_class', 'vehicle_type', 'engine_cylinders', 'fuel_type', 'transmission', 'trim']:
            if vin_data.get(field):
                enhanced[f'vin_{field}'] = vin_data[field]
        
        # Enhance descriptions with VIN data
        if enhanced.get('year') and enhanced.get('make'):
            vehicle_desc = f"{enhanced['year']} {enhanced['make']}"
            if enhanced.get('model'):
                vehicle_desc += f" {enhanced['model']}"
            if vin_data.get('trim'):
                vehicle_desc += f" {vin_data['trim']}"
            enhanced['vehicle_description'] = vehicle_desc
        
        # Add VIN specs to condition notes if they exist
        if enhanced.get('condition_notes') and vin_data:
            specs = []
            if vin_data.get('body_class'):
                specs.append(f"Body: {vin_data['body_class']}")
            if vin_data.get('fuel_type'):
                specs.append(f"Fuel: {vin_data['fuel_type']}")
            if vin_data.get('engine_cylinders'):
                specs.append(f"Engine: {vin_data['engine_cylinders']} cyl")
            
            if specs:
                enhanced['condition_notes'] += f". {', '.join(specs)}"
        
        return enhanced