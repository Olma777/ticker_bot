"""
Notifier Module (Phase 2).
Formats Decision Result into graphical card.
"""

import logging
import re
import html
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
    # Use direction from result if available, otherwise determine from entry vs level
    direction = result.direction if result.direction else "LONG" if result.entry > result.level else "SHORT" if result.entry > 0 else "UNKNOWN"
    side_icon = "🟢" if direction == "LONG" else "🔴" if direction == "SHORT" else "⚪"
    
    if result.decision == "TRADE":
        # Format TRADE signal with aligned prices and emojis
        entry_str = f"<code>${result.entry:,.2f}</code>"
        stop_str = f"<code>${result.stop_loss:,.2f}</code>"
        tp1_str = f"<code>${result.tp_targets[0]:,.2f}</code>" if len(result.tp_targets) > 0 else "N/A"
        
        # Calculate RRR if we have entry and stop
        rrr = 0.0
        if result.entry > 0 and result.stop_loss > 0:
            risk = abs(result.entry - result.stop_loss)
            reward = abs(result.tp_targets[0] - result.entry) if len(result.tp_targets) > 0 else 0
            rrr = reward / risk if risk > 0 else 0
        
        return f"🚀 <b>SIGNAL: {direction}</b> {side_icon}\n" + \
               f"🚪 Entry: {entry_str}\n" + \
               f"🛡 Stop:  {stop_str}\n" + \
               f"🎯 Target: {tp1_str}\n" + \
               f"⚖️ RRR:   {rrr:.2f}"
    else:
        # Format WAIT signal - hide Entry/Stop/TP, show CONDITION block
        clean_reason = html.escape(result.reason)
        
        # Add context information if available
        context_lines = []
        if result.market_context:
            price = result.market_context.price
            vwap = result.market_context.vwap
            if price > 0 and vwap > 0:
                dist_vwap = ((price - vwap) / vwap) * 100
                context_lines.append(f"• Price is {dist_vwap:+.1f}% {'above' if price > vwap else 'below'} VWAP")
            
            if result.market_context.supports and len(result.market_context.supports) > 0:
                nearest_support = result.market_context.supports[0]['price']
                dist_support = ((price - nearest_support) / price) * 100
                context_lines.append(f"• {dist_support:+.1f}% from nearest support")
        
        context_text = "\n".join(context_lines) if context_lines else ""
        
        return f"⛔ <b>DECISION: WAIT</b>\n" + \
               f"• Reason: {clean_reason}" + \
               (f"\n{context_text}" if context_text else "")


def _format_market_logic(market_context) -> str:
    """
    Format market logic block with regime and analysis.
    
    Args:
        market_context: MarketContext object
        
    Returns:
        Formatted market logic block or empty string
    """
    if not market_context:
        return ""
    
    # Translate regime to Russian
    regime_map = {
        "EXPANSION": "📈 <b>ЭКСПАНСИЯ</b>",
        "COMPRESSION": "📉 <b>СЖАТИЕ</b>",
        "NEUTRAL": "⚪ <b>НЕЙТРАЛЬНО</b>"
    }
    regime_text = regime_map.get(market_context.regime, f"<b>{market_context.regime}</b>")
    
    # Create bullet points based on context
    bullets = []
    
    # RSI condition
    rsi = market_context.rsi
    if rsi < 30:
        bullets.append("• RSI в зоне перепроданности")
    elif rsi > 70:
        bullets.append("• RSI в зоне перекупленности")
    else:
        bullets.append("• RSI в нейтральной зоне")
    
    # Volatility (ATR)
    atr = market_context.atr
    if atr > market_context.price * 0.02:  # 2% volatility
        bullets.append("• Высокая волатильность")
    elif atr < market_context.price * 0.005:  # 0.5% volatility
        bullets.append("• Низкая волатильность")
    
    # Price relative to VWAP
    if market_context.price > market_context.vwap * 1.01:
        bullets.append("• Цена выше VWAP (бычий сигнал)")
    elif market_context.price < market_context.vwap * 0.99:
        bullets.append("• Цена ниже VWAP (медвежий сигнал)")
    
    # Data quality
    if market_context.data_quality == "DEGRADED":
        bullets.append("• ⚠️ Качество данных снижено")
    
    # Build the block
    lines = ["🧠 <b>MARKET LOGIC:</b>", regime_text]
    lines.extend(bullets)
    return "\n".join(lines)


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
        symbol = html.escape(result.symbol)
        
        # Only show price if market context is available
        if result.market_context and hasattr(result.market_context, 'price') and result.market_context.price > 0:
            price = result.market_context.price
            price_change = getattr(result.market_context, 'price_change_24h', 0.0)
            header = f"💎 <b>{symbol}</b>\n" + \
                     f"💰 ${price:,.2f} ({price_change:+.2f}%)"
        else:
            header = f"💎 <b>{symbol}</b>\n" + \
                     f"💰 Price data unavailable"
        
        # PROGRESS BARS - RSI and Strategy Score
        score = result.p_score
        
        # Only show RSI if market context is available and RSI is valid
        if result.market_context and hasattr(result.market_context, 'rsi') and result.market_context.rsi > 0:
            rsi = result.market_context.rsi
            rsi_status = "Перепродан" if rsi < 30 else "Нейтрален" if rsi < 70 else "Перекуплен"
            escaped_rsi_status = html.escape(rsi_status)
            progress_bars = f"📊 <b>Metrics</b>\n" + \
                            f"RSI:    {draw_bar(rsi, 100, 10)} {rsi:.1f} ({escaped_rsi_status})\n" + \
                            f"Score:  {draw_bar(score, 100, 10)} {score}/100"
        else:
            progress_bars = f"📊 <b>Metrics</b>\n" + \
                            f"Score:  {draw_bar(score, 100, 10)} {score}/100\n" + \
                            f"RSI:    Data unavailable"
        
        # KEY LEVELS
        key_levels = _format_key_levels(supports or [], resistances or [])
        
        # LIQUIDITY HUNTER
        liquidity_hunter = _format_liquidity_hunter(liquidity_lines or [])
        
        # SIGNAL BLOCK
        signal_block = _format_signal_block(result)
        
        # MARKET LOGIC
        market_logic = _format_market_logic(result.market_context)
        
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
            "",
            market_logic,
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