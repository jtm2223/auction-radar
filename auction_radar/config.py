"""Configuration management for auction radar."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Application configuration."""
    
    # Database
    AUCTION_DB = os.getenv("AUCTION_DB", "auction_radar.sqlite")
    
    # Timezone
    TZ_DEFAULT = os.getenv("TZ_DEFAULT", "America/New_York")
    
    # Email
    EMAIL_ENABLED = os.getenv("EMAIL_ENABLED", "false").lower() == "true"
    EMAIL_SMTP_HOST = os.getenv("EMAIL_SMTP_HOST", "smtp.gmail.com")
    EMAIL_SMTP_PORT = int(os.getenv("EMAIL_SMTP_PORT", "587"))
    EMAIL_USER = os.getenv("EMAIL_USER", "")
    EMAIL_PASS = os.getenv("EMAIL_PASS", "")
    EMAIL_FROM_NAME = os.getenv("EMAIL_FROM_NAME", "Auction Radar")
    EMAIL_TO = [email.strip() for email in os.getenv("EMAIL_TO", "").split(",") if email.strip()]
    
    # Scraping
    USER_AGENT = os.getenv("USER_AGENT", "Mozilla/5.0 (compatible; AuctionRadar/1.0)")
    REQUEST_DELAY = float(os.getenv("REQUEST_DELAY", "5"))
    RESPECT_ROBOTS = os.getenv("RESPECT_ROBOTS", "true").lower() == "true"
    
    # Project root
    PROJECT_ROOT = Path(__file__).parent.parent

config = Config()