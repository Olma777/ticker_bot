"""
Notifier Module.
Formats and sends Decision Cards to Telegram.
Updated for P1-FIX-04 Risk Transparency.
"""

import logging
import html
import requests

from bot.config import Config
from bot.decision_models import DecisionResult

logger = logging.getLogger("DecisionEngine-Notifier")


def send_decision_card(result: DecisionResult, event: dict):
    """
    Send formatted decision card to Telegram using requests (Sync).
    Includes Risk Transparency (P1-FIX-04).
    """
    if not Config.TELEGRAM_TOKEN or not Config.TELEGRAM_CHAT_ID:
        return

    try:
        # Prepare Data
        symbol = html.escape(event.get('symbol', 'Unknown'))
        tf = html.escape(event.get('tf', '30m'))
        event_type = html.escape(event.get('event', 'SIGNAL'))
        
        # Emoji Logic
        if result.decision == "TRADE":
            icon = "✅" 
            header = f"<b>DECISION: {result.decision} {icon} ({result.side})</b>"
        else:
            icon = "❌"
            header = f"<b>DECISION: {result.decision} {icon}</b>"

        # Body Construction
        lines = [header, ""]
        lines.append(f"Symbol: <code>{symbol}</code> ({tf})")
        lines.append(f"Event: {event_type}")
        
        if result.decision == "TRADE":
            # Trade Details + Risk (P1-FIX-04)
            lines.append(f"Reason: {result.reason}")
            lines.append(f"P-Score: {result.pscore.score}")
            lines.append(f"Kevlar: PASSED")
            
            if result.risk:
                r = result.risk
                lines.append("")
                lines.append("<b>Risk Analysis:</b>")
                lines.append(f"• Entry: {r.entry_price:.4f}")
                lines.append(f"• Stop: {r.stop_loss:.4f} ({r.stop_dist_pct:.2f}%)")
                lines.append(f"• Risk: ${r.risk_amount:.2f}")
                lines.append(f"• Size: {r.position_size:.4f} {symbol.split('/')[0]}")
                lines.append(f"• Lev: {r.leverage:.2f}x")
                if not r.fee_included:
                    lines.append("<i>(Fees not included)</i>")
        else:
            # Wait Details
            lines.append(f"Reason: {result.reason}")
            lines.append(f"P-Score: {result.pscore.score} / {Config.P_SCORE_THRESHOLD}")
            
            if not result.kevlar.passed:
                lines.append(f"Kevlar Block: <code>{result.kevlar.blocked_by}</code>")

        # Breakdown (Optional, debug for now)
        # lines.append("")
        # lines.append("<i>Score Breakdown:</i>")
        # for factor in result.pscore.breakdown:
        #     lines.append(f"• {factor}")

        message = "\n".join(lines)
        
        # Send
        url = f"https://api.telegram.org/bot{Config.TELEGRAM_TOKEN}/sendMessage"
        data = {
            "chat_id": Config.TELEGRAM_CHAT_ID, 
            "text": message, 
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        
        resp = requests.post(url, json=data, timeout=5.0)
        if resp.status_code != 200:
            logger.error(f"TG Error {resp.status_code}: {resp.text}")

    except Exception as e:
        logger.error(f"Notifier Error: {e}")
