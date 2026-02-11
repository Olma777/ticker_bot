"""
AI Analyst Module - Professional analysis with REAL order calculations
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
    
    # Split by |
    parts = level_str.split('|')
    for part in parts:
        try:
            # Extract price and score
            # Format: "🟢 $95095.5500 (Sc:30.6)"
            match = re.search(r'\$([\d.]+).*?Sc:([-\d.]+)', part)
            if match:
                price = float(match.group(1))
                score = float(match.group(2))
                is_support = "SUP" in part or "поддержка" in part.lower() or "support" in part.lower()
                levels.append({
                    'price': price,
                    'score': score,
                    'is_support': is_support
                })
        except Exception as e:
            logger.debug(f"Failed to parse level: {part}, error: {e}")
            continue
    
    # Sort by distance to current price (will be set later)
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


def _determine_market_phase(p_score: int, rsi: float, regime: str, direction: str) -> str:
    """Determine market phase based on multiple factors"""
    if p_score >= 60 and direction != "WAIT":
        return "СИЛЬНЫЙ ТРЕНД / АККУМУЛЯЦИЯ"
    elif p_score >= 40 and direction != "WAIT":
        return "ТРЕНД / НАБОР ПОЗИЦИИ"
    elif rsi < 30:
        return "ПЕРЕПРОДАННОСТЬ / ВОЗМОЖЕН ОТСКОК"
    elif rsi > 70:
        return "ПЕРЕКУПЛЕННОСТЬ / ВОЗМОЖНА КОРРЕКЦИЯ"
    elif "COMPRESSION" in regime:
        return "СЖАТИЕ / ПОДГОТОВКА К ДВИЖЕНИЮ"
    else:
        return "КОНСОЛИДАЦИЯ / НЕОПРЕДЕЛЕННОСТЬ"


async def get_ai_sniper_analysis(ticker: str) -> str:
    """
    AI-powered analysis using professional trader template.
    Uses order_calc.py for REAL entry, TP, SL values.
    """
    try:
        # Import modules
        from bot.indicators import get_technical_indicators
        from bot.order_calc import build_order_plan
        from bot.config import Config
        
        # 1. Get market data
        logger.info(f"AI Analyst: Fetching data for {ticker}")
        indicators = await get_technical_indicators(ticker)
        if not indicators:
            return f"⚠️ Нет данных для {ticker}"
        
        # 2. Extract key data
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
        
        # Get level strings
        support_str = indicators.get('support', 'НЕТ')
        resistance_str = indicators.get('resistance', 'НЕТ')
        p_score = indicators.get('p_score', 0)
        regime = indicators.get('btc_regime', 'NEUTRAL')
        
        # 3. Parse levels
        supports = _parse_levels(support_str)
        resistances = _parse_levels(resistance_str)
        
        # 4. Add distance to price
        for level in supports:
            level['distance'] = abs(level['price'] - price)
        for level in resistances:
            level['distance'] = abs(level['price'] - price)
        
        # 5. Sort by distance
        supports.sort(key=lambda x: x['distance'])
        resistances.sort(key=lambda x: x['distance'])
        
        # 6. Get closest levels
        closest_support = supports[0] if supports else None
        closest_resistance = resistances[0] if resistances else None
        
        # 7. Determine trade direction and calculate REAL orders
        direction = "WAIT"
        entry = 0.0
        stop_loss = 0.0
        tp1 = 0.0
        tp2 = 0.0
        tp3 = 0.0
        rrr = 0.0
        level_used = 0.0
        level_score = 0.0
        
        # Calculate zone_half (standard from Pine Script)
        zone_half = atr_value * Config.ZONE_WIDTH_MULT
        
        # DECISION LOGIC: LONG or SHORT?
        if p_score >= 35 and closest_support and price < closest_support['price'] * 1.01:
            # Price near support, good score -> LONG
            direction = "LONG"
            level_price = closest_support['price']
            level_score = closest_support['score']
            
            # Calculate order using SINGLE SOURCE OF TRUTH
            order = build_order_plan(
                side="LONG",
                level=level_price,
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
                
        elif p_score >= 35 and closest_resistance and price > closest_resistance['price'] * 0.99:
            # Price near resistance, good score -> SHORT
            direction = "SHORT"
            level_price = closest_resistance['price']
            level_score = closest_resistance['score']
            
            # Calculate order using SINGLE SOURCE OF TRUTH
            order = build_order_plan(
                side="SHORT",
                level=level_price,
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
        
        # 8. Format sentiment analysis
        sentiment = "Нейтрально"
        if rsi > 70:
            sentiment = "Перекупленность (возможна коррекция)"
        elif rsi < 30:
            sentiment = "Перепроданность (возможен отскок)"
        
        funding = indicators.get('funding', '0%')
        try:
            funding_val = float(funding.replace('%', '').replace('+', ''))
            if funding_val > 0.01:
                sentiment += f" | Funding: +{funding_val}% (бычий)"
            elif funding_val < -0.01:
                sentiment += f" | Funding: {funding_val}% (медвежий)"
        except:
            pass
        
        # 9. Format levels for display
        support_display = _format_levels_for_display(supports[:3])
        resistance_display = _format_levels_for_display(resistances[:3])
        
        # 10. Determine market phase
        market_phase = _determine_market_phase(p_score, rsi, regime, direction)
        
        # 11. Generate professional analysis with REAL values
        if direction == "WAIT":
            signal_text = f"""
