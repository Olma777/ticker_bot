"""
Notifier Module (Phase 2).
Formats Decision Result into graphical card.
"""

import logging
from bot.decision_models import DecisionResult

logger = logging.getLogger(__name__)


def format_decision_card(result: DecisionResult) -> str:
    """
    Format output HTML.
    Template from Spec:
    🎯 SNIPER ALERT: {SYMBOL}
    ...
    """
    try:
        symbol = result.symbol
        decision = result.decision
        emoji = "✅" if decision == "TRADE" else "❌" # Or specific emojis per spec?
        # Spec: "Decison: {TRADE/WAIT} {Emoji}"
        
        reason = result.reason
        
        # Metrics
        price = result.market_context.price if result.market_context else 0.0
        score = result.p_score
        rsi = result.market_context.rsi if result.market_context else 0.0
        funding = result.sentiment_context.funding if result.sentiment_context else 0.0
        
        # Kevlar
        kevlar_status = "PASSED ✅"
        if not result.kevlar.passed:
             kevlar_status = f"FAILED ⛔\n• {result.kevlar.blocked_by}"
             
        # Execution Block
        exec_block = ""
        if decision == "TRADE":
            tp1 = result.tp_targets[0] if len(result.tp_targets) > 0 else 0
            tp3 = result.tp_targets[2] if len(result.tp_targets) > 2 else 0
            
            exec_block = f"""
🔫 <b>Execution:</b>
• Entry: {result.entry:.4f}
• Stop Loss: {result.stop_loss:.4f}
• TP1: {tp1:.4f} | TP3: {tp3:.4f}
"""

        msg = f"""🎯 <b>SNIPER ALERT: {symbol}</b>
────────────────
Decision: <b>{decision}</b> {emoji}
Reason: {reason}

📊 <b>Metrics:</b>
• Price: {price:.4f}
• P-Score: {score}/100
• RSI: {rsi:.1f} | Funding: {funding*100:.4f}%

🛡 <b>Kevlar Status:</b>
{kevlar_status}
{exec_block}
"""
        return msg

    except Exception as e:
        logger.error(f"Formatter Error: {e}")
        return "Error formatting card."


async def send_card(result: Union[DecisionResult, str]):
    """Send card to Telegram (wrapper)."""
    from bot.config import Config
    import requests
    
    if not Config.TELEGRAM_TOKEN or not Config.TELEGRAM_CHAT_ID:
        return
        
    # Handle direct text (AI Analyst) or DecisionResult
    if isinstance(result, str):
        text = result
    else:
        text = format_decision_card(result)
    
    url = f"https://api.telegram.org/bot{Config.TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": Config.TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
             async with session.post(url, json=payload) as resp:
                 if resp.status != 200:
                     logger.error(f"TG Error: {await resp.text()}")
    except Exception as e:
        logger.error(f"TG Send Error: {e}")
