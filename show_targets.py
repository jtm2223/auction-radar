#!/usr/bin/env python3
"""Show the best target vehicle matches."""

import sqlite3
from auction_radar.keywords import keyword_matcher
from auction_radar.ranker import lot_ranker

def show_target_matches():
    """Show the best target vehicle matches with scores."""
    conn = sqlite3.connect('auction_radar.sqlite')
    cursor = conn.cursor()
    
    # Get all lots
    cursor.execute("""
        SELECT source, make, model, year, location_city, location_state, 
               sale_local_time, condition_notes, lot_url, raw_text
        FROM lots 
        WHERE make IS NOT NULL AND model IS NOT NULL
        ORDER BY sale_local_time
    """)
    
    lots = []
    for row in cursor.fetchall():
        lot = {
            'source': row[0],
            'make': row[1],
            'model': row[2], 
            'year': row[3],
            'location_city': row[4],
            'location_state': row[5],
            'sale_local_time': row[6],
            'condition_notes': row[7],
            'lot_url': row[8],
            'raw_text': row[9]
        }
        lots.append(lot)
    
    # Find target matches
    target_lots = []
    for lot in lots:
        text_to_search = f"{lot.get('make', '')} {lot.get('model', '')} {lot.get('condition_notes', '')} {lot.get('raw_text', '')}"
        if keyword_matcher.has_target_match(text_to_search):
            target_lots.append(lot)
    
    # Rank the target lots
    ranked_lots = lot_ranker.rank_lots(target_lots)
    
    print(f"\n🎯 TOP {min(10, len(ranked_lots))} TARGET VEHICLE MATCHES")
    print("=" * 80)
    
    for i, lot in enumerate(ranked_lots[:10], 1):
        score = lot.get('score', 0)
        year = lot.get('year', 'Unknown')
        make = lot.get('make', 'Unknown')
        model = lot.get('model', 'Unknown')
        city = lot.get('location_city', 'Unknown')
        state = lot.get('location_state', 'Unknown')
        sale_time = lot.get('sale_local_time', 'TBD')
        
        print(f"\n{i}. {year} {make} {model} (Score: {score:.1f})")
        print(f"   📍 Location: {city}, {state}")
        print(f"   📅 Sale: {sale_time}")
        if lot.get('lot_url'):
            print(f"   🔗 {lot['lot_url']}")
    
    print(f"\n📊 SUMMARY:")
    print(f"   • Total lots: {len(lots)}")
    print(f"   • Target matches: {len(target_lots)}")
    print(f"   • Top matches shown: {min(10, len(ranked_lots))}")
    
    conn.close()

if __name__ == '__main__':
    show_target_matches()