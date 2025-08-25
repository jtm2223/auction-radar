"""Auction source scrapers."""

from .south_florida_aa import SouthFloridaAAScraper
from .nyc_finance import NYCFinanceScraper
from .statewide_auction import StatewideAuctionScraper
from .placeholder_scrapers import CountySheriffScraper, CityImpoundScraper

# Registry of all available scrapers
SCRAPERS = {
    'south_florida_aa': SouthFloridaAAScraper,
    'nyc_finance': NYCFinanceScraper,
    'statewide_auction': StatewideAuctionScraper,
    'county_sheriff': CountySheriffScraper,
    'city_impound': CityImpoundScraper,
}

def get_all_scrapers():
    """Get instances of all available scrapers."""
    return [scraper_class() for scraper_class in SCRAPERS.values()]

