# Regional Tow Auction Radar

A comprehensive Python system for aggregating and monitoring regional tow yard, police, and sheriff vehicle auctions nationwide. Specifically designed to identify target vehicles for import/export operations.

## 🎯 What It Does

- **Monitors Regional Auctions**: Scrapes county/city tow auctions, police/sheriff auctions, and municipal surplus auctions
- **Targets Specific Vehicles**: Land Cruisers, 4Runners, Tacomas, Tundras, Frontiers, Titans, and RV/campers
- **Handles All Conditions**: Clean, rebuilt, salvage, flood, totaled, parts-only vehicles
- **Smart Ranking**: Scores vehicles by desirability and deduplicates by VIN
- **Multiple Interfaces**: CLI tools, web dashboard, and email digests

## 🚗 Target Vehicles

### High Priority
- **Lexus/Toyota Land Cruiser** (all variants)
- **Toyota 4Runner** (all trims)

### Medium Priority  
- **Toyota Trucks**: Tacoma, Tundra
- **Nissan Trucks**: Frontier, Titan

### Specialty
- **RVs/Campers**: Class B/C, Sprinter/ProMaster/Transit conversions, travel trailers, teardrops

## 🛠️ Installation & Setup

### 1. Clone and Install Dependencies
```bash
git clone <repository-url>
cd auction_radar
pip install -r requirements.txt
```

### 2. Configuration
```bash
cp sample.env .env
# Edit .env with your settings
```

Key settings in `.env`:
- `EMAIL_*`: SMTP settings for digest emails
- `AUCTION_DB`: SQLite database location
- `TZ_DEFAULT`: Default timezone (America/New_York)

### 3. Initialize Database
```bash
python -m auction_radar --crawl
```

## 📊 Usage

### CLI Commands

```bash
# Crawl all sources and update database
python -m auction_radar --crawl

# Crawl with date filtering (only next 21 days)
python -m auction_radar --crawl --since-days 21

# Send email digest (or print to console if email not configured)
python -m auction_radar --email

# Export target matches to CSV
python -m auction_radar --export-csv matches.csv

# Show database statistics
python -m auction_radar --stats

# Clean up old lots
python -m auction_radar --cleanup

# Verbose logging
python -m auction_radar --crawl --verbose
```

### Web Dashboard

```bash
streamlit run dashboard_app.py
```

Features:
- **Filters**: Date range, make/model, state, title status
- **Target Matches**: Top scoring vehicles with details
- **Interactive Table**: Sortable columns, clickable links
- **Export**: Download filtered results as CSV

### Email Digests

Automatically sends weekly summaries of top target matches including:
- Vehicle details (year, make, model)
- Location and sale date/time
- Title status and condition notes  
- Auction links
- Category breakdown

## 🗄️ Database Schema

SQLite database with `lots` table containing:

- **Identifiers**: `source`, `source_lot_id`, `lot_url`
- **Timing**: `sale_date_utc`, `sale_local_time`, `tz_name`
- **Location**: `location_name`, `location_city`, `location_state`
- **Vehicle**: `vin`, `year`, `make`, `model`, `trim`, `drivetrain`, `odometer`
- **Condition**: `title_status`, `condition_notes`
- **Raw Data**: `raw_text`
- **Metadata**: `created_at`, `updated_at`

## 🔍 Current Sources

### Live Sources
- **South Florida Auto Auction** (southfloridaaa.com)
- **NYC Finance Department** (nyc.gov vehicle auctions)  
- **Statewide Auction** (statewideauction.com)

### Placeholder Sources
- **County Sheriff Auctions** (template for county sites)
- **City Impound Auctions** (includes PDF parsing example)

### Adding New Sources

1. Create scraper in `auction_radar/sources/`
2. Inherit from `BaseScraper`
3. Implement `crawl()` method returning lot dictionaries
4. Add to `SCRAPERS` registry in `sources/__init__.py`

Required fields in lot dictionary:
```python
{
    'source': 'source_name',
    'source_lot_id': 'unique_id',  
    'sale_date_utc': 'ISO_datetime',
    'location_city': 'City',
    'location_state': 'State',
    'raw_text': 'Full text description',
    # Optional: vin, year, make, model, title_status, etc.
}
```

## 🎯 Scoring System

Vehicles are scored 0-1 based on:

### Base Scores
- Land Cruiser: 1.0
- 4Runner: 0.9  
- Tacoma/Tundra: 0.8
- Frontier/Titan: 0.7
- RVs/Campers: 0.6

### Penalties
- **Title Status**: Clean (0%), Rebuilt (5%), Salvage (20%), Parts Only (60%)
- **Age**: 1% penalty per year (max 30%)

### Deduplication
- Removes duplicate VINs
- Keeps highest scoring instance
- Preserves lots without VINs

## 🤖 Technical Features

### Web Scraping
- Respectful crawling (robots.txt, delays, user agents)
- Retry logic with exponential backoff
- Both HTML (BeautifulSoup) and PDF (pdfminer.six) parsing
- Session management and error handling

### Data Processing
- Smart text extraction (VIN, year, make/model)
- Title status normalization
- Timezone handling (UTC storage, local display)
- Keyword matching with compiled regexes

### Monitoring
- Comprehensive logging (file + console)
- Database statistics and health checks
- Email alerts for new matches
- Data validation and cleanup

## 🧪 Testing

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=auction_radar

# Run specific test file
pytest tests/test_keywords.py -v
```

Test coverage includes:
- Keyword matching accuracy
- Data normalization edge cases
- Scoring and ranking logic
- Scraper base functionality

## 🚀 Deployment Ideas

### Local Development
```bash
# One-time setup
python -m auction_radar --crawl
streamlit run dashboard_app.py
```

### Scheduled Production
```bash
# Add to crontab for daily crawling
0 6 * * * cd /path/to/auction_radar && python -m auction_radar --crawl --email

# Weekly digest
0 8 * * 1 cd /path/to/auction_radar && python -m auction_radar --email
```

### Cloud Deployment
- **AWS**: Lambda for crawling, RDS for database, SES for emails
- **Google Cloud**: Cloud Functions + Cloud SQL + Gmail API
- **Heroku**: Scheduler add-on + Postgres + SendGrid

## 🔧 Architecture

```
auction_radar/
├── sources/           # Site-specific scrapers
├── db.py             # Database operations  
├── normalize.py      # Data cleaning
├── keywords.py       # Target matching
├── ranker.py         # Scoring system
├── email_digest.py   # Email notifications
├── config.py         # Settings management
├── utils.py          # Common utilities
└── __main__.py       # CLI interface

dashboard_app.py      # Streamlit web UI
tests/               # Unit tests
```

## 📈 Future Enhancements

- **Geographic Expansion**: Add more regional sources
- **Transport Integration**: Distance/cost calculations to ports
- **Market Analysis**: Price tracking and trends
- **Mobile App**: React Native or Flutter interface
- **API Access**: RESTful API for external integrations
- **ML Improvements**: Better text extraction and classification

## ⚖️ Legal & Compliance

- Respects robots.txt by default
- Only scrapes publicly available data
- Includes reasonable delays between requests
- No authentication bypass
- Descriptive user agent identification

## 🤝 Contributing

1. Fork the repository
2. Create feature branch
3. Add tests for new functionality  
4. Ensure all tests pass
5. Submit pull request

## 📄 License

MIT License - See LICENSE file for details.

---

**Regional Tow Auction Radar** - Finding diamonds in the rough, one auction at a time. 💎🚗