• <b>Направление:</b> {direction}
• <b>Причина:</b> {p_score < 35 and 'Низкий P-Score' or 'Цена далеко от уровней'}
• <b>Рекомендация:</b> Ожидать подхода цены к ключевым уровням
"""
        else:
            signal_text = f"""
• <b>Направление:</b> {direction}
• <b>Точка входа:</b> <code>${entry:,.2f}</code>
• <b>Stop Loss:</b> 🔴 <code>${stop_loss:,.2f}</code>
• <b>Тейк-профиты:</b> 
  🟢 TP1: <code>${tp1:,.2f}</code> (1.0R)
  🟢 TP2: <code>${tp2:,.2f}</code> (2.0R)
  🟢 TP3: <code>${tp3:,.2f}</code> (3.0R)
• <b>Risk/Reward (к TP2):</b> 1:{rrr:.1f}
• <b>Размер позиции (при $1000, 1% риск):</b> {order.size_units:.4f} ед.
"""
        
        return f"""
📊 <b>{ticker.upper()} | PROFESSIONAL SNIPER ANALYSIS</b>
🕒 <b>Время анализа:</b> {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
💰 <b>Текущая цена:</b> <code>${price:,.2f}</code> ({change})

🎯 <b>1. КЛЮЧЕВЫЕ УРОВНИ (M30):</b>
• <b>Поддержка:</b> {support_display}
• <b>Сопротивление:</b> {resistance_display}

📈 <b>2. ТЕКУЩАЯ ФАЗА РЫНКА:</b>
• <b>Фаза:</b> {market_phase}
• <b>RSI (14):</b> {rsi:.1f} — {rsi > 70 and 'Перекуплен' or rsi < 30 and 'Перепродан' or 'Нейтрален'}
• <b>Режим BTC:</b> {regime}
• <b>Strategy Score:</b> <b>{p_score}%</b> {'✅' if p_score >= 35 else '❌'}

💰 <b>3. АНАЛИЗ НАСТРОЕНИЯ:</b>
• <b>Вердикт:</b> {sentiment}
• <b>Funding Rate:</b> {indicators.get('funding', '0%')}
• <b>Open Interest:</b> {indicators.get('open_interest', '$0')}

🎯 <b>4. ФЬЮЧЕРСНЫЙ СИГНАЛ:</b>
{signal_text}

⚠️ <b>УСЛОВИЯ И РИСКИ:</b>
• Вход строго лимитным ордером по указанной цене
• Риск на сделку: 1-2% от депозита
• Сценарий неактуален при пробое {stop_loss:,.2f if stop_loss else 'уровня стоп-лосс'}
• RRR должен быть не менее 1.10 (текущий: {rrr:.2f})

#️⃣ <b>ТЕГИ:</b> #{ticker.upper()} #{market_phase.replace(' ', '_')} #AI_Sniper
"""
        
    except Exception as e:
        logger.error(f"AI Analyst error for {ticker}: {e}", exc_info=True)
        return f"⚠️ Ошибка AI-анализа: {str(e)[:200]}"