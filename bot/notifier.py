"""
Notifier Module.
Formats and sends Decision Cards to Telegram.
Strictly implements LOCKED Spec (P1 Final).
Updated for P1-FINAL-TEXT-CLEANSE-V2: Absolute ZERO 'Close' references.
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
    LOCKED SPEC: 
     - No discretionary text. 
     - Strict colors.
     - "P-SCORE: X / 35"
     - ENTRY MODE: TOUCH_LIMIT (Hardcoded text to ensure compliance)
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
        
        # Grade Color strictly (LOCKED VIA Model Logic, displayed here)
        grade_str = "N/A"
        grade_icon = "⚪"
        if result.level_grade:
             grade_str = result.level_grade.grade
             # Icons determined by String Grade
             if grade_str == "STRONG": grade_icon = "🟢"
             elif grade_str == "MEDIUM": grade_icon = "🟡"
             elif grade_str == "WEAK": grade_icon = "🔴"

        # P-Score Breakdown
        breakdown_text = "\n".join(result.pscore.breakdown)
        
        # Market/Sentiment
        if result.market_context:
            m = result.market_context
            rsi_val = f"{m.rsi:.1f}"
            vwap_val = f"{m.vwap:.2f}"
            atr_val = f"{m.atr:.2f}"
        else:
            rsi_val = "N/A"
            vwap_val = "N/A"
            atr_val = "N/A"
            
        if result.sentiment_context:
            s = result.sentiment_context
            fund_val = f"{s.funding:.4f}%" if s.funding is not None else "N/A"
            oi_val = f"{s.open_interest:.2f}" if s.open_interest is not None else "N/A"
        else:
            fund_val = "N/A"
            oi_val = "N/A"

        # --- Template Construction ---
        
        lines = []
        
        # Header
        lines.append(f"📊 <b>{symbol} | {tf} SNIPER</b>")
        lines.append(f"🕒 Event: {event_str} | Time: {bar_time_str}")
        lines.append(f"💰 Price: {current_price}")
        lines.append("")

        # Decision Block (LOCKED FORMAT)
        if result.decision == "TRADE":
            lines.append(f"<b>DECISION: TRADE ✅ ({result.side})</b>")
            lines.append("")
            # Strict Text: TOUCH_LIMIT only.
            lines.append(f"Entry Mode: {Config.ENTRY_MODE}") 
            
            if result.risk:
                r = result.risk
                lines.append(f"Entry: {r.entry_price:.4f}")
                lines.append(f"SL: {r.stop_loss:.4f}")
                lines.append(f"TP1: {r.tp1:.4f} | TP2: {r.tp2:.4f} | TP3: {r.tp3:.4f}")
                lines.append(f"StopDist: {r.stop_dist:.4f}")
                lines.append(f"Risk: ${r.risk_amount:.2f}")
                lines.append(f"Size: {r.position_size:.4f} (Risk / StopDist)")
                lines.append(f"RRR (TP2): {r.rrr_tp2:.2f}")
            
            lines.append("")
            # Strict Format: X / 35
            lines.append(f"<b>P-SCORE: {result.pscore.score} / {Config.P_SCORE_THRESHOLD}</b>")
            lines.append(f"Kevlar: PASSED ✅")

        elif result.decision == "WAIT":
            lines.append(f"<b>DECISION: WAIT ❌</b>")
            lines.append("")
            lines.append(f"Reason:")
            if not result.kevlar.passed:
                lines.append(f"• Kevlar: {result.kevlar.blocked_by}")
            
            if result.pscore.score < Config.P_SCORE_THRESHOLD:
                # Strict Format: X / 35
                lines.append(f"• P-SCORE below threshold ({result.pscore.score} / {Config.P_SCORE_THRESHOLD})")
                
            if result.reason and "RRR" in result.reason:
                lines.append(f"• {result.reason}")

            lines.append("")
            lines.append("Conditions to change decision:")
            # STRICT LOGIC only. No "Wait for Close".
            lines.append(f"• P-SCORE ≥ {Config.P_SCORE_THRESHOLD}")
            lines.append(f"• Grade must be MEDIUM or STRONG")
            
            lines.append("")
            # Strict Format: X / 35
            lines.append(f"<b>P-SCORE: {result.pscore.score} / {Config.P_SCORE_THRESHOLD}</b>")

        # Breakdown (Always show)
        lines.append("Score Breakdown:")
        lines.append(f"<pre>{breakdown_text}</pre>")

        # Level Info
        lines.append("")
        lines.append("<b>Level Analysis:</b>")
        lines.append(f"• Grade: {grade_icon} {grade_str}")
        lines.append(f"• Score: {sc} | Touches: {touches}")
        lines.append(f"• Zone: {level_price} ± {zone_half}")

        # Market Context
        lines.append("")
        lines.append("<b>Market Context:</b>")
        lines.append(f"• ATR: {atr_val} | RSI: {rsi_val}")
        lines.append(f"• VWAP: {vwap_val}")
        lines.append(f"• Funding: {fund_val} | OI: {oi_val}")

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
