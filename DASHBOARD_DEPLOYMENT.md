# 🚗 Northeast Auction Radar - Live Dashboard Deployment

## Quick Start (Local Network)

**For immediate team access:**

1. **Start the dashboard:**
   ```bash
   ./start_dashboard.sh
   ```
   Or manually:
   ```bash
   streamlit run dashboard_app.py --server.address 0.0.0.0 --server.port 8501
   ```

2. **Share with your team:**
   - **Local access:** http://localhost:8501
   - **Network access:** http://[your-ip]:8501
   - Your dad and partners can access via your computer's IP address

## Cloud Deployment Options

### 🌟 Option 1: Streamlit Cloud (Recommended - FREE)

**Best for: Easy sharing with anyone, anywhere**

1. **Push to GitHub:**
   ```bash
   git add .
   git commit -m "Dashboard ready for deployment"
   git push origin main
   ```

2. **Deploy:**
   - Visit [share.streamlit.io](https://share.streamlit.io)
   - Connect your GitHub account
   - Select this repository
   - Set main file: `dashboard_app.py`
   - Click "Deploy"

3. **Result:**
   - Get a public URL like: `https://auction-radar.streamlit.app`
   - Share this URL with anyone
   - Auto-updates when you push to GitHub

### 🔧 Option 2: Cloud Server (VPS)

**Best for: Custom domain, more control**

1. **Deploy to DigitalOcean/Linode/AWS:**
   ```bash
   # On your server
   git clone [your-repo]
   cd Auctions
   pip install -r requirements_dashboard.txt

   # Install system service for auto-restart
   sudo nano /etc/systemd/system/auction-dashboard.service
   ```

2. **System service file:**
   ```ini
   [Unit]
   Description=Auction Radar Dashboard
   After=network.target

   [Service]
   Type=simple
   User=ubuntu
   WorkingDirectory=/home/ubuntu/Auctions
   ExecStart=/usr/bin/python3 -m streamlit run dashboard_app.py --server.address 0.0.0.0 --server.port 8501
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```

3. **Start service:**
   ```bash
   sudo systemctl enable auction-dashboard
   sudo systemctl start auction-dashboard
   ```

### 🚀 Option 3: Railway/Heroku (Easy Cloud)

**Best for: Simple cloud deployment**

1. **Railway:**
   - Connect GitHub at [railway.app](https://railway.app)
   - Select repository
   - Add environment variables if needed
   - Deploy automatically

2. **Heroku:**
   - Create `Procfile`:
     ```
     web: streamlit run dashboard_app.py --server.address 0.0.0.0 --server.port $PORT
     ```
   - Deploy via Heroku CLI or GitHub integration

## Features Included

✅ **Auto-refresh**: Updates every 30 seconds when enabled
✅ **State filtering**: Filter by NY, CT, MA, RI, NJ
✅ **Live data**: Shows current auction listings
✅ **CSV export**: Download data for analysis
✅ **Mobile friendly**: Works on phones/tablets
✅ **Target vehicle focus**: Highlights high-value matches

## Automated Data Updates

To keep data fresh, set up automated crawling:

```bash
# Add to crontab (crontab -e)
# Run every 30 minutes
*/30 * * * * cd /path/to/Auctions && python -m auction_radar --crawl

# Or use the dashboard's built-in auto-refresh
```

## Access Control

**For business use, consider:**
- Password protection with Streamlit auth
- VPN access for sensitive data
- Custom domain for professional appearance

## Troubleshooting

**Dashboard won't start:**
```bash
pip install streamlit pandas
```

**Network access issues:**
- Check firewall settings
- Ensure port 8501 is open
- Use correct IP address

**Data not updating:**
- Run manual crawl: `python -m auction_radar --crawl`
- Check database permissions
- Enable auto-refresh in dashboard

## Support

- Dashboard runs on Streamlit
- Data from 12+ auction sources
- Northeast coverage: NY, CT, MA, RI, NJ
- Real-time vehicle auction tracking