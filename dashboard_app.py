"""Streamlit dashboard for auction radar."""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import logging
import time
import os

# Configure streamlit page
st.set_page_config(
    page_title="Auction Radar Dashboard",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
.main > div {
    padding-top: 2rem;
}

.stMetric {
    background-color: #f0f2f6;
    padding: 1rem;
    border-radius: 0.5rem;
    border-left: 4px solid #ff6b6b;
}

.target-match {
    background-color: #f8f9ff;
    padding: 1.5rem;
    border-radius: 0.8rem;
    border: 1px solid #e0e7ff;
    margin: 1rem 0;
}

.vehicle-title {
    color: #1f2937;
    font-weight: 600;
    font-size: 1.25rem;
    margin-bottom: 0.5rem;
}

.info-item {
    margin: 0.25rem 0;
    color: #4b5563;
}

.score-badge {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 0.5rem 1rem;
    border-radius: 2rem;
    text-align: center;
    font-weight: bold;
}

.sidebar .sidebar-content {
    background-color: #fafafa;
}

h1 {
    color: #1f2937;
    border-bottom: 3px solid #ff6b6b;
    padding-bottom: 0.5rem;
}

.stAlert {
    border-radius: 0.5rem;
}

.dataframe {
    font-size: 0.9rem;
}

.stButton > button {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    border: none;
    border-radius: 0.5rem;
    padding: 0.5rem 2rem;
    font-weight: 500;
}

.stButton > button:hover {
    background: linear-gradient(135deg, #5a67d8 0%, #6b46c1 100%);
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}
</style>
""", unsafe_allow_html=True)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import auction radar modules
try:
    from auction_radar.config import config
    from auction_radar.db_adapter import AuctionDB
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
        logger.info(f"Loaded {len(lots)} lots from database")
        return lots
    except Exception as e:
        logger.error(f"Error loading data: {e}")
        st.error(f"Database error: {e}")
        return []

@st.cache_data(ttl=300)
def get_target_matches(days_ahead):
    """Get target vehicle matches with caching."""
    try:
        db = AuctionDB(config.AUCTION_DB)
        target_lots = db.get_target_matches(days_ahead=days_ahead)
        ranked_lots = lot_ranker.rank_lots(target_lots)
        logger.info(f"Found {len(ranked_lots)} target matches")
        return ranked_lots
    except Exception as e:
        logger.error(f"Error getting target matches: {e}")
        st.error(f"Error loading target matches: {e}")
        return []

def main():
    """Main dashboard function."""

    # Auto-refresh controls at the top
    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        st.markdown("### 🚗 Regional Tow Auction Radar")

    with col2:
        auto_refresh = st.checkbox("🔄 Auto-refresh", value=False, help="Refresh data every 30 seconds")

    with col3:
        if st.button("🔄 Refresh Now", help="Manually refresh data"):
            st.cache_data.clear()
            st.rerun()

    # Auto-refresh mechanism
    if auto_refresh:
        placeholder = st.empty()
        placeholder.text("⏱️ Auto-refreshing in 30 seconds...")
        time.sleep(30)
        st.cache_data.clear()
        st.rerun()

    # Last updated info
    st.markdown(f"**Last Updated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Header with improved styling
    st.markdown("""
    <div style='text-align: center; margin-bottom: 2rem;'>
        <h2 style='color: #1f2937; font-size: 2rem; margin-bottom: 0.5rem;'>
            Northeast State Surplus Auctions
        </h2>
        <p style='color: #6b7280; font-size: 1.1rem; margin: 0;'>
            Track vehicle auctions across NY, CT, MA, RI, NJ
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Sidebar filters with improved styling
    st.sidebar.markdown("""
    <div style='text-align: center; margin-bottom: 1.5rem;'>
        <h2 style='color: #374151; margin-bottom: 0.5rem;'>🎯 Filters</h2>
        <p style='color: #6b7280; font-size: 0.9rem; margin: 0;'>Customize your search</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Date range filter
    days_ahead = st.sidebar.slider(
        "Days ahead to show",
        min_value=1,
        max_value=60,
        value=14,
        help="Show auctions within the next N days"
    )
    
    # Load initial data to get filter options
    with st.spinner("Loading auction data..."):
        initial_lots = load_auction_data(days_ahead, 'All', 'All', 'all')
    
    if not initial_lots:
        st.warning("""
        ### 📭 No auction data available

        The database is empty. Click the button below to crawl auction sources and populate the database with target vehicles.
        """)

        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button("🔍 Crawl Auction Sources", type="primary", help="This will fetch target vehicles from all auction sources"):
                with st.spinner("Crawling auction sources for target vehicles... This may take 2-3 minutes."):
                    try:
                        # Import and run the crawler
                        from auction_radar.sources import get_all_scrapers
                        from auction_radar.target_filter import target_filter

                        scrapers = get_all_scrapers()
                        total_targets = 0

                        progress_bar = st.progress(0)
                        status_text = st.empty()

                        for i, scraper in enumerate(scrapers):
                            status_text.text(f"Crawling {scraper.source_name}...")
                            progress_bar.progress((i) / len(scrapers))

                            try:
                                raw_lots = scraper.crawl()
                                source_targets = 0

                                for raw_lot in raw_lots:
                                    if target_filter.is_target_vehicle(raw_lot):
                                        db = AuctionDB(config.AUCTION_DB)
                                        if db.upsert_lot(raw_lot):
                                            source_targets += 1

                                total_targets += source_targets
                                logger.info(f"Found {source_targets} target vehicles from {scraper.source_name}")

                            except Exception as e:
                                logger.error(f"Error crawling {scraper.source_name}: {e}")
                                continue

                        progress_bar.progress(1.0)
                        status_text.text("Crawling complete!")

                        if total_targets > 0:
                            st.success(f"✅ Successfully found {total_targets} target vehicles! Refreshing dashboard...")
                            time.sleep(2)
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.info("No target vehicles found in current auctions. Try again later or check different sources.")

                    except Exception as e:
                        st.error(f"Error during crawling: {e}")
                        logger.error(f"Crawler error: {e}")

        st.info("💡 The crawler only saves target vehicles (Toyota 4Runner, Land Cruiser, Tacoma 4x4, etc.) to keep the database focused.")
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
    with st.spinner("Applying filters and loading data..."):
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
    
    # Stats overview with improved styling
    st.markdown("### 📊 Overview")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown("""
        <div class='stMetric'>
            <div style='font-size: 2rem; font-weight: bold; color: #1f2937;'>{}</div>
            <div style='color: #6b7280; font-size: 0.9rem;'>Total Lots</div>
        </div>
        """.format(len(lots)), unsafe_allow_html=True)
    
    with col2:
        if targets_only or not lots:
            target_count = len(lots)
        else:
            target_lots = get_target_matches(days_ahead)
            target_count = len(target_lots)
        st.markdown("""
        <div class='stMetric'>
            <div style='font-size: 2rem; font-weight: bold; color: #ef4444;'>{}</div>
            <div style='color: #6b7280; font-size: 0.9rem;'>Target Matches</div>
        </div>
        """.format(target_count), unsafe_allow_html=True)
    
    with col3:
        states_count = len(set([lot.get('location_state', 'Unknown') for lot in lots]))
        st.markdown("""
        <div class='stMetric'>
            <div style='font-size: 2rem; font-weight: bold; color: #10b981;'>{}</div>
            <div style='color: #6b7280; font-size: 0.9rem;'>States</div>
        </div>
        """.format(states_count), unsafe_allow_html=True)
    
    with col4:
        sources_count = len(set([lot.get('source', 'Unknown') for lot in lots]))
        st.markdown("""
        <div class='stMetric'>
            <div style='font-size: 2rem; font-weight: bold; color: #3b82f6;'>{}</div>
            <div style='color: #6b7280; font-size: 0.9rem;'>Sources</div>
        </div>
        """.format(sources_count), unsafe_allow_html=True)
    
    # Top matches section
    if targets_only or st.sidebar.checkbox("Show top matches section", value=True):
        st.markdown("""
        <div style='margin: 2rem 0;'>
            <h2 style='color: #1f2937; font-size: 1.8rem; margin-bottom: 1rem;'>🎯 Top Target Matches</h2>
            <p style='color: #6b7280; margin-bottom: 1.5rem;'>High-value vehicles matching your search criteria</p>
        </div>
        """, unsafe_allow_html=True)
        
        with st.spinner("Loading target matches..."):
            target_lots = get_target_matches(days_ahead)
        
        if target_lots:
            # Show top 5 matches in columns
            top_matches = target_lots[:5]
            
            for i, lot in enumerate(top_matches):
                # Vehicle info
                year = lot.get('year', 'Unknown')
                make = lot.get('make', 'Unknown')
                model = lot.get('model', 'Unknown')
                
                # Location and date
                city = lot.get('location_city', 'Unknown')
                state = lot.get('location_state', 'Unknown')
                sale_time = lot.get('sale_local_time', 'TBD')
                
                # Title and condition
                title_status = lot.get('title_status', 'unknown').title()
                condition = lot.get('condition_notes', '')
                
                # VIN if available
                vin = lot.get('vin', '')
                vin_display = f"...{vin[-8:]}" if vin else "Not available"
                
                # Show VIN-decoded specs if available
                specs = []
                if lot.get('body_class'):
                    specs.append(f"Body: {lot.get('body_class')}")
                if lot.get('fuel_type'):
                    specs.append(f"Fuel: {lot.get('fuel_type')}")
                if lot.get('vin_engine_cylinders'):
                    specs.append(f"Engine: {lot.get('vin_engine_cylinders')} cyl")
                if lot.get('vin_transmission'):
                    specs.append(f"Trans: {lot.get('vin_transmission')}")
                
                specs_text = ', '.join(specs) if specs else "No specs available"
                
                # Score and link
                score = lot.get('score', 0)
                lot_url = lot.get('lot_url', '')
                view_link = f"<a href='{lot_url}' target='_blank' style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 0.5rem 1rem; border-radius: 0.5rem; text-decoration: none; font-weight: 500;'>View Lot →</a>" if lot_url else "<span style='color: #9ca3af;'>No link available</span>"
                
                st.markdown(f"""
                <div class='target-match'>
                    <div style='display: flex; justify-content: between; align-items: flex-start;'>
                        <div style='flex: 1;'>
                            <h3 class='vehicle-title'>{year} {make} {model}</h3>
                            <div class='info-item'>📍 <strong>Location:</strong> {city}, {state}</div>
                            <div class='info-item'>📅 <strong>Sale Date:</strong> {sale_time}</div>
                            <div class='info-item'>📋 <strong>Title:</strong> {title_status}</div>
                            <div class='info-item'>🔢 <strong>VIN:</strong> {vin_display}</div>
                            <div class='info-item'>🔧 <strong>Specs:</strong> {specs_text}</div>
                            {f"<div class='info-item'>⚠️ <strong>Condition:</strong> {condition[:100]}{'...' if len(condition) > 100 else ''}</div>" if condition else ""}
                        </div>
                        <div style='text-align: center; margin-left: 1rem;'>
                            <div class='score-badge'>
                                <div style='font-size: 1.5rem;'>{score:.1f}</div>
                                <div style='font-size: 0.8rem;'>SCORE</div>
                            </div>
                            <div style='margin-top: 1rem;'>{view_link}</div>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style='text-align: center; padding: 2rem; background-color: #f9fafb; border-radius: 0.8rem; margin: 1rem 0;'>
                <h3 style='color: #6b7280; margin-bottom: 0.5rem;'>🔍 No target matches found</h3>
                <p style='color: #9ca3af; margin: 0;'>Try adjusting your filters or check back later for new listings.</p>
            </div>
            """, unsafe_allow_html=True)
    
    # Main data table
    st.markdown("""
    <div style='margin: 2rem 0 1rem 0;'>
        <h2 style='color: #1f2937; font-size: 1.8rem; margin-bottom: 0.5rem;'>📋 All Auction Lots</h2>
        <p style='color: #6b7280; margin-bottom: 1.5rem;'>Complete listing of available vehicles</p>
    </div>
    """, unsafe_allow_html=True)
    
    if lots:
        # Convert to DataFrame for better display
        df_data = []
        for lot in lots:
            # Build enhanced vehicle description
            vehicle_parts = []
            if lot.get('year'):
                vehicle_parts.append(str(lot['year']))
            if lot.get('make'):
                vehicle_parts.append(lot['make'])
            if lot.get('model'):
                vehicle_parts.append(lot['model'])
            
            vehicle_desc = ' '.join(vehicle_parts) if vehicle_parts else 'Unknown Vehicle'
            
            # Add VIN-decoded specs for display
            specs = []
            if lot.get('vin_body_class'):
                specs.append(lot['vin_body_class'])
            elif lot.get('body_class'):
                specs.append(lot['body_class'])
            if lot.get('vin_fuel_type'):
                specs.append(f"{lot['vin_fuel_type']} fuel")
                
            specs_text = f" ({', '.join(specs)})" if specs else ""
            
            row = {
                'Sale Date': lot.get('sale_local_time', 'TBD'),
                'Vehicle': vehicle_desc + specs_text,
                'Location': f"{lot.get('location_city', '')}, {lot.get('location_state', '')}",
                'Title': lot.get('title_status', 'unknown').title(),
                'Source': lot.get('source', 'Unknown'),
                'VIN': lot.get('vin', '')[-8:] if lot.get('vin') else '',  # Show last 8 digits
                'Condition': (lot.get('condition_notes') or '')[:50] + ('...' if len(lot.get('condition_notes') or '') > 50 else ''),
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
        st.markdown("""
        <div style='text-align: center; padding: 2rem; background-color: #fef3c7; border-radius: 0.8rem; margin: 1rem 0;'>
            <h3 style='color: #92400e; margin-bottom: 0.5rem;'>📭 No lots found</h3>
            <p style='color: #b45309; margin: 0;'>No vehicles match your current filter criteria. Try adjusting your filters above.</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Deployment info and footer
    with st.expander("🌐 Share Dashboard"):
        st.markdown("""
        **Deploy this dashboard for your team:**
        1. **Streamlit Cloud (Recommended)**:
           ```bash
           # Push to GitHub, then connect to streamlit.io
           git add . && git commit -m "Dashboard ready"
           git push origin main
           ```
           Then visit [share.streamlit.io](https://share.streamlit.io) to deploy

        2. **Local Network Access**:
           ```bash
           streamlit run dashboard_app.py --server.address 0.0.0.0 --server.port 8501
           ```
           Access at `http://[your-ip]:8501`

        3. **Cloud Deployment**:
           - Deploy to Heroku, Railway, or DigitalOcean
           - Set up automated crawling with cron jobs
        """)

    # Footer
    st.markdown("""
    <div style='margin-top: 3rem; padding: 2rem; background-color: #f9fafb; border-radius: 0.8rem; text-align: center;'>
        <p style='color: #6b7280; margin: 0; font-size: 0.9rem;'>
            🔄 Auto-refresh enabled •
            📊 Live data from 12+ auction sources •
            🚗 Northeast Auction Radar v2.0
        </p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == '__main__':
    main()