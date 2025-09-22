#!/usr/bin/env python3
"""Clean up auction data to remove duplicates, TBD entries, and improve quality."""

import sqlite3
import re
from datetime import datetime

def cleanup_database():
    """Clean up the auction database."""
    conn = sqlite3.connect('auction_radar.sqlite')
    cursor = conn.cursor()
    
    print("🧹 Cleaning up auction database...")
    
    # 1. Remove obvious non-vehicle entries
    non_vehicle_keywords = [
        'CRADLEPOINT', 'ELECTRIC STEAM', 'VOLRATH', 'LOT OF 15',
        'OFFICE', 'DESK', 'CHAIR', 'COMPUTER', 'MONITOR', 'PRINTER',
        'PLOTTER', 'EQUIPMENT', 'GENERATOR', 'MOWER'
    ]
    
    for keyword in non_vehicle_keywords:
        cursor.execute("""
            DELETE FROM lots 
            WHERE UPPER(raw_text) LIKE ? OR UPPER(condition_notes) LIKE ?
        """, (f'%{keyword}%', f'%{keyword}%'))
    
    deleted_non_vehicles = cursor.rowcount
    print(f"   Removed {deleted_non_vehicles} non-vehicle entries")
    
    # 2. Remove entries with no useful vehicle data
    cursor.execute("""
        DELETE FROM lots 
        WHERE (make IS NULL OR make = '') 
        AND (model IS NULL OR model = '') 
        AND (year IS NULL) 
        AND (vin IS NULL OR vin = '')
        AND source != 'nyc_finance'
    """)
    
    deleted_no_data = cursor.rowcount
    print(f"   Removed {deleted_no_data} entries with no vehicle data")
    
    # 3. Remove duplicates based on VIN (for NYC data)
    cursor.execute("""
        DELETE FROM lots 
        WHERE id NOT IN (
            SELECT MIN(id) 
            FROM lots 
            WHERE vin IS NOT NULL AND vin != '' 
            GROUP BY vin
        ) AND vin IS NOT NULL AND vin != ''
    """)
    
    deleted_vin_dupes = cursor.rowcount
    print(f"   Removed {deleted_vin_dupes} VIN duplicates")
    
    # 4. Remove duplicates based on source_lot_id
    cursor.execute("""
        DELETE FROM lots 
        WHERE id NOT IN (
            SELECT MIN(id) 
            FROM lots 
            GROUP BY source, source_lot_id
        )
    """)
    
    deleted_id_dupes = cursor.rowcount
    print(f"   Removed {deleted_id_dupes} source ID duplicates")
    
    # 5. Update entries with "Unknown Vehicle" to extract vehicle info from condition_notes
    cursor.execute("""
        SELECT id, condition_notes, raw_text 
        FROM lots 
        WHERE (make IS NULL OR make = '' OR make = 'Unknown')
        AND condition_notes IS NOT NULL
    """)
    
    updated_vehicles = 0
    for row in cursor.fetchall():
        lot_id, condition_notes, raw_text = row
        text_to_parse = f"{condition_notes} {raw_text or ''}"
        
        # Try to extract vehicle info
        year, make, model = extract_vehicle_info(text_to_parse)
        
        if year or make or model:
            cursor.execute("""
                UPDATE lots 
                SET year = ?, make = ?, model = ?
                WHERE id = ?
            """, (year, make, model, lot_id))
            updated_vehicles += 1
    
    print(f"   Updated {updated_vehicles} entries with extracted vehicle info")
    
    # 6. Remove entries with TBD sale dates and no useful info (except NYC which is good)
    cursor.execute("""
        DELETE FROM lots 
        WHERE sale_local_time IN ('TBD', 'Check Mass.gov for availability', 'Contact MA State Surplus Property Office')
        AND source != 'nyc_finance'
        AND (make IS NULL OR make = '' OR year IS NULL)
    """)
    
    deleted_tbd = cursor.rowcount
    print(f"   Removed {deleted_tbd} TBD entries with no useful data")
    
    # 7. Update location parsing for better city extraction
    cursor.execute("""
        UPDATE lots 
        SET location_city = TRIM(REPLACE(REPLACE(location_city, 'Bid(s):', ''), 'Current Bid:', ''))
        WHERE location_city LIKE '%Bid(s):%' OR location_city LIKE '%Current Bid:%'
    """)
    
    cleaned_locations = cursor.rowcount
    print(f"   Cleaned {cleaned_locations} location entries")
    
    conn.commit()
    
    # Show final stats
    cursor.execute("SELECT source, COUNT(*) as count FROM lots GROUP BY source ORDER BY count DESC")
    print("\n📊 Final data counts:")
    for source, count in cursor.fetchall():
        print(f"   {source}: {count}")
    
    cursor.execute("SELECT COUNT(*) FROM lots")
    total = cursor.fetchone()[0]
    print(f"\n✅ Total lots remaining: {total}")
    
    conn.close()

def extract_vehicle_info(text):
    """Extract year, make, model from text."""
    year, make, model = None, None, None
    
    # Common vehicle patterns
    patterns = [
        r'(\d{4})\s+(FORD|CHEVY|CHEVROLET|TOYOTA|HONDA|NISSAN|GMC|DODGE|JEEP|BUICK|CADILLAC|LINCOLN|AUDI|BMW|MERCEDES|VOLKSWAGEN|SUBARU|MAZDA|HYUNDAI|KIA|MITSUBISHI|ACURA|INFINITI|LEXUS)\s+([A-Z0-9\s\-]+)',
        r'(FORD|CHEVY|CHEVROLET|TOYOTA|HONDA|NISSAN|GMC|DODGE|JEEP|BUICK|CADILLAC|LINCOLN|AUDI|BMW|MERCEDES|VOLKSWAGEN|SUBARU|MAZDA|HYUNDAI|KIA|MITSUBISHI|ACURA|INFINITI|LEXUS)\s+([A-Z0-9\s\-]+)\s+(\d{4})',
        r'(\d{4})\s+(Ford|Chevy|Toyota|Honda|Nissan|GMC|Dodge)\s+([A-Za-z0-9\s\-]+)',
    ]
    
    text_upper = text.upper()
    
    for pattern in patterns:
        match = re.search(pattern, text_upper)
        if match:
            groups = match.groups()
            if groups[0].isdigit():  # Year first
                year = int(groups[0])
                make = groups[1].strip()
                model = groups[2].strip() if len(groups) > 2 else None
            elif len(groups) >= 3 and groups[2].isdigit():  # Year last
                make = groups[0].strip()
                model = groups[1].strip()
                year = int(groups[2])
            else:
                make = groups[0].strip() if len(groups) > 0 else None
                model = groups[1].strip() if len(groups) > 1 else None
            break
    
    # Clean up model
    if model:
        model = re.sub(r'\s+(TRUCK|VAN|CAR|VEHICLE|PICKUP).*$', '', model, flags=re.I).strip()
        model = model[:50]  # Limit length
    
    return year, make, model

if __name__ == '__main__':
    cleanup_database()