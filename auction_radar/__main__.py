"""Command-line interface for auction radar."""

import argparse
import sys
import logging
from datetime import datetime, timedelta
import csv
from pathlib import Path

from .config import config
from .db_adapter import AuctionDB
from .sources import get_all_scrapers
from .utils import setup_logging

logger = logging.getLogger(__name__)

def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description='Northeast State Surplus Auction Radar')
    
    parser.add_argument('--crawl', action='store_true',
                       help='Run all source scrapers')
    parser.add_argument('--since-days', type=int, default=30,
                       help='Only process lots with sale dates within N days (default: 30)')
    parser.add_argument('--email', action='store_true',
                       help='Send email digest')
    parser.add_argument('--export-csv', type=str,
                       help='Export target matches to CSV file')
    parser.add_argument('--cleanup', action='store_true',
                       help='Clean up old lots from database')
    parser.add_argument('--stats', action='store_true',
                       help='Show database statistics')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    parser.add_argument('--sample-data', action='store_true',
                       help='Add sample data for testing')
    parser.add_argument('--dashboard', action='store_true',
                       help='Run full dashboard with auto-refresh (crawl + stats + export)')
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    setup_logging(log_level)
    
    # Initialize database
    db = AuctionDB(config.AUCTION_DB)
    
    if args.dashboard:
        run_dashboard(db, args.since_days, args.verbose)
    elif args.crawl:
        crawl_sources(db, args.since_days)
    elif args.email:
        send_email_digest(db)
    elif args.export_csv:
        export_to_csv(db, args.export_csv)
    elif args.cleanup:
        cleanup_database(db)
    elif args.stats:
        show_stats(db)
    elif args.sample_data:
        add_sample_data(db)
    else:
        # Default to dashboard if no args provided
        run_dashboard(db, args.since_days, args.verbose)

def run_dashboard(db: AuctionDB, since_days: int, verbose: bool = False):
    """Run complete dashboard with auto-refresh."""
    print("🎯 NORTHEAST AUCTION RADAR DASHBOARD")
    print("="*50)
    
    # 1. Auto-refresh data
    print("📊 Refreshing auction data...")
    crawl_sources(db, since_days)
    
    print("\n" + "="*50)
    
    # 2. Show current stats
    show_stats(db)
    
    # 3. Auto-export TARGET MATCHES to CSV
    export_filename = f"target_vehicles_{datetime.now().strftime('%Y%m%d')}.csv"
    print(f"\n📁 Exporting target matches to {export_filename}...")
    export_to_csv(db, export_filename)
    
    print(f"\n✅ Dashboard complete! Data exported to {export_filename}")
    print("💡 Run 'python -m auction_radar' anytime to refresh")

def crawl_sources(db: AuctionDB, since_days: int):
    """Crawl all auction sources with timeout protection."""
    import signal
    from contextlib import contextmanager
    
    @contextmanager
    def timeout(seconds):
        def timeout_handler(signum, frame):
            raise TimeoutError(f"Scraper timeout after {seconds} seconds")
        
        # Set the signal handler
        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(seconds)
        
        try:
            yield
        finally:
            # Restore the old handler
            signal.signal(signal.SIGALRM, old_handler)
            signal.alarm(0)
    
    logger.info("Starting auction source crawling...")
    
    scrapers = get_all_scrapers()
    total_lots = 0
    successful_scrapers = 0
    
    for scraper in scrapers:
        try:
            logger.info(f"Crawling {scraper.source_name}...")
            
            # Add timeout protection - max 2 minutes per scraper
            with timeout(120):
                raw_lots = scraper.crawl()
            
            processed_lots = 0
            target_lots = 0
            
            for raw_lot in raw_lots:
                # Check if it's a target vehicle before storing
                from .target_filter import target_filter
                if target_filter.is_target_vehicle(raw_lot):
                    if db.upsert_lot(raw_lot):
                        processed_lots += 1
                        target_lots += 1
                # Still store non-target lots but don't count them as priority
                elif db.upsert_lot(raw_lot):
                    processed_lots += 1
            
            logger.info(f"Processed {processed_lots} lots ({target_lots} targets) from {scraper.source_name}")
            total_lots += processed_lots
            successful_scrapers += 1
            
        except TimeoutError as e:
            logger.error(f"Timeout crawling {scraper.source_name}: {e}")
        except Exception as e:
            logger.error(f"Error crawling {scraper.source_name}: {e}")
    
    logger.info(f"Crawling complete: {total_lots} lots processed from {successful_scrapers} scrapers")

