"""
AI Analyst Module - INDICATOR DRIVEN, AI ENHANCED
INDICATOR = уровни + score (тех. анализ)
AI = решение + контекст + шаблон
ORDER_CALC = точные цифры TP/SL
"""

import logging
import re
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


def _parse_levels(level_str: str) -> List[Dict]:
    """Parse level string from INDICATOR into list of level dictionaries"""
    levels = []
    if not level_str or level_str == "НЕТ":
        return levels
    
    parts = level_str.split('|')
    for part in parts:
        try:
            # Extract price and score from INDICATOR data
            match = re.search(r'\$([\d.]+).*?Sc:([-\d.]+)', part)
            if match:
                price = float(match.group(1))
                score = float(match.group(2))
                is_support = "SUP" in part or "поддержка" in part.lower()
                levels.append({
                    'price': price,
                    'score': score,
                    'is_support': is_support,
                    'strength': 'STRONG' if score >= 3.0 else 'MEDIUM' if score >= 1.0 else 'WEAK'
                })
        except Exception:
            continue
    return levels


def _format_levels_for_display(levels: List[Dict], count: int = 3) -> str:
    """Format INDICATOR levels for display with proper emoji based on score"""
    if not levels:
        return "НЕТ"
    result = []
    for level in levels[:count]:
        # Emoji strictly follows INDICATOR grading
        if level['score'] >= 3.0:
            emoji = "�"  # STRONG
        elif level['score'] >= 1.0:
            emoji = "🟡"  # MEDIUM
        else:
            emoji = "🔴"  # WEAK
        result.append(f"{emoji} ${level['price']:,.2f} (Sc:{level['score']:.1f})")
    return " | ".join(result)


def _determine_market_phase(p_score: int, rsi: float, regime: str, 
                           strong_supports: List, strong_resists: List) -> str:
    """Determine market phase based on INDICATOR data + context"""
    
    # INDICATOR shows strong levels on both sides
    if strong_supports and strong_resists:
        return "СИЛЬНЫЙ ДИАПАЗОН / НАКОПЛЕНИЕ"
    
    # INDICATOR shows strong support only
    if strong_supports and not strong_resists:
        return "ПОДДЕРЖКА УДЕРЖИВАЕТСЯ / ПОТЕНЦИАЛЬНЫЙ РАЗВОРОТ"
    
    # INDICATOR shows strong resistance only
    if strong_resists and not strong_supports:
        return "СОПРОТИВЛЕНИЕ УДЕРЖИВАЕТСЯ / ПОТЕНЦИАЛЬНАЯ КОРРЕКЦИЯ"
    
    # INDICATOR shows weak levels only
    weak_levels = not strong_supports and not strong_resists
    if weak_levels and p_score < 40:
        return "НЕОПРЕДЕЛЕННОСТЬ / ОТСУТСТВИЕ СИЛЬНЫХ УРОВНЕЙ"
    
    # Default - use P-Score and RSI
    if p_score >= 60:
        return "СИЛЬНЫЙ ТРЕНД"
    elif p_score >= 40:
        return "ТРЕНДОВОЕ ДВИЖЕНИЕ"
    elif rsi < 30:
        return "ПЕРЕПРОДАННОСТЬ"
    elif rsi > 70:
        return "ПЕРЕКУПЛЕННОСТЬ"
    else:
        return "КОНСОЛИДАЦИЯ"


