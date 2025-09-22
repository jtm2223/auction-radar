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
        # Define target patterns - ONLY vehicles you specifically want
        self.patterns = {
            # Lexus/Toyota Land Cruiser - HIGHEST PRIORITY
            'land_cruiser': {
                'regex': re.compile(r'\b(?:(?:lexus|toyota).*(?:land\s*cruiser|landcruiser)|land\s*cruiser|landcruiser|lx\s*\d+|lx570|lx470|lx450|lc\s*\d+|lc200|lc100|lc80)\b', re.IGNORECASE),
                'score': 1.0,
                'keywords': ['land cruiser', 'landcruiser', 'lexus lx', 'lx570', 'lx470', 'lc200', 'lc100', 'lc80']
            },
            
            # 4Runner - SECOND HIGHEST PRIORITY
            'fourrunner': {
                'regex': re.compile(r'\b(?:4[\s\-]*runner|four[\s\-]*runner)\b', re.IGNORECASE),
                'score': 0.95,
                'keywords': ['4runner', 'four runner', '4 runner', '4-runner']
            },
            
            # Toyota Trucks (ANY drivetrain)
            'toyota_trucks': {
                'regex': re.compile(r'\b(?:toyota.*(?:tacoma|tundra|t100|pickup)|(?:tacoma|tundra|t100))\b', re.IGNORECASE),
                'score': 0.9,
                'keywords': ['tacoma', 'tundra', 'toyota pickup', 't100']
            },

            # Nissan Trucks (ANY drivetrain)
            'nissan_trucks': {
                'regex': re.compile(r'\b(?:nissan.*(?:frontier|titan|navara|hardbody|pickup)|(?:frontier|titan|navara|hardbody))\b', re.IGNORECASE),
                'score': 0.85,
                'keywords': ['frontier', 'titan', 'nissan pickup', 'navara', 'hardbody']
            },
            
            # Mini Campers with Motor (Class B/Small RVs) - NOT expanded
            'mini_campers_motor': {
                'regex': re.compile(r'\b(?:(?:class\s*b|mini\s*motor\s*home|small\s*rv|conversion\s*van|roadtrek|pleasure\s*way|leisure\s*travel\s*van|great\s*west\s*van)(?!\s*(?:expand|slide|out)))\b', re.IGNORECASE),
                'score': 0.8,
                'keywords': ['class b', 'mini motorhome', 'conversion van', 'roadtrek', 'pleasure way']
            },
            
            # Towable Mini Campers (Small Travel Trailers) - NOT expanded
            'mini_campers_tow': {
                'regex': re.compile(r'\b(?:(?:teardrop|small\s*travel\s*trailer|mini\s*trailer|compact\s*trailer|pop\s*up|casita|scamp|t@b|tab|little\s*guy|rpod|r\s*pod)(?!\s*(?:expand|slide|out)))\b', re.IGNORECASE),
                'score': 0.75,
                'keywords': ['teardrop', 'small travel trailer', 'pop up', 'casita', 'scamp', 'little guy', 'rpod']
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