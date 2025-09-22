"""Target vehicle filtering for high-value Northeast auctions."""

import re
from typing import Dict, List, Any, Optional

class TargetVehicleFilter:
    """Filter for target vehicles we actually want to buy."""
    
    # Primary target vehicles - high resale value, reliable
    TARGET_VEHICLES = {
        'toyota_4runner': {
            'make': ['toyota'],
            'model': ['4runner', '4-runner', 'fourrunner'],
            'keywords': ['4runner', '4-runner', 'four runner'],
            'priority': 10
        },
        'toyota_land_cruiser': {
            'make': ['toyota'],
            'model': ['land cruiser', 'landcruiser', 'lc', 'land-cruiser'],
            'keywords': ['land cruiser', 'landcruiser', 'land-cruiser'],
            'priority': 10
        },
        'lexus_lx': {
            'make': ['lexus'],
            'model': ['lx', 'lx470', 'lx570', 'lx600'],
            'keywords': ['lx470', 'lx570', 'lx600', 'lx 470', 'lx 570', 'lx 600'],
            'priority': 9
        },
        'toyota_tacoma': {
            'make': ['toyota'],
            'model': ['tacoma'],
            'keywords': ['tacoma'],
            'priority': 8
        },
        'toyota_tundra': {
            'make': ['toyota'],
            'model': ['tundra'],
            'keywords': ['tundra'],
            'priority': 7
        },
        'nissan_frontier': {
            'make': ['nissan'],
            'model': ['frontier'],
            'keywords': ['frontier'],
            'priority': 6
        },
        'recreational_vehicles': {
            'make': ['*'],
            'model': ['*'],
            'keywords': ['camper', 'rv', 'motorhome', 'travel trailer', 'fifth wheel', 'toy hauler'],
            'priority': 5
        }
    }
    
    # States we actually operate in
    TARGET_STATES = ['CT', 'NY', 'NJ', 'RI', 'MA']
    
    def is_target_vehicle(self, lot_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Check if lot matches our target criteria and return match info."""
        
        # Quick state filter
        state = lot_data.get('location_state', '').upper()
        if state not in self.TARGET_STATES:
            return None
        
        # Get searchable text
        make = (lot_data.get('make') or '').lower()
        model = (lot_data.get('model') or '').lower()
        raw_text = (lot_data.get('raw_text') or '').lower()
        condition_notes = (lot_data.get('condition_notes') or '').lower()
        
        search_text = f"{make} {model} {raw_text} {condition_notes}"
        
        # Check each target vehicle type
        for vehicle_type, criteria in self.TARGET_VEHICLES.items():
            match_info = self._check_vehicle_match(lot_data, search_text, vehicle_type, criteria)
            if match_info:
                return match_info
        
        return None
    
    def _check_vehicle_match(self, lot_data: Dict[str, Any], search_text: str, 
                           vehicle_type: str, criteria: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Check if lot matches specific vehicle criteria."""
        
        make = (lot_data.get('make') or '').lower()
        model = (lot_data.get('model') or '').lower()
        year = lot_data.get('year')
        
        # Check make (unless wildcard)
        if criteria['make'] != ['*']:
            if not any(target_make in make for target_make in criteria['make']):
                return None
        
        # Check model (unless wildcard)
        if criteria['model'] != ['*']:
            model_match = any(target_model in model for target_model in criteria['model'])
            if not model_match:
                # Also check in search text for model keywords
                model_match = any(keyword in search_text for keyword in criteria.get('keywords', []))
            if not model_match:
                return None
        
        # Check keywords
        keyword_match = any(keyword in search_text for keyword in criteria.get('keywords', []))
        if not keyword_match:
            return None
        
        # Check required keywords (like 4x4 for trucks) - REMOVED RESTRICTION
        # required_keywords = criteria.get('required_keywords', [])
        # if required_keywords:
        #     has_required = any(req_keyword in search_text for req_keyword in required_keywords)
        #     if not has_required:
        #         return None

        # Check minimum year - REMOVED RESTRICTION
        # min_year = criteria.get('min_year', 2000)
        # if year and year < min_year:
        #     return None
        
        # Calculate match score
        priority = criteria.get('priority', 1)
        year_bonus = max(0, (year or 2010) - 2010) * 0.1 if year else 0
        match_score = priority + year_bonus
        
        return {
            'vehicle_type': vehicle_type,
            'priority': priority,
            'match_score': match_score,
            'match_reason': f"{vehicle_type.replace('_', ' ').title()}",
            'is_target': True
        }
    
    def filter_target_lots(self, lots: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter lots to only target vehicles and add match info."""
        target_lots = []
        
        for lot in lots:
            match_info = self.is_target_vehicle(lot)
            if match_info:
                # Add match info to lot
                lot.update(match_info)
                target_lots.append(lot)
        
        # Sort by match score (highest first)
        target_lots.sort(key=lambda x: x.get('match_score', 0), reverse=True)
        
        return target_lots
    
    def get_summary_stats(self, lots: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Get summary statistics for target matches."""
        if not lots:
            return {'total': 0, 'by_type': {}, 'by_state': {}}
        
        by_type = {}
        by_state = {}
        
        for lot in lots:
            # Count by vehicle type
            vehicle_type = lot.get('vehicle_type', 'unknown')
            by_type[vehicle_type] = by_type.get(vehicle_type, 0) + 1
            
            # Count by state
            state = lot.get('location_state', 'unknown')
            by_state[state] = by_state.get(state, 0) + 1
        
        return {
            'total': len(lots),
            'by_type': by_type,
            'by_state': by_state
        }

# Global instance
target_filter = TargetVehicleFilter()