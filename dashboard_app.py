"""Streamlit dashboard for auction radar."""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import logging

# Configure streamlit page
st.set_page_config(
    page_title="Auction Radar Dashboard",
    page_icon="🚗",
    layout="wide"
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import auction radar modules
try:
    from auction_radar.config import config
    from auction_radar.db import AuctionDB
    from auction_radar.ranker import lot_ranker
    from auction_radar.keywords import keyword_matcher
except ImportError as e:
    st.error(f"Failed to import auction_radar modules: {e}")
    st.stop()

@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_auction_data(days_ahead, make_filter, state_filter, title_filter):
    """Load auction data with caching."""
    try:
        db = AuctionDB(config.AUCTION_DB)
        lots = db.get_lots(
            days_ahead=days_ahead,
            make=make_filter if make_filter != 'All' else None,
            state=state_filter if state_filter != 'All' else None,
            title_status=title_filter if title_filter != 'all' else None
        )
        return lots
    except Exception as e:
        logger.error(f"Error loading data: {e}")
        return []

@st.cache_data(ttl=300)
def get_target_matches(days_ahead):
    """Get target vehicle matches with caching."""
    try:
        db = AuctionDB(config.AUCTION_DB)
        target_lots = db.get_target_matches(days_ahead=days_ahead)
        ranked_lots = lot_ranker.rank_lots(target_lots)
        return ranked_lots
    except Exception as e:
        logger.error(f"Error getting target matches: {e}")
        return []

def main():
    """Main dashboard function."""
    
    st.title("🚗 Regional Tow Auction Radar")
    st.markdown("---")
    
    # Sidebar filters
    st.sidebar.header("Filters")
    
    # Date range filter
    days_ahead = st.sidebar.slider(
        "Days ahead to show",
        min_value=1,
        max_value=60,
        value=14,
        help="Show auctions within the next N days"
    )
    
    # Load initial data to get filter options
    initial_lots = load_auction_data(days_ahead, 'All', 'All', 'all')
    
    if not initial_lots:
        st.warning("No auction data available. Run `python -m auction_radar --crawl` to populate the database.")
        return
    
    # Get unique values for filters
    makes = ['All'] + sorted(list(set([lot.get('make', 'Unknown') for lot in initial_lots if lot.get('make')])))
    states = ['All'] + sorted(list(set([lot.get('location_state', 'Unknown') for lot in initial_lots if lot.get('location_state')])))
    title_statuses = ['all', 'clean', 'rebuilt', 'salvage', 'parts_only', 'unknown']
    
    # Filter controls
    make_filter = st.sidebar.selectbox("Make", makes)
    state_filter = st.sidebar.selectbox("State", states)
    title_filter = st.sidebar.selectbox("Title Status", title_statuses)
    
    # Target matches only toggle
    targets_only = st.sidebar.checkbox("Show target vehicles only", value=False)
    
    # Load filtered data
    if targets_only:
        lots = get_target_matches(days_ahead)
        # Apply additional filters to target matches
        if make_filter != 'All':
            lots = [lot for lot in lots if lot.get('make', '').lower() == make_filter.lower()]
        if state_filter != 'All':
            lots = [lot for lot in lots if lot.get('location_state', '') == state_filter]
        if title_filter != 'all':
            lots = [lot for lot in lots if lot.get('title_status', '') == title_filter]
    else:
        lots = load_auction_data(days_ahead, make_filter, state_filter, title_filter)
    
    # Stats overview
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Lots", len(lots))
    
    with col2:
        if targets_only or not lots:
            target_count = len(lots)
        else:
            target_lots = get_target_matches(days_ahead)
            target_count = len(target_lots)
        st.metric("Target Matches", target_count)
    
    with col3:
        states_count = len(set([lot.get('location_state', 'Unknown') for lot in lots]))
        st.metric("States", states_count)
    
    with col4:
        sources_count = len(set([lot.get('source', 'Unknown') for lot in lots]))
        st.metric("Sources", sources_count)
    
    # Top matches section
    if targets_only or st.sidebar.checkbox("Show top matches section"):
        st.header("🎯 Top Target Matches")
        
        target_lots = get_target_matches(days_ahead)
        
        if target_lots:
            # Show top 5 matches in columns
            top_matches = target_lots[:5]
            
            for i, lot in enumerate(top_matches):
                with st.container():
                    col1, col2 = st.columns([3, 1])
                    
                    with col1:
                        # Vehicle info
                        year = lot.get('year', 'Unknown')
                        make = lot.get('make', 'Unknown')
                        model = lot.get('model', 'Unknown')
                        
                        st.subheader(f"{year} {make} {model}")
                        
                        # Location and date
                        city = lot.get('location_city', 'Unknown')
                        state = lot.get('location_state', 'Unknown')
                        sale_time = lot.get('sale_local_time', 'TBD')
                        
                        st.write(f"📍 **Location:** {city}, {state}")
                        st.write(f"📅 **Sale Date:** {sale_time}")
                        
                        # Title and condition
                        title_status = lot.get('title_status', 'unknown').title()
                        condition = lot.get('condition_notes', '')
                        
                        st.write(f"📋 **Title:** {title_status}")
                        if condition:
                            st.write(f"⚠️ **Condition:** {condition}")
                        
                        # VIN if available
                        vin = lot.get('vin', '')
                        if vin:
                            st.write(f"🔢 **VIN:** {vin}")
                    
                    with col2:
                        # Score
                        score = lot.get('score', 0)
                        st.metric("Score", f"{score:.1f}")
                        
                        # Link
                        lot_url = lot.get('lot_url', '')
                        if lot_url and lot_url != '':
                            st.markdown(f"[View Lot]({lot_url})", unsafe_allow_html=True)
                        
                    st.markdown("---")
        else:
            st.info("No target matches found in the selected time period.")
    
    # Main data table
    st.header("📋 All Auction Lots")
    
    if lots:
        # Convert to DataFrame for better display
        df_data = []
        for lot in lots:
            row = {
                'Sale Date': lot.get('sale_local_time', 'TBD'),
                'Vehicle': f"{lot.get('year', '')} {lot.get('make', '')} {lot.get('model', '')}".strip(),
                'Location': f"{lot.get('location_city', '')}, {lot.get('location_state', '')}",
                'Title': lot.get('title_status', 'unknown').title(),
                'Source': lot.get('source', 'Unknown'),
                'VIN': lot.get('vin', ''),
                'Condition': lot.get('condition_notes', '')[:50] + ('...' if len(lot.get('condition_notes', '')) > 50 else ''),
                'URL': lot.get('lot_url', ''),
                'Score': lot.get('score', 0) if 'score' in lot else 'N/A'
            }
            df_data.append(row)
        
        df = pd.DataFrame(df_data)
        
        # Sort by score if available, otherwise by date
        if targets_only and 'Score' in df.columns:
            df = df.sort_values('Score', ascending=False)
        
        # Display with clickable URLs
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "URL": st.column_config.LinkColumn("Lot URL"),
                "Score": st.column_config.NumberColumn("Score", format="%.1f"),
            }
        )
        
        # Download CSV button
        csv_data = df.to_csv(index=False)
        st.download_button(
            label="Download CSV",
            data=csv_data,
            file_name=f"auction_radar_export_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv"
        )
    
    else:
        st.info("No lots found matching your criteria.")
    
    # Footer
    st.markdown("---")
    st.markdown("*Data refreshes every 5 minutes. Run `python -m auction_radar --crawl` to update.*")

if __name__ == '__main__':
    main()