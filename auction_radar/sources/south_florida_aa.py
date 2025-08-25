"""South Florida Auto Auction scraper."""

import logging
from typing import List, Dict, Any
from datetime import datetime, timedelta
import re
from bs4 import BeautifulSoup
from .base import BaseScraper
from ..utils import safe_get_text, normalize_timezone

logger = logging.getLogger(__name__)

class SouthFloridaAAScraper(BaseScraper):
    """Scraper for South Florida Auto Auction (southfloridaaa.com)."""
    
    def __init__(self):
        super().__init__('south_florida_aa', 'https://southfloridaaa.com')
    
    def crawl(self) -> List[Dict[str, Any]]:
        """Crawl South Florida AA auction listings."""
        lots = []
        
        try:
            # Get main auction page
            response = self.safe_get(f"{self.base_url}/auctions")
            if not response:
                logger.warning("Could not fetch South Florida AA main page")
                return lots
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for upcoming auctions
            auction_links = self._find_auction_links(soup)
            
            for auction_url in auction_links:
                auction_lots = self._scrape_auction(auction_url)
                lots.extend(auction_lots)
                
                # Be polite - limit to first few auctions for demo
                if len(lots) > 50:
                    break
        
        except Exception as e:
            logger.error(f"Error crawling South Florida AA: {e}")
        
        return lots
    
    def _find_auction_links(self, soup: BeautifulSoup) -> List[str]:
        """Find links to individual auction pages."""
        links = []
        
        # Look for common auction link patterns
        for link in soup.find_all('a', href=True):
            href = link['href']
            text = link.get_text(strip=True).lower()
            
            if any(keyword in text for keyword in ['auction', 'sale', 'vehicles', 'cars']):
                if href.startswith('/'):
                    href = self.base_url + href
                elif not href.startswith('http'):
                    continue
                links.append(href)
        
        return list(set(links))[:5]  # Limit for demo
    
    def _scrape_auction(self, auction_url: str) -> List[Dict[str, Any]]:
        """Scrape individual auction page."""
        lots = []
        
        try:
            response = self.safe_get(auction_url)
            if not response:
                return lots
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract auction date/time
            auction_date = self._extract_auction_date(soup)
            
            # Find vehicle listings
            vehicle_elements = self._find_vehicle_listings(soup)
            
            for i, element in enumerate(vehicle_elements):
                lot_data = self._parse_vehicle_element(element, auction_url, auction_date, i)
                if lot_data:
                    lots.append(lot_data)
        
        except Exception as e:
            logger.error(f"Error scraping auction {auction_url}: {e}")
        
        return lots
    
    def _extract_auction_date(self, soup: BeautifulSoup) -> str:
        """Extract auction date from page."""
        # Look for common date patterns
        date_selectors = [
            '.auction-date', '.sale-date', '.event-date',
            'h1', 'h2', '.title', '.header'
        ]
        
        for selector in date_selectors:
            elements = soup.select(selector)
            for elem in elements:
                text = elem.get_text(strip=True)
                # Look for date patterns
                date_match = re.search(r'\b\w+\s+\d{1,2},?\s+\d{4}\b', text)
                if date_match:
                    return date_match.group()
        
        # Default to next week if no date found
        return (datetime.now() + timedelta(days=7)).strftime("%B %d, %Y")
    
    def _find_vehicle_listings(self, soup: BeautifulSoup) -> List:
        """Find vehicle listing elements on the page."""
        # Try different selectors for vehicle listings
        selectors = [
            '.vehicle', '.car', '.lot', '.item',
            'tr', '.listing', '.auction-item'
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            if elements and len(elements) > 2:  # Found meaningful results
                return elements[:20]  # Limit for demo
        
        # Fallback: look for any element with vehicle-related text
        all_elements = soup.find_all(['div', 'tr', 'li'])
        vehicle_elements = []
        
        for elem in all_elements:
            text = elem.get_text(strip=True).lower()
            if any(keyword in text for keyword in ['toyota', 'honda', 'ford', 'year', 'vin']):
                vehicle_elements.append(elem)
        
        return vehicle_elements[:20]
    
    def _parse_vehicle_element(self, element, auction_url: str, auction_date: str, index: int) -> Dict[str, Any]:
        """Parse individual vehicle element."""
        text = element.get_text(strip=True)
        if len(text) < 10:  # Skip empty or tiny elements
            return None
        
        # Extract basic info using base class method
        base_data = self.extract_common_fields(text, auction_url)
        
        # Parse auction date
        sale_date_utc, tz_name = normalize_timezone(f"{auction_date} 10:00 AM")
        
        lot_data = {
            'source': self.source_name,
            'source_lot_id': f"sfaa_{hash(auction_url + str(index))}",
            'sale_date_utc': sale_date_utc.isoformat() if sale_date_utc else None,
            'sale_local_time': f"{auction_date} 10:00 AM",
            'tz_name': tz_name,
            'location_name': 'South Florida Auto Auction',
            'location_city': 'Fort Lauderdale',
            'location_state': 'FL',
            **base_data
        }
        
        return lot_data