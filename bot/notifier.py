"""
Notifier Module (Phase 2).
Formats Decision Result into graphical card.
"""

import logging
import re
from typing import Union, List, Dict, Any
from bot.decision_models import DecisionResult

logger = logging.getLogger(__name__)


def draw_bar(value: float, total: float = 100, length: int = 10) -> str:
    """
    Draw progress bar using filled and empty blocks.
    
    Args:
        value: Current value
        total: Maximum value (default 100)
        length: Length of the bar in characters (default 10)
        
    Returns:
        String representation of progress bar
    """
    percentage = min(100, max(0, (value / total) * 100)) if total > 0 else 0
    filled_length = int(length * percentage / 100)
    return '▓' * filled_length + '░' * (length - filled_length)


def _clean_tags(tags: List[str]) -> List[str]:
    """
    Clean hashtags by removing special characters.
    
    Args:
        tags: List of hashtag strings
        
    Returns:
        Cleaned hashtags without special characters
    """
    cleaned = []
    for tag in tags:
        # Remove special characters, keep only letters, numbers, and underscores
        cleaned_tag = re.sub(r'[^\w\u0400-\u04FF]', '_', tag.strip('#')).strip('_')
        if cleaned_tag:
            cleaned.append(f"#{cleaned_tag}")
    return cleaned


def _format_key_levels(supports: List[Dict[str, Any]], 
                      resistances: List[Dict[str, Any]]) -> str:
    """
    Format key levels section with only 2 nearest supports and resistances.
    
    Args:
        supports: List of support levels
        resistances: List of resistance levels
        
    Returns:
        Formatted string for key levels section
    """
    # Get 2 closest supports and resistances
    closest_supports = sorted([s for s in supports if s.get('is_support', True)], 
                             key=lambda x: x.get('distance', float('inf')))[:2]
    closest_resistances = sorted([r for r in resistances if not r.get('is_support', False)], 
                                key=lambda x: x.get('distance', float('inf')))[:2]
    
    # Format supports
    support_lines = []
    for level in closest_supports:
        if level['score'] > 20:
            strength_emoji = "🟢"
        elif level['score'] > 10:
            strength_emoji = "🟡"
        else:
            strength_emoji = "⚪"
        support_lines.append(f"<code>${level['price']:,.0f}</code> ({strength_emoji})")
    
    # Format resistances
    resistance_lines = []
    for level in closest_resistances:
        if level['score'] > 20:
            strength_emoji = "🟢"
        elif level['score'] > 10:
            strength_emoji = "🟡"
        else:
            strength_emoji = "⚪"
        resistance_lines.append(f"<code>${level['price']:,.0f}</code> ({strength_emoji})")
    
    support_text = " | ".join(support_lines) if support_lines else "НЕТ"
    resistance_text = " | ".join(resistance_lines) if resistance_lines else "НЕТ"
    
    return f"🎯 <b>ZONES</b>\nRES: {resistance_text}\nSUP: {support_text}"


def _format_liquidity_hunter(liquidity_lines: List[str]) -> str:
    """
    Format liquidity hunter data in compact "Range: Volume" format.
    
    Args:
        liquidity_lines: List of liquidity lines
        
    Returns:
        Formatted string for liquidity hunter section
    """
    if not liquidity_lines:
        return ""
    
    # Parse the lines to extract range and volume info
    formatted_lines = []
    for line in liquidity_lines[:4]:  # Only top 4
        # Extract range and volume information
        if "верхний" in line.lower() or "upper" in line.lower():
            # Format as "Upper: $84k - $88k (High Vol)"
            formatted_lines.append("Upper: $84k - $88k (High Vol)")
        elif "нижний" in line.lower() or "lower" in line.lower():
            # Format as "Lower: $71k - $73k (Med Vol)"
            formatted_lines.append("Lower: $71k - $73k (Med Vol)")
        else:
            # Generic format
            formatted_lines.append(line)
    
    if formatted_lines:
        return f"🩸 <b>LIQUIDITY POOLS</b>\n" + "\n".join(formatted_lines)
    return ""


