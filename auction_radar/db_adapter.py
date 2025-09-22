"""Database adapter supporting both SQLite and PostgreSQL."""

import os
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Union
from contextlib import contextmanager
from pathlib import Path
from .config import config

logger = logging.getLogger(__name__)

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False
    logger.warning("psycopg2 not available, PostgreSQL support disabled")

class DatabaseAdapter:
    """Database adapter that works with both SQLite and PostgreSQL."""
    
    def __init__(self):
        self.use_postgres = bool(config.DATABASE_URL and HAS_PSYCOPG2)
        self.db_path = config.AUCTION_DB if not self.use_postgres else None
        
        logger.info(f"Using {'PostgreSQL' if self.use_postgres else 'SQLite'} database")
        
        if not self.use_postgres:
            self.db_path = Path(config.AUCTION_DB)
        
        self.init_db()
    
    @contextmanager
    def get_connection(self):
        """Get database connection with proper cleanup."""
        if self.use_postgres:
            conn = psycopg2.connect(config.DATABASE_URL, cursor_factory=RealDictCursor)
            conn.autocommit = False
        else:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
        
        try:
            yield conn
        finally:
            conn.close()
    
    def init_db(self):
        """Initialize database with schema."""
        if self.use_postgres:
            schema = """
                CREATE TABLE IF NOT EXISTS lots (
                    id SERIAL PRIMARY KEY,
                    source VARCHAR(100) NOT NULL,
                    source_lot_id VARCHAR(200) NOT NULL,
                    lot_url TEXT,
                    sale_date_utc TIMESTAMP,
                    sale_local_time VARCHAR(100),
                    tz_name VARCHAR(50) DEFAULT 'America/New_York',
                    location_name VARCHAR(200),
                    location_city VARCHAR(100),
                    location_state VARCHAR(10),
                    vin VARCHAR(17),
                    year INTEGER,
                    make VARCHAR(50),
                    model VARCHAR(100),
                    trim VARCHAR(100),
                    drivetrain VARCHAR(50),
                    odometer INTEGER,
                    title_status VARCHAR(20) DEFAULT 'unknown',
                    condition_notes TEXT,
                    raw_text TEXT,
                    lot_number INTEGER,
                    license_plate VARCHAR(20),
                    license_state VARCHAR(10),
                    vin_series VARCHAR(100),
                    vin_body_class VARCHAR(100),
                    vin_vehicle_type VARCHAR(100),
                    vin_engine_cylinders VARCHAR(10),
                    vin_fuel_type VARCHAR(50),
                    vin_transmission VARCHAR(100),
                    vin_trim VARCHAR(100),
                    body_class VARCHAR(100),
                    fuel_type VARCHAR(50),
                    vehicle_description TEXT,
                    current_bid DECIMAL(10,2),
                    mileage INTEGER,
                    car_number VARCHAR(50),
                    auction_day VARCHAR(20),
                    auction_time VARCHAR(50),
                    auction_type VARCHAR(50),
                    auction_schedule VARCHAR(200),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(source, source_lot_id)
                );
                
                CREATE INDEX IF NOT EXISTS idx_lots_vin ON lots(vin);
                CREATE INDEX IF NOT EXISTS idx_lots_sale_date ON lots(sale_date_utc);
                CREATE INDEX IF NOT EXISTS idx_lots_source ON lots(source);
                CREATE INDEX IF NOT EXISTS idx_lots_make_model ON lots(make, model);
                CREATE INDEX IF NOT EXISTS idx_lots_title_status ON lots(title_status);
            """
        else:
            schema = """
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
                    lot_number INTEGER,
                    license_plate TEXT,
                    license_state TEXT,
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
                    mileage INTEGER,
                    car_number TEXT,
                    auction_day TEXT,
                    auction_time TEXT,
                    auction_type TEXT,
                    auction_schedule TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(source, source_lot_id)
                );
                
                CREATE INDEX IF NOT EXISTS idx_lots_vin ON lots(vin);
                CREATE INDEX IF NOT EXISTS idx_lots_sale_date ON lots(sale_date_utc);
                CREATE INDEX IF NOT EXISTS idx_lots_source ON lots(source);
                CREATE INDEX IF NOT EXISTS idx_lots_make_model ON lots(make, model);
                CREATE INDEX IF NOT EXISTS idx_lots_title_status ON lots(title_status);
            """
        
        with self.get_connection() as conn:
            if self.use_postgres:
                with conn.cursor() as cur:
                    cur.execute(schema)
                conn.commit()
            else:
                conn.executescript(schema)

        # Run migrations for existing databases
        self._run_migrations()

    def _run_migrations(self):
        """Run database migrations for existing databases."""
        migrations = [
            self._add_ct_auction_fields,
        ]

        for migration in migrations:
            try:
                migration()
            except Exception as e:
                logger.debug(f"Migration failed (may already be applied): {e}")

    def _add_ct_auction_fields(self):
        """Add fields needed for CT Statewide Auction and NJ auction data."""
        new_columns = [
            ('mileage', 'INTEGER'),
            ('car_number', 'TEXT' if not self.use_postgres else 'VARCHAR(50)'),
            ('auction_day', 'TEXT' if not self.use_postgres else 'VARCHAR(20)'),
            ('auction_time', 'TEXT' if not self.use_postgres else 'VARCHAR(50)'),
            ('auction_type', 'TEXT' if not self.use_postgres else 'VARCHAR(50)'),
            ('auction_schedule', 'TEXT' if not self.use_postgres else 'VARCHAR(200)'),
            ('bidding_deadline', 'TEXT' if not self.use_postgres else 'VARCHAR(100)'),
            ('results_posted', 'TEXT' if not self.use_postgres else 'VARCHAR(100)'),
            ('dealer_requirement', 'TEXT' if not self.use_postgres else 'VARCHAR(200)'),
            ('buy_it_now_price', 'REAL' if not self.use_postgres else 'DECIMAL(10,2)'),
            ('damage_type', 'TEXT' if not self.use_postgres else 'VARCHAR(100)'),
        ]

        with self.get_connection() as conn:
            for column_name, column_type in new_columns:
                try:
                    if self.use_postgres:
                        with conn.cursor() as cur:
                            cur.execute(f"ALTER TABLE lots ADD COLUMN {column_name} {column_type}")
                        conn.commit()
                    else:
                        conn.execute(f"ALTER TABLE lots ADD COLUMN {column_name} {column_type}")
                        conn.commit()
                    logger.info(f"Added column {column_name} to lots table")
                except Exception as e:
                    # Column probably already exists
                    logger.debug(f"Could not add column {column_name}: {e}")

    def upsert_lot(self, lot_data: Dict[str, Any]) -> bool:
        """Insert or update a lot record."""
        try:
            if not lot_data.get('source') or not lot_data.get('source_lot_id'):
                logger.warning(f"Missing required fields: {lot_data}")
                return False
            
            # Convert datetime strings for PostgreSQL
            if self.use_postgres and lot_data.get('sale_date_utc'):
                try:
                    # Ensure ISO format for PostgreSQL
                    if isinstance(lot_data['sale_date_utc'], str):
                        datetime.fromisoformat(lot_data['sale_date_utc'].replace('Z', '+00:00'))
                except ValueError:
                    lot_data['sale_date_utc'] = None
            
            lot_data['updated_at'] = datetime.utcnow().isoformat()
            
            with self.get_connection() as conn:
                if self.use_postgres:
                    return self._upsert_postgres(conn, lot_data)
                else:
                    return self._upsert_sqlite(conn, lot_data)
                    
        except Exception as e:
            logger.error(f"Failed to upsert lot: {e}")
            return False
    
    def _upsert_postgres(self, conn, lot_data: Dict[str, Any]) -> bool:
        """PostgreSQL upsert implementation."""
        with conn.cursor() as cur:
            columns = list(lot_data.keys())
            placeholders = ', '.join(['%s' for _ in columns])
            column_names = ', '.join(columns)
            
            # Create conflict resolution
            update_columns = [k for k in columns if k not in ('source', 'source_lot_id')]
            update_clause = ', '.join([f"{k} = EXCLUDED.{k}" for k in update_columns])
            
            query = f"""
                INSERT INTO lots ({column_names}) 
                VALUES ({placeholders})
                ON CONFLICT (source, source_lot_id) 
                DO UPDATE SET {update_clause}
            """
            
            cur.execute(query, list(lot_data.values()))
            conn.commit()
            logger.debug(f"Upserted lot: {lot_data['source']}/{lot_data['source_lot_id']}")
            return True
    
    def _upsert_sqlite(self, conn, lot_data: Dict[str, Any]) -> bool:
        """SQLite upsert implementation."""
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
    
    def get_lots(self, 
                 days_ahead: int = 14, 
                 make: Optional[str] = None,
                 state: Optional[str] = None,
                 title_status: Optional[str] = None) -> List[Dict]:
        """Get lots within specified criteria."""
        
        if self.use_postgres:
            query = """
                SELECT * FROM lots 
                WHERE (sale_date_utc >= %s AND sale_date_utc <= %s) 
                   OR sale_date_utc IS NULL
            """
            date_format = "%Y-%m-%dT%H:%M:%S"
        else:
            query = """
                SELECT * FROM lots 
                WHERE (sale_date_utc >= ? AND sale_date_utc <= ?) 
                   OR sale_date_utc IS NULL
            """
            date_format = "%Y-%m-%dT%H:%M:%S"
        
        params = [
            datetime.utcnow().strftime(date_format),
            (datetime.utcnow() + timedelta(days=days_ahead)).strftime(date_format)
        ]
        
        if make:
            query += " AND make ILIKE %s" if self.use_postgres else " AND make LIKE ?"
            params.append(f"%{make}%")
            
        if state:
            query += " AND location_state = %s" if self.use_postgres else " AND location_state = ?"
            params.append(state)
            
        if title_status and title_status != 'all':
            query += " AND title_status = %s" if self.use_postgres else " AND title_status = ?"
            params.append(title_status)
        
        query += " ORDER BY CASE WHEN sale_date_utc IS NULL THEN 1 ELSE 0 END, sale_date_utc ASC"
        
        try:
            with self.get_connection() as conn:
                if self.use_postgres:
                    with conn.cursor() as cur:
                        cur.execute(query, params)
                        return [dict(row) for row in cur.fetchall()]
                else:
                    cursor = conn.execute(query, params)
                    return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get lots: {e}")
            return []
    
    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        try:
            with self.get_connection() as conn:
                stats = {}
                
                if self.use_postgres:
                    with conn.cursor() as cur:
                        # Total lots
                        cur.execute("SELECT COUNT(*) as count FROM lots")
                        stats['total_lots'] = cur.fetchone()['count']
                        
                        # Lots by source
                        cur.execute("""
                            SELECT source, COUNT(*) as count 
                            FROM lots 
                            GROUP BY source 
                            ORDER BY count DESC
                        """)
                        stats['by_source'] = dict(cur.fetchall())
                        
                        # Upcoming lots
                        future_date = datetime.utcnow() + timedelta(days=14)
                        cur.execute("""
                            SELECT COUNT(*) as count 
                            FROM lots 
                            WHERE sale_date_utc >= %s AND sale_date_utc <= %s
                        """, [datetime.utcnow(), future_date])
                        stats['upcoming_lots'] = cur.fetchone()['count']
                else:
                    # SQLite version
                    cursor = conn.execute("SELECT COUNT(*) as count FROM lots")
                    stats['total_lots'] = cursor.fetchone()['count']
                    
                    cursor = conn.execute("""
                        SELECT source, COUNT(*) as count 
                        FROM lots 
                        GROUP BY source 
                        ORDER BY count DESC
                    """)
                    stats['by_source'] = dict(cursor.fetchall())
                    
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

