"""Tests for keyword matching."""

import pytest
from auction_radar.keywords import keyword_matcher, TargetMatch

class TestKeywordMatcher:
    """Test keyword matching functionality."""
    
    def test_land_cruiser_matches(self):
        """Test Land Cruiser keyword matching."""
        test_cases = [
            "2018 Toyota Land Cruiser Heritage Edition",
            "LEXUS LANDCRUISER 200 SERIES",
            "Toyota LC 76 series",
            "2020 Land-Cruiser GXL"
        ]
        
        for text in test_cases:
            matches = keyword_matcher.find_matches(text)
            assert len(matches) > 0, f"Should match: {text}"
            assert any(m.category == 'land_cruiser' for m in matches), f"Should be Land Cruiser: {text}"
    
    def test_fourrunner_matches(self):
        """Test 4Runner keyword matching."""
        test_cases = [
            "2019 Toyota 4Runner TRD Pro",
            "Toyota 4-Runner SR5",
            "TOYOTA FOURRUNNER LIMITED"
        ]
        
        for text in test_cases:
            matches = keyword_matcher.find_matches(text)
            assert len(matches) > 0, f"Should match: {text}"
            assert any(m.category == 'fourrunner' for m in matches), f"Should be 4Runner: {text}"
    
    def test_truck_matches(self):
        """Test truck keyword matching."""
        truck_tests = [
            ("2020 Toyota Tacoma TRD", 'tacoma'),
            ("Toyota Tundra CrewMax", 'tundra'),
            ("Nissan Frontier King Cab", 'frontier'),
            ("2018 Nissan Titan XD", 'titan')
        ]
        
        for text, expected_category in truck_tests:
            matches = keyword_matcher.find_matches(text)
            assert len(matches) > 0, f"Should match: {text}"
            assert any(m.category == expected_category for m in matches), f"Should be {expected_category}: {text}"
    
    def test_camper_rv_matches(self):
        """Test camper/RV keyword matching."""
        test_cases = [
            "2019 Winnebago Travato Class B",
            "Ford Transit Camper Conversion",
            "Mercedes Sprinter RV",
            "Travel Trailer 20ft",
            "Teardrop camper with tow hitch"
        ]
        
        for text in test_cases:
            matches = keyword_matcher.find_matches(text)
            assert len(matches) > 0, f"Should match: {text}"
            assert any(m.category == 'campers_rvs' for m in matches), f"Should be camper/RV: {text}"
    
    def test_no_matches(self):
        """Test that non-target vehicles don't match."""
        test_cases = [
            "2020 Honda Civic EX",
            "Ford F-150 SuperCrew",
            "Chevrolet Silverado 1500",
            "BMW X5 xDrive35i",
            "Audi Q7 Premium Plus"
        ]
        
        for text in test_cases:
            matches = keyword_matcher.find_matches(text)
            assert len(matches) == 0, f"Should not match: {text}"
    
    def test_get_best_match(self):
        """Test getting the best match for a text."""
        # Land Cruiser should score highest
        text = "2018 Toyota Land Cruiser vs 4Runner comparison"
        best_match = keyword_matcher.get_best_match(text)
        assert best_match is not None
        assert best_match.category == 'land_cruiser'
        
        # 4Runner should be best when Land Cruiser not present
        text = "2020 Toyota 4Runner TRD Pro"
        best_match = keyword_matcher.get_best_match(text)
        assert best_match is not None
        assert best_match.category == 'fourrunner'
    
    def test_has_target_match(self):
        """Test simple target matching check."""
        assert keyword_matcher.has_target_match("2018 Toyota Tacoma")
        assert keyword_matcher.has_target_match("Land Cruiser for sale")
        assert keyword_matcher.has_target_match("Class B RV Sprinter")
        assert not keyword_matcher.has_target_match("Honda Accord sedan")
        assert not keyword_matcher.has_target_match("Random text with no vehicles")