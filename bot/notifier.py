"""
Notifier Module.
Formats and sends Decision Cards to Telegram.
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
    Currently sync to run in BackgroundTasks easily.
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
            # Trade Details (Placeholder for real entry calculation)
            # In Phase 2 P1 we just show the signal, execution is Phase 3
            lines.append(f"Reason: {result.reason}")
            lines.append(f"P-Score: {result.pscore.score}")
            lines.append(f"Kevlar: PASSED")
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
