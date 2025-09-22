"""Database operations for auction radar."""

import sqlite3
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from contextlib import contextmanager
from pathlib import Path

logger = logging.getLogger(__name__)

class AuctionDB:
    """Database manager for auction lots."""
    
    def __init__(self, db_path: str = "auction_radar.sqlite"):
        self.db_path = Path(db_path)
        self.init_db()
    
    def init_db(self):
        """Initialize database with schema."""
        with self.get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS lots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    source_lot_id TEXT NOT NULL,
                    lot_url TEXT,
                    sale_date_utc TEXT,
                    sale_local_time TEXT,
                    tz_name TEXT DEFAULT 'America/New_York',
                    location_name TEXT,
                    location_city TEXT,
                    location_state TEXT,
                    vin TEXT,
                    year INTEGER,
                    make TEXT,
                    model TEXT,
                    trim TEXT,
                    drivetrain TEXT,
                    odometer INTEGER,
                    title_status TEXT DEFAULT 'unknown',
                    condition_notes TEXT,
                    raw_text TEXT,
                    -- NYC Finance specific fields
                    lot_number INTEGER,
                    license_plate TEXT,
                    license_state TEXT,
                    -- VIN-decoded fields
                    vin_series TEXT,
                    vin_body_class TEXT,
                    vin_vehicle_type TEXT,
                    vin_engine_cylinders TEXT,
                    vin_fuel_type TEXT,
                    vin_transmission TEXT,
                    vin_trim TEXT,
                    body_class TEXT,
                    fuel_type TEXT,
                    vehicle_description TEXT,
                    current_bid REAL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(source, source_lot_id)
                );
                
                CREATE INDEX IF NOT EXISTS idx_lots_vin ON lots(vin);
                CREATE INDEX IF NOT EXISTS idx_lots_sale_date ON lots(sale_date_utc);
                CREATE INDEX IF NOT EXISTS idx_lots_source ON lots(source);
                CREATE INDEX IF NOT EXISTS idx_lots_make_model ON lots(make, model);
                CREATE INDEX IF NOT EXISTS idx_lots_title_status ON lots(title_status);
            """)
    
    @contextmanager
    def get_connection(self):
        """Get database connection with proper cleanup."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        try:
            yield conn
        finally:
            conn.close()
    
    def upsert_lot(self, lot_data: Dict[str, Any]) -> bool:
        """Insert or update a lot record."""
        try:
            # Ensure required fields
            if not lot_data.get('source') or not lot_data.get('source_lot_id'):
                logger.warning(f"Missing required fields: {lot_data}")
                return False
            
            # Set updated_at
            lot_data['updated_at'] = datetime.utcnow().isoformat()
            
            with self.get_connection() as conn:
                # Try insert first
                placeholders = ', '.join(['?' for _ in lot_data])
                columns = ', '.join(lot_data.keys())
                values = list(lot_data.values())
                
                try:
                    conn.execute(
                        f"INSERT INTO lots ({columns}) VALUES ({placeholders})",
                        values
                    )
                    conn.commit()
                    logger.debug(f"Inserted new lot: {lot_data['source']}/{lot_data['source_lot_id']}")
                    return True
                    
                except sqlite3.IntegrityError:
                    # Record exists, update it
                    set_clause = ', '.join([f"{k} = ?" for k in lot_data.keys() if k not in ('source', 'source_lot_id')])
                    update_values = [v for k, v in lot_data.items() if k not in ('source', 'source_lot_id')]
                    update_values.extend([lot_data['source'], lot_data['source_lot_id']])
                    
                    conn.execute(
                        f"UPDATE lots SET {set_clause} WHERE source = ? AND source_lot_id = ?",
                        update_values
                    )
                    conn.commit()
                    logger.debug(f"Updated existing lot: {lot_data['source']}/{lot_data['source_lot_id']}")
                    return True
                    
        except Exception as e:
            logger.error(f"Failed to upsert lot: {e}")
            return False
    
    def get_lots(self, 
                 days_ahead: int = 14, 
                 make: Optional[str] = None,
                 state: Optional[str] = None,
                 title_status: Optional[str] = None) -> List[Dict]:
        """Get lots within specified criteria."""
        
        query = """
            SELECT * FROM lots 
            WHERE (sale_date_utc >= ? AND sale_date_utc <= ?) 
               OR sale_date_utc IS NULL
        """
        params = [
            datetime.utcnow().isoformat(),
            (datetime.utcnow() + timedelta(days=days_ahead)).isoformat()
        ]
        
        if make:
            query += " AND make LIKE ?"
            params.append(f"%{make}%")
            
        if state:
            query += " AND location_state = ?"
            params.append(state)
            
        if title_status and title_status != 'all':
            query += " AND title_status = ?"
            params.append(title_status)
        
        query += " ORDER BY CASE WHEN sale_date_utc IS NULL THEN 1 ELSE 0 END, sale_date_utc ASC"
        
        try:
            with self.get_connection() as conn:
                cursor = conn.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get lots: {e}")
            return []
    
    def get_target_matches(self, days_ahead: int = 14) -> List[Dict]:
        """Get lots that match target keywords."""
        try:
            from .keywords import keyword_matcher
        except ImportError:
            # Fallback if keywords module not available yet
            logger.warning("Keywords module not available, returning all lots")
            return self.get_lots(days_ahead=days_ahead)
        
        lots = self.get_lots(days_ahead=days_ahead)
        matches = []
        
        for lot in lots:
            # Check if lot matches target keywords
            search_text = f"{lot.get('make', '')} {lot.get('model', '')} {lot.get('raw_text', '')}"
            if keyword_matcher.has_target_match(search_text):
                matches.append(lot)
        
        return matches
    
    def cleanup_old_lots(self, days_old: int = 30):
        """Remove lots older than specified days."""
        cutoff_date = (datetime.utcnow() - timedelta(days=days_old)).isoformat()
        
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("DELETE FROM lots WHERE sale_date_utc < ?", [cutoff_date])
                deleted_count = cursor.rowcount
                conn.commit()
                logger.info(f"Cleaned up {deleted_count} old lots")
                return deleted_count
        except Exception as e:
            logger.error(f"Failed to cleanup old lots: {e}")
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        try:
            with self.get_connection() as conn:
                stats = {}
                
                # Total lots
                cursor = conn.execute("SELECT COUNT(*) as count FROM lots")
                stats['total_lots'] = cursor.fetchone()['count']
                
                # Lots by source
                cursor = conn.execute("""
                    SELECT source, COUNT(*) as count 
                    FROM lots 
                    GROUP BY source 
                    ORDER BY count DESC
                """)
                stats['by_source'] = dict(cursor.fetchall())
                
                # Upcoming lots
                future_date = (datetime.utcnow() + timedelta(days=14)).isoformat()
                cursor = conn.execute("""
                    SELECT COUNT(*) as count 
                    FROM lots 
                    WHERE sale_date_utc >= ? AND sale_date_utc <= ?
                """, [datetime.utcnow().isoformat(), future_date])
                stats['upcoming_lots'] = cursor.fetchone()['count']
                
                return stats
                
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {}
    
    def add_sample_data(self):
        """Add sample data for testing purposes."""
        sample_lots = [
            {
                'source': 'test_source',
                'source_lot_id': 'sample_1',
                'lot_url': 'https://example.com/lot1',
                'sale_date_utc': (datetime.utcnow() + timedelta(days=7)).isoformat(),
                'sale_local_time': 'January 1, 2025 10:00 AM',
                'tz_name': 'America/New_York',
                'location_name': 'Northeast Auction House',
                'location_city': 'Albany',
                'location_state': 'NY',
                'vin': '1ABCD23EFGH456789',
                'year': 2018,
                'make': 'Toyota',
                'model': '4Runner',
                'trim': 'SR5',
                'title_status': 'clean',
                'condition_notes': 'Good condition, minor scratches',
                'raw_text': '2018 Toyota 4Runner SR5 VIN: 1ABCD23EFGH456789 Clean title, good condition',
            },
            {
                'source': 'test_source',
                'source_lot_id': 'sample_2',
                'lot_url': 'https://example.com/lot2',
                'sale_date_utc': (datetime.utcnow() + timedelta(days=10)).isoformat(),
                'sale_local_time': 'January 4, 2025 2:00 PM',
                'tz_name': 'America/New_York',
                'location_name': 'Hartford County Sheriff Auction',
                'location_city': 'Hartford',
                'location_state': 'CT',
                'vin': '2WXYZ98KLMN123456',
                'year': 2019,
                'make': 'Toyota',
                'model': 'Land Cruiser',
                'trim': 'Heritage Edition',
                'title_status': 'clean',
                'condition_notes': 'Former state vehicle, well maintained',
                'raw_text': '2019 Toyota Land Cruiser Heritage Edition VIN: 2WXYZ98KLMN123456 Clean title, state vehicle',
            },
            {
                'source': 'test_source',
                'source_lot_id': 'sample_3',
                'lot_url': 'https://example.com/lot3',
                'sale_date_utc': (datetime.utcnow() + timedelta(days=12)).isoformat(),
                'sale_local_time': 'January 6, 2025 11:00 AM',
                'tz_name': 'America/New_York',
                'location_name': 'Boston Municipal Surplus Auction',
                'location_city': 'Boston',
                'location_state': 'MA',
                'vin': '3PQRS45TUVW789012',
                'year': 2020,
                'make': 'Nissan',
                'model': 'Frontier',
                'trim': 'SV',
                'title_status': 'clean',
                'condition_notes': 'City fleet vehicle, regular maintenance',
                'raw_text': '2020 Nissan Frontier SV VIN: 3PQRS45TUVW789012 Clean title, city fleet',
            }
        ]
        
        logger.info("Adding sample data...")
        count = 0
        for lot in sample_lots:
            if self.upsert_lot(lot):
                count += 1
        
        logger.info(f"Added {count} sample lots")
        return count