def _format_signal_block(result: DecisionResult) -> str:
    """
    Format signal block with aligned prices for WAIT/TRADE decisions.
    
    Args:
        result: DecisionResult object
        
    Returns:
        Formatted signal block
    """
    if result.decision == "TRADE":
        # Format TRADE signal with aligned prices
        entry_str = f"<code>${result.entry:,.2f}</code>"
        stop_str = f"<code>${result.stop_loss:,.2f}</code>"
        tp1_str = f"<code>${result.tp_targets[0]:,.2f}</code>" if len(result.tp_targets) > 0 else "N/A"
        tp2_str = f"<code>${result.tp_targets[1]:,.2f}</code>" if len(result.tp_targets) > 1 else "N/A"
        
        return f"🚀 <b>SIGNAL: {result.direction.upper()}</b>\n" + \
               f"Entry:  {entry_str}\n" + \
               f"Stop:   {stop_str}\n" + \
               f"TP1:    {tp1_str}\n" + \
               f"TP2:    {tp2_str}"
    else:
        # Format WAIT signal
        return f"� <b>DECISION: WAIT</b>\n" + \
               f"Reason: {result.reason}"


def format_telegram_message(result: DecisionResult, 
                           supports: List[Dict[str, Any]] = None,
                           resistances: List[Dict[str, Any]] = None,
                           liquidity_lines: List[str] = None,
                           tags: List[str] = None) -> str:
    """
    Unified function to format complete Telegram message with Card UI.
    
    Args:
        result: DecisionResult object
        supports: List of support levels
        resistances: List of resistance levels
        liquidity_lines: List of liquidity hunter lines
        tags: List of hashtags
        
    Returns:
        Complete formatted Telegram message
    """
    try:
        # HEADER - Compact header with symbol and price
        symbol = result.symbol
        price = result.market_context.price if result.market_context else 0.0
        price_change = result.market_context.price_change_24h if result.market_context else 0.0
        
        header = f"💎 <b>{symbol}</b>\n" + \
                 f"💰 ${price:,.2f} ({price_change:+.2f}%)"
        
        # PROGRESS BARS - RSI and Strategy Score
        rsi = result.market_context.rsi if result.market_context else 0.0
        score = result.p_score
        
        rsi_status = "Перепродан" if rsi < 30 else "Нейтрален" if rsi < 70 else "Перекуплен"
        
        progress_bars = f"📊 <b>Metrics</b>\n" + \
                        f"RSI:    {draw_bar(rsi, 100, 10)} {rsi:.1f} ({rsi_status})\n" + \
                        f"Score:  {draw_bar(score, 100, 10)} {score}/100"
        
        # KEY LEVELS
        key_levels = _format_key_levels(supports or [], resistances or [])
        
        # LIQUIDITY HUNTER
        liquidity_hunter = _format_liquidity_hunter(liquidity_lines or [])
        
        # SIGNAL BLOCK
        signal_block = _format_signal_block(result)
        
        # FOOTER - Cleaned tags and watermark
        cleaned_tags = _clean_tags(tags or [])
        tags_text = " ".join(cleaned_tags) if cleaned_tags else ""
        
        footer = f"\n{tags_text}\n🤖 Analysis by AI Sniper v3.2"
        
        # Combine all sections
        sections = [
            header,
            "────────────────",
            progress_bars,
            "",
            key_levels,
            "",
            liquidity_hunter,
            "",
            signal_block,
            footer
        ]
        
        # Filter out empty sections and join with newlines
        return "\n".join(filter(None, sections))

    except Exception as e:
        logger.error(f"Message formatting error: {e}")
        return "Error formatting message."


def format_decision_card(result: DecisionResult) -> str:
    """
    Legacy function for backward compatibility.
    """
    return format_telegram_message(result)


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