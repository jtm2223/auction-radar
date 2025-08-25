"""Command-line interface for auction radar."""

import argparse
import sys
import logging
from datetime import datetime, timedelta
import csv
from pathlib import Path

from .config import config
from .db import AuctionDB
from .sources import get_all_scrapers
from .auction_radar.normalize import lot_normalizer
from .email_digest import EmailDigest
from .utils import setup_logging

logger = logging.getLogger(__name__)

def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description='Regional Tow Auction Radar')
    
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
    parser.add_argument('--ignore-robots', action='store_true',
                       help='Ignore robots.txt (for testing only)')
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    setup_logging(log_level)
    
    # Override robots.txt setting if requested
    if args.ignore_robots:
        config.RESPECT_ROBOTS = False
        logger.warning("Ignoring robots.txt restrictions")
    
    # Initialize database
    db = AuctionDB(config.AUCTION_DB)
    
    if args.crawl:
        crawl_sources(db, args.since_days)
    
    if args.email:
        send_email_digest(db)
    
    if args.export_csv:
        export_to_csv(db, args.export_csv)
    
    if args.cleanup:
        cleanup_database(db)
    
    if args.stats:
        show_stats(db)
    
    # If no specific action requested, show help
    if not any([args.crawl, args.email, args.export_csv, args.cleanup, args.stats]):
        parser.print_help()

def crawl_sources(db: AuctionDB, since_days: int):
    """Crawl all auction sources."""
    logger.info("Starting auction source crawling...")
    
    scrapers = get_all_scrapers()
    total_lots = 0
    successful_sources = 0
    
    cutoff_date = datetime.utcnow() + timedelta(days=since_days)
    
    for scraper in scrapers:
        try:
            logger.info(f"Crawling {scraper.source_name}...")
            raw_lots = scraper.crawl()
            
            processed_lots = 0
            for raw_lot in raw_lots:
                # Normalize the lot data
                normalized_lot = lot_normalizer.normalize_lot(raw_lot)
                
                # Check if sale date is within our window
                sale_date_str = normalized_lot.get('sale_date_utc')
                if sale_date_str:
                    try:
                        sale_date = datetime.fromisoformat(sale_date_str.replace('Z', '+00:00'))
                        if sale_date > cutoff_date:
                            continue  # Skip lots too far in future
                    except:
                        pass  # Include lots with unparseable dates
                
                # Store in database
                if db.upsert_lot(normalized_lot):
                    processed_lots += 1
            
            logger.info(f"Processed {processed_lots} lots from {scraper.source_name}")
            total_lots += processed_lots
            successful_sources += 1
            
        except Exception as e:
            logger.error(f"Error crawling {scraper.source_name}: {e}")
    
    logger.info(f"Crawling complete: {total_lots} lots from {successful_sources} sources")

def send_email_digest(db: AuctionDB):
    """Send email digest."""
    logger.info("Generating email digest...")
    
    digest = EmailDigest(db)
    success = digest.send_digest(days_ahead=14)
    
    if success:
        logger.info("Email digest sent successfully")
    else:
        logger.error("Failed to send email digest")

def export_to_csv(db: AuctionDB, filename: str):
    """Export target matches to CSV."""
    logger.info(f"Exporting target matches to {filename}...")
    
    # Get target matches for next 14 days
    lots = db.get_target_matches(days_ahead=14)
    
    if not lots:
        logger.info("No target matches found to export")
        return
    
    # Rank the lots
    from .ranker import lot_ranker
    ranked_lots = lot_ranker.rank_lots(lots)
    
    # Write to CSV
    fieldnames = [
        'source', 'source_lot_id', 'lot_url', 'sale_date_utc', 'sale_local_time',
        'location_city', 'location_state', 'vin', 'year', 'make', 'model',
        'title_status', 'condition_notes', 'score'
    ]
    
    try:
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for lot in ranked_lots:
                # Filter to only include specified fields
                row = {field: lot.get(field, '') for field in fieldnames}
                writer.writerow(row)
        
        logger.info(f"Exported {len(ranked_lots)} target matches to {filename}")
        
    except Exception as e:
        logger.error(f"Error exporting to CSV: {e}")

def cleanup_database(db: AuctionDB):
    """Clean up old lots from database."""
    logger.info("Cleaning up old lots...")
    
    deleted_count = db.cleanup_old_lots(days_old=30)
    logger.info(f"Cleaned up {deleted_count} old lots")

def show_stats(db: AuctionDB):
    """Show database statistics."""
    logger.info("Database Statistics:")
    
    stats = db.get_stats()
    
    print(f"\nTotal lots: {stats.get('total_lots', 0)}")
    print(f"Upcoming lots (next 14 days): {stats.get('upcoming_lots', 0)}")
    
    by_source = stats.get('by_source', {})
    if by_source:
        print("\nLots by source:")
        for source, count in by_source.items():
            print(f"  {source}: {count}")
    
    # Show target match stats
    target_lots = db.get_target_matches(days_ahead=14)
    print(f"\nTarget matches (next 14 days): {len(target_lots)}")
    
    if target_lots:
        from .ranker import lot_ranker
        ranked_lots = lot_ranker.rank_lots(target_lots)
        
        if ranked_lots:
            avg_score = sum(lot.get('score', 0) for lot in ranked_lots) / len(ranked_lots)
            print(f"Average target score: {avg_score:.2f}")
            
            best_lot = ranked_lots[0]
            print(f"Best match: {best_lot.get('year', 'Unknown')} {best_lot.get('make', '')} {best_lot.get('model', '')} (Score: {best_lot.get('score', 0):.2f})")

if __name__ == '__main__':
    main()