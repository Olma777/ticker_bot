"""
Notifier Module.
Formats and sends Decision Cards to Telegram.
Strictly implements Reference Template (P1-FIX).
"""

import logging
import html
import requests
from datetime import datetime, timezone

from bot.config import Config
from bot.decision_models import DecisionResult

logger = logging.getLogger("DecisionEngine-Notifier")


def send_decision_card(result: DecisionResult, event: dict):
    """
    Send strictly formatted Decision Card.
    """
    if not Config.TELEGRAM_TOKEN or not Config.TELEGRAM_CHAT_ID:
        return

    try:
        # Data Prep
        symbol = html.escape(event.get('symbol', 'Unknown'))
        tf = html.escape(event.get('tf', '30m'))
        event_str = html.escape(event.get('event', 'SIGNAL'))
        bar_time_ts = event.get('bar_time', 0)
        bar_time_str = datetime.fromtimestamp(bar_time_ts, tz=timezone.utc).strftime('%H:%M:%S')
        current_price = result.market_context.price if result.market_context else event.get('close', 0)
        
        level_price = event.get('level', 0.0)
        zone_half = event.get('zone_half', 0.0)
        sc = event.get('score', 0.0)
        touches = event.get('touches', 0)
        
        level_side = "SUPPORT" if "SUPPORT" in event_str else "RESISTANCE"
        if result.level_grade:
             grade_str = result.level_grade.grade
        else:
             grade_str = "N/A"

        # P-Score Breakdown
        breakdown_text = "\n".join(result.pscore.breakdown)
        
        # Market/Sentiment
        if result.market_context:
            m = result.market_context
            rsi_val = f"{m.rsi:.1f}"
            vwap_val = f"{m.vwap:.2f}"
            atr_val = f"{m.atr:.2f}"
            vs_vwap = "ABOVE" if m.price > m.vwap else "BELOW"
            dq_market = m.data_quality
        else:
            rsi_val = "N/A"
            vwap_val = "N/A"
            atr_val = "N/A"
            vs_vwap = "N/A"
            dq_market = "N/A"
            
        if result.sentiment_context:
            s = result.sentiment_context
            fund_val = f"{s.funding:.4f}%" if s.funding is not None else "N/A"
            oi_val = f"{s.open_interest:.2f}" if s.open_interest is not None else "N/A"
            dq_sent = s.data_quality
        else:
            fund_val = "N/A"
            oi_val = "N/A"
            dq_sent = "N/A"

        # --- Template Construction ---
        
        lines = []
        
        # Header
        lines.append(f"📊 <b>{symbol} | {tf} SNIPER</b>")
        lines.append(f"🕒 Event: {event_str} | bar_time: {bar_time_str}")
        lines.append(f"💰 Price: {current_price}")
        lines.append("")

        # Decision Block
        if result.decision == "TRADE":
            lines.append(f"<b>DECISION: TRADE ✅ ({result.side})</b>")
            lines.append(f"Entry Mode: {result.entry_mode}")
            lines.append("")
            
            if result.risk:
                r = result.risk
                lines.append(f"Entry: {r.entry_price:.4f}")
                lines.append(f"SL: {r.stop_loss:.4f}  (StopDist={r.stop_dist:.4f} | Risk=${r.risk_amount:.2f})")
                lines.append(f"TP1: {r.tp1:.4f} | TP2: {r.tp2:.4f} | TP3: {r.tp3:.4f}")
                lines.append(f"Size: {r.position_size:.4f}")
                lines.append(f"RRR (to TP2): {r.rrr_tp2:.2f}")
            
            lines.append("")
            lines.append(f"<b>P-SCORE: {result.pscore.score}/{Config.P_SCORE_THRESHOLD}</b>")
            lines.append("Breakdown:")
            lines.append(f"<pre>{breakdown_text}</pre>")
            lines.append("")
            lines.append("Kevlar: PASSED ✅")

        elif result.decision == "WAIT":
            icon = "❌"
            if not result.kevlar.passed:
                lines.append(f"<b>DECISION: WAIT {icon}</b>")
                lines.append(f"Blocked by Kevlar: {result.kevlar.blocked_by}")
            else:
                lines.append(f"<b>DECISION: WAIT {icon}</b>")
                lines.append(f"Reason: {result.reason}")

            lines.append("")
            lines.append(f"<b>P-SCORE: {result.pscore.score}/{Config.P_SCORE_THRESHOLD}</b>")
            lines.append("Breakdown:")
            lines.append(f"<pre>{breakdown_text}</pre>")

        # Level Info
        lines.append("")
        lines.append("<b>Level:</b>")
        lines.append(f"• Type: {level_side} | Level: {level_price} | Zone: ±{zone_half}")
        lines.append(f"• sc={sc} → grade={grade_str} | touches={touches}")

        # Market Context
        lines.append("")
        lines.append("<b>Market:</b>")
        lines.append(f"• ATR={atr_val} | RSI={rsi_val}")
        lines.append(f"• VWAP={vwap_val} | Price vs VWAP: {vs_vwap}")
        
        # Sentiment
        lines.append("<b>Sentiment:</b>")
        lines.append(f"• Funding={fund_val} | OI={oi_val}")
        lines.append(f"Data Quality: {dq_market}/{dq_sent}")
        
        # Cancel rules (Static for P1)
        if result.decision == "TRADE":
             missed_entry_mult = getattr(Config, 'KEVLAR_MISSED_ENTRY_ATR_MULT', 1.0)
             lines.append("")
             lines.append("Cancel if:")
             lines.append(f"• Missed Entry: |price-level| > {missed_entry_mult}*ATR")
             lines.append(f"• Next bar violates Kevlar")

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
