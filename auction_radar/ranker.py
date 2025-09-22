"""Ranking and scoring system for auction lots."""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from .keywords import keyword_matcher, TargetMatch

logger = logging.getLogger(__name__)

class LotRanker:
    """Ranks and scores auction lots based on desirability."""
    
    def __init__(self):
        # Title status penalties (0 = no penalty, 1 = maximum penalty)
        self.title_penalties = {
            'clean': 0.0,
            'rebuilt': 0.05,
            'salvage': 0.2,
            'parts_only': 0.6,
            'unknown': 0.1
        }
        
        # Age penalties (newer is better)
        self.age_penalty_per_year = 0.01  # 1% penalty per year
        self.max_age_penalty = 0.3  # Max 30% penalty for age
    
    def score_lot(self, lot: Dict[str, Any]) -> float:
        """Calculate desirability score for a lot (0-1, higher is better)."""
        
        # Start with base score from keyword matching
        base_score = self._get_keyword_score(lot)
        if base_score == 0:
            return 0  # Not a target vehicle
        
        # Apply penalties
        title_penalty = self._get_title_penalty(lot.get('title_status', 'unknown'))
        age_penalty = self._get_age_penalty(lot.get('year'))
        
        # Calculate final score
        final_score = base_score * (1 - title_penalty) * (1 - age_penalty)
        
        # Ensure score stays in valid range
        return max(0, min(1, final_score))
    
    def _get_keyword_score(self, lot: Dict[str, Any]) -> float:
        """Get base score from keyword matching."""
        search_text = f"{lot.get('make', '')} {lot.get('model', '')} {lot.get('raw_text', '')}"
        
        best_match = keyword_matcher.get_best_match(search_text)
        return best_match.score if best_match else 0
    
    def _get_title_penalty(self, title_status: str) -> float:
        """Get penalty based on title status."""
        return self.title_penalties.get(title_status, 0.1)
    
    def _get_age_penalty(self, year: Optional[int]) -> float:
        """Get penalty based on vehicle age."""
        if not year:
            return 0.1  # Small penalty for unknown year
        
        current_year = datetime.now().year
        age = current_year - year
        
        if age <= 0:
            return 0  # No penalty for current/future year
        
        age_penalty = min(age * self.age_penalty_per_year, self.max_age_penalty)
        return age_penalty
    
    def rank_lots(self, lots: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Rank lots by desirability score and deduplicate by VIN."""
        
        # Calculate scores for all lots
        scored_lots = []
        for lot in lots:
            score = self.score_lot(lot)
            if score > 0:  # Only include target vehicles
                lot_copy = lot.copy()
                lot_copy['score'] = score
                scored_lots.append(lot_copy)
        
        # Deduplicate by VIN (keep highest scoring)
        deduped_lots = self._deduplicate_by_vin(scored_lots)
        
        # Sort by score (highest first)
        deduped_lots.sort(key=lambda x: x['score'], reverse=True)
        
        return deduped_lots
    
    def _deduplicate_by_vin(self, lots: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deduplicate lots by VIN, keeping the highest scoring one."""
        vin_to_lot = {}
        
        for lot in lots:
            vin = lot.get('vin')
            if not vin:
                # No VIN, keep all
                continue
            
            if vin not in vin_to_lot or lot['score'] > vin_to_lot[vin]['score']:
                vin_to_lot[vin] = lot
        
        # Combine VIN-deduplicated lots with no-VIN lots
        result = list(vin_to_lot.values())
        result.extend([lot for lot in lots if not lot.get('vin')])
        
        return result

# Global ranker instance
lot_ranker = LotRanker()