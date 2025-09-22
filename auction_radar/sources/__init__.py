"""Regional auction sources focused on NY, CT, MA, NJ, RI state surplus auctions."""

from .nyc_finance import NYCFinanceScraper
from .ct_state_surplus import CTStateSurplusScraper
from .ct_statewide_auction import CTStatewideAuctionScraper
from .ma_state_surplus import MAStateSurplusScraper
from .nj_state_surplus import NJStateSurplusScraper
from .nj_south_jersey_auction import NJSouthJerseyAuctionScraper
from .nj_adesa_auction import NJADESAAuctionScraper
from .ny_state_surplus import NYStateSurplusScraper
from .ri_state_surplus import RIStateSurplusScraper
from .public_surplus import PublicSurplusScraper
from .gsa_auctions import GSAAuctionsScraper
from .ny_abetter_bid import NYABetterBidScraper

# Regional scraper registry - only working state surplus sources
SCRAPERS = {
    'nyc_finance': NYCFinanceScraper,
    'ct_state_surplus': CTStateSurplusScraper,
    'ct_statewide_auction': CTStatewideAuctionScraper,
    'ma_state_surplus': MAStateSurplusScraper,
    'nj_state_surplus': NJStateSurplusScraper,
    'nj_south_jersey_auction': NJSouthJerseyAuctionScraper,
    'nj_adesa_auction': NJADESAAuctionScraper,
    'ny_state_surplus': NYStateSurplusScraper,
    'ri_state_surplus': RIStateSurplusScraper,
    'public_surplus': PublicSurplusScraper,
    'gsa_auctions': GSAAuctionsScraper,
    'abetter_bid_northeast': NYABetterBidScraper,
}

def get_all_scrapers():
    """Get all regional state surplus scrapers."""
    return [
        NYCFinanceScraper(),
        CTStateSurplusScraper(),
        CTStatewideAuctionScraper(),
        MAStateSurplusScraper(),
        NJStateSurplusScraper(),
        NJSouthJerseyAuctionScraper(),
        NJADESAAuctionScraper(),
        NYStateSurplusScraper(),
        RIStateSurplusScraper(),
        PublicSurplusScraper(),
        GSAAuctionsScraper(),
        NYABetterBidScraper(),
    ]