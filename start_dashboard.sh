#!/bin/bash

# Start Auction Radar Dashboard
echo "🚗 Starting Northeast Auction Radar Dashboard..."

# Check if streamlit is installed
if ! command -v streamlit &> /dev/null; then
    echo "Installing Streamlit..."
    pip install streamlit pandas
fi

# Get local IP for network access
LOCAL_IP=$(ipconfig getifaddr en0 2>/dev/null || ip route get 1 | awk '{print $7; exit}' 2>/dev/null || echo "localhost")

echo "Starting dashboard..."
echo "📊 Local access: http://localhost:8501"
echo "🌐 Network access: http://$LOCAL_IP:8501"
echo "👥 Share the network URL with your team!"
echo ""

# Start the dashboard
streamlit run dashboard_app.py --server.address 0.0.0.0 --server.port 8501