"""Tests for data normalization."""

import pytest
from datetime import datetime
from auction_radar.normalize import lot_normalizer

class TestLotNormalizer:
    """Test lot normalization functionality."""
    
    def test_basic_normalization(self):
        """Test basic lot normalization."""
        raw_lot = {
            'source': 'test_source',
            'source_lot_id': '123',
            'make': 'toyota',
            'model': 'tacoma',
            'year': '2018',
            'vin': 'ABCD123EFGH456789',
            'title_status': 'clean',
        }
        
        normalized = lot_normalizer.normalize_lot(raw_lot)
        
        assert normalized['source'] == 'test_source'
        assert normalized['source_lot_id'] == '123'
        assert normalized['make'] == 'Toyota'
        assert normalized['model'] == 'Tacoma'
        assert normalized['year'] == 2018
        assert normalized['vin'] == 'ABCD123EFGH456789'
        assert normalized['title_status'] == 'clean'
    
    def test_vin_normalization(self):
        """Test VIN normalization."""
        test_cases = [
            ('1ABCD23EFGH456789', '1ABCD23EFGH456789'),  # Valid VIN
            ('1abcd23efgh456789', '1ABCD23EFGH456789'),  # Lowercase
            ('1-ABCD-23-EFGH-456789', '1ABCD23EFGH456789'),  # With dashes
            ('1ABCD23EFGH45678', ''),  # Too short
            ('1ABCD23EFGH4567890', ''),  # Too long
            ('1ABCD23EFGH45678I', ''),  # Contains invalid character I
        ]
        
        for input_vin, expected in test_cases:
            normalized = lot_normalizer._normalize_vin(input_vin)
            assert normalized == expected, f"VIN {input_vin} should normalize to {expected}, got {normalized}"
    
    def test_year_normalization(self):
        """Test year normalization."""
        test_cases = [
            (2018, 2018),
            ('2018', 2018),
            ('Model Year: 2019', 2019),
            (1899, None),  # Too old
            (2040, None),  # Too new
            ('not a year', None),
            (None, None),
        ]
        
        for input_year, expected in test_cases:
            normalized = lot_normalizer._normalize_year(input_year)
            assert normalized == expected, f"Year {input_year} should normalize to {expected}"
    
    def test_make_normalization(self):
        """Test make normalization."""
        test_cases = [
            ('toyota', 'Toyota'),
            ('TOYOTA', 'Toyota'),
            ('chevy', 'Chevrolet'),
            ('LEXUS', 'Lexus'),
            ('Unknown Make', 'Unknown Make'),
        ]
        
        for input_make, expected in test_cases:
            normalized = lot_normalizer._normalize_make(input_make)
            assert normalized == expected, f"Make {input_make} should normalize to {expected}"
    
    def test_title_status_normalization(self):
        """Test title status normalization."""
        test_cases = [
            ('Clean title', '', 'clean'),
            ('Salvage title', '', 'salvage'),
            ('', 'This car was totaled in accident', 'salvage'),
            ('', 'Rebuilt after damage', 'rebuilt'),
            ('', 'Parts only vehicle', 'parts_only'),
            ('Unknown', '', 'unknown'),
        ]
        
        for title_status, raw_text, expected in test_cases:
            normalized = lot_normalizer._normalize_title_status(title_status, raw_text)
            assert normalized == expected, f"Title '{title_status}' with text '{raw_text}' should be {expected}"
    
    def test_extract_from_raw_text(self):
        """Test extracting fields from raw text."""
        raw_text = "2018 Toyota Tacoma TRD Sport VIN: 1ABCD23EFGH456789 Clean title, runs great"
        
        lot = {}
        result = lot_normalizer._extract_from_raw_text(lot, raw_text)
        
        assert result['vin'] == '1ABCD23EFGH456789'
        assert result['year'] == 2018
        assert result['make'] == 'Toyota'
        assert result['model'] == 'Tacoma'
    
    def test_odometer_normalization(self):
        """Test odometer normalization."""
        test_cases = [
            (85000, 85000),
            ('85,000 miles', 85000),
            ('Odometer: 125000', 125000),
            ('High mileage', None),
            (-1000, None),  # Negative
            (2000000, None),  # Too high
        ]
        
        for input_odo, expected in test_cases:
            normalized = lot_normalizer._normalize_odometer(input_odo)
            assert normalized == expected, f"Odometer {input_odo} should normalize to {expected}"