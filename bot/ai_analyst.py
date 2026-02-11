"""
AI Analyst Module - Professional analysis with REAL order calculations
FORCED MODE - NO FALLBACK TO LEGACY
"""

import logging
import re
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


def _parse_levels(level_str: str) -> List[Dict]:
    """Parse level string into list of level dictionaries"""
    levels = []
    if not level_str or level_str == "НЕТ":
        return levels
    
    parts = level_str.split('|')
    for part in parts:
        try:
            match = re.search(r'\$([\d.]+).*?Sc:([-\d.]+)', part)
            if match:
                price = float(match.group(1))
                score = float(match.group(2))
                is_support = "SUP" in part or "поддержка" in part.lower()
                levels.append({
                    'price': price,
                    'score': score,
                    'is_support': is_support
                })
        except Exception:
            continue
    return levels


def _format_levels_for_display(levels: List[Dict], count: int = 3) -> str:
    """Format top N levels for display"""
    if not levels:
        return "НЕТ"
    result = []
    for level in levels[:count]:
        emoji = "🟢" if level['score'] >= 3.0 else "🟡" if level['score'] >= 1.0 else "🔴"
        result.append(f"{emoji} ${level['price']:,.2f} (Sc:{level['score']:.1f})")
    return " | ".join(result)


async def get_ai_sniper_analysis(ticker: str) -> str:
    """FORCED AI ANALYST - REAL ORDERS FROM order_calc.py"""
    try:
        from bot.indicators import get_technical_indicators
        from bot.order_calc import build_order_plan
        from bot.config import Config
        
        indicators = await get_technical_indicators(ticker)
        if not indicators:
            return f"⚠️ No data for {ticker}"
        
        # Extract data
        price = indicators.get('price', 0)
        change = indicators.get('change', '0%')
        rsi = indicators.get('rsi', 50)
        atr_raw = indicators.get('atr_val', '$0')
        
        # Parse ATR
        atr_value = 0.0
        if isinstance(atr_raw, str):
            atr_value = float(atr_raw.replace('$', '').replace(',', ''))
        else:
            atr_value = float(atr_raw)
        
        support_str = indicators.get('support', 'НЕТ')
        resistance_str = indicators.get('resistance', 'НЕТ')
        p_score = indicators.get('p_score', 0)
        regime = indicators.get('btc_regime', 'NEUTRAL')
        funding = indicators.get('funding', '0%')
        oi = indicators.get('open_interest', '$0')
        
        # Parse levels
        supports = _parse_levels(support_str)
        resistances = _parse_levels(resistance_str)
        
        # Add distance
        for level in supports:
            level['distance'] = abs(level['price'] - price)
        for level in resistances:
            level['distance'] = abs(level['price'] - price)
        
        # Sort by distance
        supports.sort(key=lambda x: x['distance'])
        resistances.sort(key=lambda x: x['distance'])
        
        closest_support = supports[0] if supports else None
        closest_resistance = resistances[0] if resistances else None
        
        # Calculate zone_half
        zone_half = atr_value * Config.ZONE_WIDTH_MULT
        
        # DECISION & ORDER CALCULATION
        direction = "WAIT"
        entry = 0.0
        stop_loss = 0.0
        tp1 = 0.0
        tp2 = 0.0
        tp3 = 0.0
        rrr = 0.0
        size = 0.0
        level_used = 0.0
        
        # LONG signal
        if p_score >= 35 and closest_support and price < closest_support['price'] * 1.01:
            direction = "LONG"
            level_used = closest_support['price']
            
            order = build_order_plan(
                side="LONG",
                level=level_used,
                zone_half=zone_half,
                atr=atr_value,
                capital=1000.0,
                risk_pct=1.0,
                lot_step=None
            )
            
            if order and not order.reason_blocked:
                entry = order.entry
                stop_loss = order.stop_loss
                tp1 = order.tp1
                tp2 = order.tp2
                tp3 = order.tp3
                rrr = order.rrr_tp2
                size = order.size_units
        
        # SHORT signal
        elif p_score >= 35 and closest_resistance and price > closest_resistance['price'] * 0.99:
            direction = "SHORT"
            level_used = closest_resistance['price']
            
            order = build_order_plan(
                side="SHORT",
                level=level_used,
                zone_half=zone_half,
                atr=atr_value,
                capital=1000.0,
                risk_pct=1.0,
                lot_step=None
            )
            
            if order and not order.reason_blocked:
                entry = order.entry
                stop_loss = order.stop_loss
                tp1 = order.tp1
                tp2 = order.tp2
                tp3 = order.tp3
                rrr = order.rrr_tp2
                size = order.size_units
        
        # Format levels for display
        support_display = _format_levels_for_display(supports[:3])
        resistance_display = _format_levels_for_display(resistances[:3])
        
        # Determine market phase
        market_phase = "НЕОПРЕДЕЛЕННОСТЬ"
        if p_score >= 60:
            market_phase = "СИЛЬНЫЙ ТРЕНД"
        elif p_score >= 40:
            market_phase = "ТРЕНДОВОЕ ДВИЖЕНИЕ"
        elif rsi < 30:
            market_phase = "ПЕРЕПРОДАННОСТЬ"
        elif rsi > 70:
            market_phase = "ПЕРЕКУПЛЕННОСТЬ"
        
        # Format sentiment
        sentiment = "Нейтрально"
        try:
            funding_val = float(funding.replace('%', '').replace('+', ''))
            if funding_val > 0.01:
                sentiment = f"Бычий (Funding: {funding})"
            elif funding_val < -0.01:
                sentiment = f"Медвежий (Funding: {funding})"
        except:
            pass
        
        # Build signal text with REAL values
        if direction == "WAIT":
            signal_text = f"""
🚦 <b>Тип:</b> WAIT
📌 <b>Причина:</b> {p_score < 35 and 'Низкий P-Score' or 'Цена далеко от уровней'}
📊 <b>P-Score:</b> {p_score}% {'✅' if p_score >= 35 else '❌'}
"""
        else:
            signal_text = f"""
🚦 <b>Тип:</b> {direction}
🎯 <b>Вход:</b> <code>${entry:,.2f}</code>
🛡 <b>Stop Loss:</b> <code>${stop_loss:,.2f}</code>

✅ <b>Тейк-профиты:</b>
   • TP1: <code>${tp1:,.2f}</code> (1.0R)
   • TP2: <code>${tp2:,.2f}</code> (2.0R)  
   • TP3: <code>${tp3:,.2f}</code> (3.0R)

📊 <b>Risk/Reward (TP2):</b> 1:{rrr:.2f}
📏 <b>Размер позиции:</b> {size:.4f} ед. (при $1000, 1% риск)
"""
        
        # FINAL OUTPUT - YOUR TEMPLATE
        return f"""
📊 <b>{ticker.upper()} | PROFESSIONAL SNIPER ANALYSIS</b>
🕒 <b>Время:</b> {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
💰 <b>Текущая цена:</b> <code>${price:,.2f}</code> ({change})

🎯 <b>1. КЛЮЧЕВЫЕ УРОВНИ (M30):</b>
• <b>Поддержка:</b> {support_display}
• <b>Сопротивление:</b> {resistance_display}

📈 <b>2. ТЕКУЩАЯ ФАЗА РЫНКА:</b>
• <b>Фаза:</b> {market_phase}
• <b>RSI:</b> {rsi:.1f} — {'Перепроданность' if rsi < 30 else 'Перекупленность' if rsi > 70 else 'Нейтрально'}
• <b>Режим BTC:</b> {regime}
• <b>Strategy Score:</b> <b>{p_score}%</b> {'✅' if p_score >= 35 else '❌'}

💰 <b>3. АНАЛИЗ НАСТРОЕНИЯ:</b>
• <b>Вердикт:</b> {sentiment}
• <b>Funding Rate:</b> {funding}
• <b>Open Interest:</b> {oi}

🎯 <b>4. ФЬЮЧЕРСНЫЙ СИГНАЛ:</b>{signal_text}
⚠️ <b>УСЛОВИЯ ВХОДА:</b>
• Вход строго лимитным ордером
• Риск: 1-2% от депозита
• RRR должен быть ≥ 1.10 {'✅' if rrr >= 1.10 else '❌'}

#️⃣ <b>ТЕГИ:</b> #{ticker.upper()} #{market_phase.replace(' ', '_')} #AI_Sniper
"""
        
    except Exception as e:
        logger.error(f"AI Analyst error: {e}", exc_info=True)
        return f"""❌ <b>AI ANALYST ERROR</b>
        
{ticker}: {str(e)[:200]}

Time: {datetime.now(timezone.utc).strftime("%H:%M UTC")}
"""

print("✅ STEP 1: ai_analyst.py code prepared")