async def get_ai_sniper_analysis(ticker: str) -> str:
    """
    INDICATOR → AI → ORDER_CALC pipeline
    1. INDICATOR provides levels with SCORE
    2. AI analyzes levels, market context, sentiment
    3. ORDER_CALC calculates exact entry, stop, targets
    4. OUTPUT formatted to your template
    """
    try:
        from bot.indicators import get_technical_indicators
        from bot.order_calc import build_order_plan
        from bot.config import Config
        
        # ===== STEP 1: GET INDICATOR DATA =====
        logger.info(f"📊 INDICATOR: Fetching data for {ticker}")
        indicators = await get_technical_indicators(ticker)
        if not indicators:
            return f"⚠️ INDICATOR: No data for {ticker}"
        
        # Extract ALL indicator data
        price = indicators.get('price', 0)
        change = indicators.get('change', '0%')
        rsi = indicators.get('rsi', 50)
        vwap = indicators.get('vwap', '$0')
        
        # Parse ATR (volatility)
        atr_raw = indicators.get('atr_val', '$0')
        atr_value = 0.0
        if isinstance(atr_raw, str):
            atr_value = float(atr_raw.replace('$', '').replace(',', ''))
        else:
            atr_value = float(atr_raw)
        
        # Get level strings DIRECTLY FROM INDICATOR
        support_str = indicators.get('support', 'НЕТ')
        resistance_str = indicators.get('resistance', 'НЕТ')
        
        # Get P-Score and regime
        p_score = indicators.get('p_score', 0)
        regime = indicators.get('btc_regime', 'NEUTRAL')
        
        # Get sentiment data
        funding = indicators.get('funding', '0%')
        oi = indicators.get('open_interest', '$0')
        
        # ===== STEP 2: PARSE INDICATOR LEVELS =====
        supports = _parse_levels(support_str)
        resistances = _parse_levels(resistance_str)
        
        # Add distance to current price
        for level in supports:
            level['distance'] = abs(level['price'] - price)
            level['distance_pct'] = (level['distance'] / price) * 100
        for level in resistances:
            level['distance'] = abs(level['price'] - price)
            level['distance_pct'] = (level['distance'] / price) * 100
        
        # Sort by distance (closest first)
        supports.sort(key=lambda x: x['distance'])
        resistances.sort(key=lambda x: x['distance'])
        
        # ===== STEP 3: ANALYZE INDICATOR STRENGTH =====
        # STRONG levels (🟢) - score >= 3.0
        strong_supports = [l for l in supports if l['score'] >= 3.0]
        strong_resists = [l for l in resistances if l['score'] >= 3.0]
        
        # MEDIUM levels (🟡) - score between 1.0 and 2.9
        medium_supports = [l for l in supports if 1.0 <= l['score'] < 3.0]
        medium_resists = [l for l in resistances if 1.0 <= l['score'] < 3.0]
        
        # WEAK levels (🔴) - score < 1.0
        weak_supports = [l for l in supports if l['score'] < 1.0]
        weak_resists = [l for l in resistances if l['score'] < 1.0]
        
        logger.info(f"📊 INDICATOR: {len(strong_supports)} strong supports, {len(strong_resists)} strong resists")
        logger.info(f"📊 INDICATOR: {len(medium_supports)} medium supports, {len(medium_resists)} medium resists")
        logger.info(f"📊 INDICATOR: {len(weak_supports)} weak supports, {len(weak_resists)} weak resists")
        
        # ===== STEP 4: AI DECISION MAKING =====
        # Decision is BASED ON INDICATOR DATA, not ignoring it!
        
        direction = "WAIT"
        entry_level = 0.0
        entry_score = 0.0
        decision_reason = []
        
        # Calculate zone_half for order calculations
        zone_half = atr_value * Config.ZONE_WIDTH_MULT
        
        # --- CASE 1: STRONG SUPPORT (🟢) near price ---
        if strong_supports and price < strong_supports[0]['price'] * 1.02:
            direction = "LONG"
            entry_level = strong_supports[0]['price']
            entry_score = strong_supports[0]['score']
            decision_reason.append(f"Strong Support 🟢 (Sc:{entry_score:.1f})")
            decision_reason.append(f"Price ${price:.0f} near level ${entry_level:.0f}")
            logger.info(f"✅ AI: LONG signal from STRONG SUPPORT (Sc:{entry_score})")
        
        # --- CASE 2: STRONG RESISTANCE (🟢) near price ---
        elif strong_resists and price > strong_resists[0]['price'] * 0.98:
            direction = "SHORT"
            entry_level = strong_resists[0]['price']
            entry_score = strong_resists[0]['score']
            decision_reason.append(f"Strong Resistance 🟢 (Sc:{entry_score:.1f})")
            decision_reason.append(f"Price ${price:.0f} near level ${entry_level:.0f}")
            logger.info(f"✅ AI: SHORT signal from STRONG RESISTANCE (Sc:{entry_score})")
        
        # --- CASE 3: MEDIUM SUPPORT (🟡) + good P-Score ---
        elif medium_supports and p_score >= 45 and price < medium_supports[0]['price'] * 1.01:
            direction = "LONG"
            entry_level = medium_supports[0]['price']
            entry_score = medium_supports[0]['score']
            decision_reason.append(f"Medium Support 🟡 (Sc:{entry_score:.1f}) + P-Score {p_score}%")
            logger.info(f"⚠️ AI: LONG signal from MEDIUM SUPPORT (Sc:{entry_score})")
        
        # --- CASE 4: MEDIUM RESISTANCE (🟡) + good P-Score ---
        elif medium_resists and p_score >= 45 and price > medium_resists[0]['price'] * 0.99:
            direction = "SHORT"
            entry_level = medium_resists[0]['price']
            entry_score = medium_resists[0]['score']
            decision_reason.append(f"Medium Resistance 🟡 (Sc:{entry_score:.1f}) + P-Score {p_score}%")
            logger.info(f"⚠️ AI: SHORT signal from MEDIUM RESISTANCE (Sc:{entry_score})")
        
        # --- CASE 5: P-Score only (no strong/medium levels) ---
        elif p_score >= 60 and supports and resistances:
            # Use closest level based on price position
            closest_sup = supports[0]['distance'] if supports else float('inf')
            closest_res = resistances[0]['distance'] if resistances else float('inf')
            
            if closest_sup < closest_res and price < supports[0]['price'] * 1.01:
                direction = "LONG"
                entry_level = supports[0]['price']
                entry_score = supports[0]['score']
                decision_reason.append(f"High P-Score ({p_score}%) + Closest Support")
            elif closest_res < closest_sup and price > resistances[0]['price'] * 0.99:
                direction = "SHORT"
                entry_level = resistances[0]['price']
                entry_score = resistances[0]['score']
                decision_reason.append(f"High P-Score ({p_score}%) + Closest Resistance")
        
        # ===== STEP 5: CALCULATE ORDERS =====
        order = None
        if direction != "WAIT" and entry_level > 0:
            order = build_order_plan(
                side=direction,
                level=entry_level,
                zone_half=zone_half,
                atr=atr_value,
                capital=1000.0,
                risk_pct=1.0,
                lot_step=None
            )
            
            # If order is blocked by RRR, go back to WAIT
            if order and order.reason_blocked:
                logger.info(f"❌ AI: Order blocked - {order.reason_blocked}")
                direction = "WAIT"
                decision_reason.append(f"Blocked: {order.reason_blocked}")
        
        # ===== STEP 6: FORMAT DISPLAY =====
        # Show TOP 3 levels from INDICATOR (closest)
        support_display = _format_levels_for_display(supports[:3])
        resistance_display = _format_levels_for_display(resistances[:3])
        
        # Market phase based on INDICATOR
        market_phase = _determine_market_phase(p_score, rsi, regime, 
                                             strong_supports, strong_resists)
        
        # Sentiment analysis
        sentiment = "Нейтрально"
        try:
            funding_val = float(funding.replace('%', '').replace('+', ''))
            if funding_val > 0.01:
                sentiment = f"Бычий (Funding: {funding})"
            elif funding_val < -0.01:
                sentiment = f"Медвежий (Funding: {funding})"
        except:
            pass
        
        # Build reason string
        reason_text = " • ".join(decision_reason) if decision_reason else "Нет сигнала"
        
        # ===== STEP 7: BUILD SIGNAL TEXT =====
        if direction == "WAIT" or not order:
            signal_text = f"""
🚦 <b>Тип:</b> WAIT
� <b>P-Score:</b> {p_score}% {'✅' if p_score >= 35 else '❌'}
� <b>Причина:</b> {reason_text}
"""
        else:
            # Calculate position size display
            pos_size_display = f"{order.size_units:.4f}"
            if order.size_units > 100:
                pos_size_display = f"{order.size_units:.0f}"
            
            signal_text = f"""
🚦 <b>Тип:</b> {direction}
🎯 <b>Вход:</b> <code>${order.entry:,.2f}</code> (Sc:{entry_score:.1f})
🛡 <b>Stop Loss:</b> <code>${order.stop_loss:,.2f}</code>

✅ <b>Тейк-профиты (ATR-based):</b>
   • TP1: <code>${order.tp1:,.2f}</code> (0.75×ATR)
   • TP2: <code>${order.tp2:,.2f}</code> (1.25×ATR)  
   • TP3: <code>${order.tp3:,.2f}</code> (2.00×ATR)

📊 <b>Risk/Reward (TP2):</b> 1:{order.rrr_tp2:.2f} {'✅' if order.rrr_tp2 >= 1.10 else '❌'}
� <b>Размер позиции:</b> {pos_size_display} ед. (1% риск, $1000)
📏 <b>Дистанция стопа:</b> ${order.stop_dist:.2f} ({order.stop_dist/atr_value:.1f}×ATR)
"""
        
        # ===== STEP 8: FINAL OUTPUT - YOUR TEMPLATE =====
        return f"""
📊 <b>{ticker.upper()} | PROFESSIONAL SNIPER ANALYSIS</b>
🕒 <b>Время:</b> {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
💰 <b>Текущая цена:</b> <code>${price:,.2f}</code> ({change})

🎯 <b>1. КЛЮЧЕВЫЕ УРОВНИ (M30) — ИНДИКАТОР:</b>
• <b>Поддержка:</b> {support_display}
• <b>Сопротивление:</b> {resistance_display}

📈 <b>2. ТЕКУЩАЯ ФАЗА РЫНКА:</b>
• <b>Фаза:</b> {market_phase}
• <b>RSI (14):</b> {rsi:.1f} — {'Перепроданность' if rsi < 30 else 'Перекупленность' if rsi > 70 else 'Нейтрально'}
• <b>Режим BTC:</b> {regime}
• <b>Strategy Score:</b> <b>{p_score}%</b> {'✅' if p_score >= 35 else '❌'}

💰 <b>3. АНАЛИЗ НАСТРОЕНИЯ:</b>
• <b>Вердикт:</b> {sentiment}
• <b>Funding Rate:</b> {funding}
• <b>Open Interest:</b> {oi}

🎯 <b>4. ФЬЮЧЕРСНЫЙ СИГНАЛ (НА ОСНОВЕ ИНДИКАТОРА):</b>{signal_text}
📋 <b>ЛОГИКА РЕШЕНИЯ:</b>
{reason_text}

⚠️ <b>УСЛОВИЯ ВХОДА:</b>
• Вход строго лимитным ордером по уровню
• Риск на сделку: 1-2% от депозита
• Минимальный RRR: 1.10
• Отмена сигнала: пробой уровня стоп-лосс

#️⃣ <b>ТЕГИ:</b> #{ticker.upper()} #{market_phase.replace(' ', '_')} #AI_Sniper #IndicatorDriven
"""
        
    except Exception as e:
        logger.error(f"AI Analyst error: {e}", exc_info=True)
        return f"""❌ <b>AI ANALYST ERROR</b>
        
{ticker}: {str(e)[:200]}

Время: {datetime.now(timezone.utc).strftime("%H:%M UTC")}
"""

if __name__ == "__main__":
    print("✅ AI ANALYST UPDATED: Indicator-Driven Architecture")
    print("📊 INDICATOR provides levels with SCORE")
    print("🧠 AI makes decisions based on level strength")
    print("🧮 ORDER_CALC calculates exact numbers")
    print("📋 OUTPUT follows your professional template")
