"""Email digest functionality for auction radar."""

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Any
from datetime import datetime, timedelta
from .config import config
from .db import AuctionDB
from .ranker import lot_ranker

logger = logging.getLogger(__name__)

class EmailDigest:
    """Handles email digest generation and sending."""
    
    def __init__(self, db: AuctionDB):
        self.db = db
    
    def send_digest(self, days_ahead: int = 14) -> bool:
        """Send email digest of upcoming auctions."""
        
        # Get target matches for the next period
        target_lots = self.db.get_target_matches(days_ahead=days_ahead)
        
        # Rank and score the lots
        ranked_lots = lot_ranker.rank_lots(target_lots)
        
        # Generate digest content
        subject, body = self._generate_digest_content(ranked_lots, days_ahead)
        
        # Send email or print to console
        if config.EMAIL_ENABLED and config.EMAIL_TO:
            return self._send_email(subject, body)
        else:
            print("\n" + "="*80)
            print(f"EMAIL DIGEST - {subject}")
            print("="*80)
            print(body)
            print("="*80)
            return True
    
    def _generate_digest_content(self, lots: List[Dict[str, Any]], days_ahead: int) -> tuple[str, str]:
        """Generate email subject and body content."""
        
        if not lots:
            subject = f"Auction Radar - No Target Vehicles Found (Next {days_ahead} Days)"
            body = f"""
Auction Radar Weekly Digest

No target vehicles found in the next {days_ahead} days.

Target vehicles we're watching for:
• Lexus/Toyota Land Cruiser
• Toyota 4Runner, Tacoma, Tundra  
• Nissan Frontier, Titan
• Mini campers / RVs / towable trailers

The system will continue monitoring and will alert you when matches are found.
            """.strip()
            return subject, body
        
        subject = f"Auction Radar - {len(lots)} Target Vehicle{'s' if len(lots) != 1 else ''} Found!"
        
        # Generate body
        body_lines = [
            "Auction Radar Weekly Digest",
            f"Found {len(lots)} target vehicles in the next {days_ahead} days:",
            "",
            "🎯 TOP MATCHES:",
            ""
        ]
        
        # Show top 10 matches
        top_lots = lots[:10]
        
        for i, lot in enumerate(top_lots, 1):
            # Format vehicle info
            year = lot.get('year') or 'Unknown'
            make = lot.get('make') or 'Unknown'
            model = lot.get('model') or 'Unknown'
            
            # Format location
            city = lot.get('location_city') or 'Unknown'
            state = lot.get('location_state') or 'Unknown'
            
            # Format date
            sale_local = lot.get('sale_local_time') or 'TBD'
            
            # Format title/condition
            title_status = lot.get('title_status', 'unknown').title()
            condition = lot.get('condition_notes', '')
            condition_str = f" - {condition}" if condition else ""
            
            # Format score
            score = lot.get('score', 0)
            score_str = f" (Score: {score:.1f})"
            
            # Format URL
            url = lot.get('lot_url', 'N/A')
            
            body_lines.extend([
                f"{i}. {year} {make} {model}{score_str}",
                f"   📍 {city}, {state}",
                f"   📅 {sale_local}",
                f"   📋 {title_status}{condition_str}",
                f"   🔗 {url}",
                ""
            ])
        
        # Add summary stats if more than 10
        if len(lots) > 10:
            body_lines.extend([
                f"... and {len(lots) - 10} more matches",
                ""
            ])
        
        # Add breakdown by category
        category_counts = {}
        for lot in lots:
            from .keywords import keyword_matcher
            search_text = f"{lot.get('make', '')} {lot.get('model', '')} {lot.get('raw_text', '')}"
            best_match = keyword_matcher.get_best_match(search_text)
            if best_match:
                category_counts[best_match.category] = category_counts.get(best_match.category, 0) + 1
        
        if category_counts:
            body_lines.extend([
                "📊 BREAKDOWN BY CATEGORY:",
                ""
            ])
            
            category_names = {
                'land_cruiser': 'Land Cruiser',
                'fourrunner': '4Runner', 
                'tacoma': 'Tacoma',
                'tundra': 'Tundra',
                'frontier': 'Frontier',
                'titan': 'Titan',
                'campers_rvs': 'Campers/RVs'
            }
            
            for category, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
                name = category_names.get(category, category.title())
                body_lines.append(f"   {name}: {count}")
            
            body_lines.append("")
        
        # Add footer
        body_lines.extend([
            "---",
            f"Generated by Auction Radar on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}",
            "Visit the dashboard for full details and filters.",
        ])
        
        body = "\n".join(body_lines)
        return subject, body
    
    def _send_email(self, subject: str, body: str) -> bool:
        """Send email via SMTP."""
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = f"{config.EMAIL_FROM_NAME} <{config.EMAIL_USER}>"
            msg['To'] = ', '.join(config.EMAIL_TO)
            msg['Subject'] = subject
            
            # Attach body
            msg.attach(MIMEText(body, 'plain'))
            
            # Connect to server and send
            with smtplib.SMTP(config.EMAIL_SMTP_HOST, config.EMAIL_SMTP_PORT) as server:
                server.starttls()
                server.login(config.EMAIL_USER, config.EMAIL_PASS)
                
                for recipient in config.EMAIL_TO:
                    server.send_message(msg, to_addrs=[recipient])
            
            logger.info(f"Email digest sent successfully to {len(config.EMAIL_TO)} recipients")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email digest: {e}")
            return False