# Compatibility wrapper to maintain existing API
class AuctionDB(DatabaseAdapter):
    """Backward compatibility wrapper."""
    
    def __init__(self, db_path: str = None):
        # Ignore db_path parameter, use config instead
        super().__init__()
    
    def get_target_matches(self, days_ahead: int = 14) -> List[Dict]:
        """Get lots that match our target vehicles only."""
        try:
            from .target_filter import target_filter
        except ImportError:
            logger.warning("Target filter not available, returning all lots")
            return self.get_lots(days_ahead=days_ahead)
        
        lots = self.get_lots(days_ahead=days_ahead)
        target_lots = target_filter.filter_target_lots(lots)
        
        logger.info(f"Found {len(target_lots)} target matches out of {len(lots)} total lots")
        return target_lots
    
    def cleanup_old_lots(self, days_old: int = 30):
        """Remove lots older than specified days."""
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        try:
            with self.get_connection() as conn:
                if self.use_postgres:
                    with conn.cursor() as cur:
                        cur.execute("DELETE FROM lots WHERE sale_date_utc < %s", [cutoff_date])
                        deleted_count = cur.rowcount
                    conn.commit()
                else:
                    cursor = conn.execute("DELETE FROM lots WHERE sale_date_utc < ?", [cutoff_date.isoformat()])
                    deleted_count = cursor.rowcount
                    conn.commit()
                    
                logger.info(f"Cleaned up {deleted_count} old lots")
                return deleted_count
        except Exception as e:
            logger.error(f"Failed to cleanup old lots: {e}")
            return 0
    
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