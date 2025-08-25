"""Keyword matching for target vehicles."""

import re
from typing import List, Dict, Set
from dataclasses import dataclass

@dataclass
class TargetMatch:
    """Represents a matched target vehicle."""
    category: str
    keywords: List[str]
    score: float

class KeywordMatcher:
    """Handles keyword matching for target vehicles."""
    
    def __init__(self):
        # Define target patterns with scores (higher = more desirable)
        self.patterns = {
            # Land Cruiser - highest priority
            'land_cruiser': {
                'regex': re.compile(r'\b(?:land\s*cruiser|landcruiser|lc\s*\d+|lc)\b', re.IGNORECASE),
                'score': 1.0,
                'keywords': ['land cruiser', 'landcruiser', 'lc']
            },
            
            # 4Runner - high priority
            'fourrunner': {
                'regex': re.compile(r'\b(?:4\s*runner|4runner|four\s*runner)\b', re.IGNORECASE),
                'score': 0.9,
                'keywords': ['4runner', 'four runner']
            },
            
            # Toyota trucks
            'tacoma': {
                'regex': re.compile(r'\btacoma\b', re.IGNORECASE),
                'score': 0.8,
                'keywords': ['tacoma']
            },
            'tundra': {
                'regex': re.compile(r'\btundra\b', re.IGNORECASE),
                'score': 0.8,
                'keywords': ['tundra']
            },
            
            # Nissan trucks
            'frontier': {
                'regex': re.compile(r'\bfrontier\b', re.IGNORECASE),
                'score': 0.7,
                'keywords': ['frontier']
            },
            'titan': {
                'regex': re.compile(r'\btitan\b', re.IGNORECASE),
                'score': 0.7,
                'keywords': ['titan']
            },
            
            # Campers and RVs
            'campers_rvs': {
                'regex': re.compile(
                    r'\b(?:camper|class\s*[bc]|sprinter|promaster|transit|'
                    r'teardrop|travel\s*trailer|tow\s*hitch|rv|motorhome|'
                    r'fifth\s*wheel|pop\s*up)\b', 
                    re.IGNORECASE
                ),
                'score': 0.6,
                'keywords': ['camper', 'class b', 'class c', 'sprinter', 'promaster', 
                           'transit', 'teardrop', 'travel trailer', 'rv', 'motorhome']
            }
        }
    
    def find_matches(self, text: str) -> List[TargetMatch]:
        """Find all keyword matches in the given text."""
        matches = []
        text_lower = text.lower()
        
        for category, pattern_info in self.patterns.items():
            if pattern_info['regex'].search(text):
                # Find actual matched keywords
                matched_keywords = []
                for keyword in pattern_info['keywords']:
                    if keyword.lower() in text_lower:
                        matched_keywords.append(keyword)
                
                matches.append(TargetMatch(
                    category=category,
                    keywords=matched_keywords or [category],
                    score=pattern_info['score']
                ))
        
        return matches
    
    def get_best_match(self, text: str) -> TargetMatch:
        """Get the highest scoring match for the text."""
        matches = self.find_matches(text)
        if not matches:
            return None
        return max(matches, key=lambda m: m.score)
    
    def has_target_match(self, text: str) -> bool:
        """Check if text contains any target keywords."""
        return bool(self.find_matches(text))

# Global keyword matcher instance
keyword_matcher = KeywordMatcher()