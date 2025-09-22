"""Tests for auction scrapers."""

import pytest
from unittest.mock import Mock, patch
import requests
from auction_radar.sources.base import BaseScraper

class TestBaseScraper:
    """Test base scraper functionality."""
    
    def test_robots_txt_checking(self):
        """Test robots.txt checking functionality."""
        scraper = BaseScraper('test', 'https://example.com')
        
        # Mock robots.txt that allows all
        with patch('urllib.robotparser.RobotFileParser') as mock_rp:
            mock_instance = Mock()
            mock_instance.can_fetch.return_value = True
            mock_rp.return_value = mock_instance
            
            result = scraper.check_robots_txt('https://example.com/test')
            assert result is True
            
        # Mock robots.txt that blocks
        with patch('urllib.robotparser.RobotFileParser') as mock_rp:
            mock_instance = Mock()
            mock_instance.can_fetch.return_value = False
            mock_rp.return_value = mock_instance
            
            result = scraper.check_robots_txt('https://example.com/blocked')
            assert result is False
    
    def test_safe_get_with_retry(self):
        """Test safe_get with retry functionality."""
        scraper = BaseScraper('test', 'https://example.com')
        
        # Mock successful response after one failure
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        
        with patch.object(scraper, 'check_robots_txt', return_value=True):
            with patch.object(scraper.session, 'get') as mock_get:
                # First call fails, second succeeds
                mock_get.side_effect = [requests.RequestException("Network error"), mock_response]
                
                result = scraper.safe_get('https://example.com/test')
                assert result == mock_response
                assert mock_get.call_count == 2
    
    def test_extract_common_fields(self):
        """Test common field extraction."""
        scraper = BaseScraper('test', 'https://example.com')
        
        text = "2018 Toyota Tacoma TRD Sport VIN: 1ABCD23EFGH456789 Clean title"
        fields = scraper.extract_common_fields(text, 'https://example.com/lot1')
        
        assert fields['year'] == 2018
        assert fields['make'] == 'Toyota'
        assert fields['model'] == 'Tacoma Trd Sport'
        assert fields['vin'] == '1ABCD23EFGH456789'
        assert fields['lot_url'] == 'https://example.com/lot1'
        assert 'raw_text' in fields