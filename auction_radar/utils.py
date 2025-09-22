"""Utility functions for auction radar."""

import time
import logging
import requests
from typing import Optional
from functools import wraps
import pytz
from datetime import datetime

logger = logging.getLogger(__name__)

def setup_logging(level=logging.INFO):
    """Setup logging configuration."""
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('auction_radar.log'),
            logging.StreamHandler()
        ]
    )

def retry_with_backoff(max_retries=3, base_delay=1, max_delay=60):
    """Decorator for retrying functions with exponential backoff."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise e
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay}s")
                    time.sleep(delay)
            return None
        return wrapper
    return decorator

def safe_get_text(element, default="") -> str:
    """Safely extract text from BeautifulSoup element."""
    if element is None:
        return default
    return element.get_text(strip=True) or default

def normalize_timezone(dt_str: str, default_tz: str = "America/New_York") -> tuple[Optional[datetime], str]:
    """
    Parse datetime string and return UTC datetime and timezone name.
    
    Args:
        dt_str: DateTime string to parse
        default_tz: Default timezone if none specified
    
    Returns:
        Tuple of (UTC datetime, timezone name)
    """
    from dateutil import parser as date_parser
    
    if not dt_str:
        return None, default_tz
    
    try:
        # Try to parse the datetime
        dt = date_parser.parse(dt_str)
        
        # If no timezone info, assume default
        if dt.tzinfo is None:
            tz = pytz.timezone(default_tz)
            dt = tz.localize(dt)
            tz_name = default_tz
        else:
            tz_name = str(dt.tzinfo)
        
        # Convert to UTC
        utc_dt = dt.astimezone(pytz.UTC)
        return utc_dt, tz_name
        
    except Exception as e:
        logger.warning(f"Failed to parse datetime '{dt_str}': {e}")
        return None, default_tz

def create_session(user_agent: str, request_delay: float = 5) -> requests.Session:
    """Create a requests session with appropriate headers and delay."""
    session = requests.Session()
    session.headers.update({
        'User-Agent': user_agent,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
    })
    
    # Add delay between requests
    original_get = session.get
    def delayed_get(*args, **kwargs):
        time.sleep(request_delay)
        return original_get(*args, **kwargs)
    session.get = delayed_get
    
    return session