def send_email_digest(db: AuctionDB):
    """Send email digest (placeholder)."""
    logger.info("Email digest not implemented yet")
    print("📧 Email digest functionality coming soon!")

def export_to_csv(db: AuctionDB, filename: str):
    """Export target matches to CSV."""
    logger.info(f"Exporting to {filename}...")
    
    lots = db.get_target_matches(days_ahead=14)
    
    if not lots:
        logger.info("No lots found to export")
        return
    
    # Write to CSV
    fieldnames = [
        'source', 'source_lot_id', 'lot_url', 'sale_date_utc', 'sale_local_time',
        'location_city', 'location_state', 'vin', 'year', 'make', 'model',
        'title_status', 'condition_notes'
    ]
    
    try:
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for lot in lots:
                row = {field: lot.get(field, '') for field in fieldnames}
                writer.writerow(row)
        
        logger.info(f"Exported {len(lots)} lots to {filename}")
        
    except Exception as e:
        logger.error(f"Error exporting to CSV: {e}")

def cleanup_database(db: AuctionDB):
    """Clean up old lots from database."""
    logger.info("Cleaning up old lots...")
    deleted_count = db.cleanup_old_lots(days_old=30) if hasattr(db, 'cleanup_old_lots') else 0
    logger.info(f"Cleaned up {deleted_count} old lots")

def add_sample_data(db: AuctionDB):
    """Add sample data to database."""
    count = db.add_sample_data()
    print(f"✅ Added {count} sample lots")

def show_stats(db: AuctionDB):
    """Show database statistics."""
    logger.info("Database Statistics:")
    
    stats = db.get_stats()
    
    print(f"\n📊 AUCTION RADAR STATISTICS")
    print(f"{'='*40}")
    print(f"Total lots: {stats.get('total_lots', 0)}")
    print(f"Upcoming lots (next 14 days): {stats.get('upcoming_lots', 0)}")
    
    by_source = stats.get('by_source', {})
    if by_source:
        print(f"\nLots by source:")
        for source, count in by_source.items():
            print(f"  📁 {source}: {count}")
    
    # Show TARGET MATCHES ONLY - this is what we actually want to buy
    target_lots = db.get_target_matches(days_ahead=14)
    all_lots = db.get_lots(days_ahead=14)
    
    print(f"\n🎯 TARGET VEHICLE MATCHES ({len(target_lots)} of {len(all_lots)} total lots):")
    
    if target_lots:
        for lot in target_lots[:10]:  # Show more since these are filtered
            year = lot.get('year', 'Unknown')
            make = lot.get('make', 'Unknown') 
            model = lot.get('model', 'Unknown')
            city = lot.get('location_city', 'Unknown')
            state = lot.get('location_state', 'Unknown')
            date = lot.get('sale_local_time', 'TBD')
            priority = lot.get('priority', 0)
            match_reason = lot.get('match_reason', 'Target Vehicle')
            
            print(f"  ⭐ {year} {make} {model} - {city}, {state} - {date}")
            print(f"     📋 {match_reason} (Priority: {priority})")
        
        if len(target_lots) > 10:
            print(f"  ... and {len(target_lots) - 10} more target matches")
    else:
        print("  📭 No target vehicles found. Check back after next crawl.")
        print("  🎯 Targeting: Toyota 4Runner, Land Cruiser, Lexus LX, Tacoma 4x4, etc.")

if __name__ == '__main__':
    main()