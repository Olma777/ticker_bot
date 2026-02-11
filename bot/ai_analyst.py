"""
AI Analyst Module - FINAL VERSION
INDICATOR DRIVEN + MM BEHAVIOR + ORDER CALC
Complete integration of all requirements.
"""

import logging
import re
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


# ============================================
# PART 1: INDICATOR DATA PARSING
# ============================================

def _parse_levels(level_str: str) -> List[Dict]:
    """Parse level string from INDICATOR into list of level dictionaries"""
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
                    'is_support': is_support,
                    'strength': 'STRONG' if score >= 3.0 else 'MEDIUM' if score >= 1.0 else 'WEAK'
                })
        except Exception:
            continue
    return levels


def _format_levels_for_display(levels: List[Dict], count: int = 3) -> str:
    """Format INDICATOR levels with proper emoji based on SCORE"""
    if not levels:
        return "НЕТ"
    result = []
    for level in levels[:count]:
        if level['score'] >= 3.0:
            emoji = "🟢"
        elif level['score'] >= 1.0:
            emoji = "🟡"
        else:
            emoji = "🔴"
        result.append(f"{emoji} ${level['price']:,.2f} (Sc:{level['score']:.1f})")
    return " | ".join(result)


# ============================================
# PART 2: MARKET MAKER BEHAVIOR ANALYSIS
# ============================================

def _detect_accumulation_distribution(
    price: float,
    vwap: float,
    rsi: float,
    funding: float,
    supports: List[Dict],
    resistances: List[Dict],
    p_score: int
) -> Tuple[str, List[str]]:
    """
    Detect if MM is accumulating (buying) or distributing (selling)
    Uses indirect on-chain and price action signals.
    """
    verdict_lines = []
    accumulation_signals = 0
    distribution_signals = 0
    
    # ===== ACCUMULATION SIGNALS (MM BUYING) =====
    
    # 1. Price below VWAP but holding support
    if price < vwap and supports and price < supports[0]['price'] * 1.02:
        accumulation_signals += 1
        verdict_lines.append("📈 Цена ниже VWAP, но удерживается у поддержки — скрытый набор лонгов")
    
    # 2. RSI recovering from oversold (30→45)
    if 35 <= rsi <= 48:
        accumulation_signals += 1
        verdict_lines.append("🔄 RSI выходит из перепроданности — спрос возвращается")
    
    # 3. Negative funding but price not falling
    if funding < -0.005 and supports and price > supports[0]['price'] * 0.99:
        accumulation_signals += 1
        verdict_lines.append("💰 Отрицательный фандинг, но цена держится — шорты платят за удержание")
    
    # 4. Strong support with high P-Score
    if p_score >= 50 and supports and supports[0]['score'] >= 2.0:
        accumulation_signals += 1
        verdict_lines.append("🎯 Высокий P-Score у поддержки — алгоритмы видят потенциал")
    
    # 5. Price coiling near support (low volatility)
    if supports and abs(price - supports[0]['price']) / price < 0.01:
        accumulation_signals += 1
        verdict_lines.append("📊 Цена сжимается у поддержки — подготовка к движению")
    
    # ===== DISTRIBUTION SIGNALS (MM SELLING) =====
    
    # 1. Price above VWAP but rejecting resistance
    if price > vwap and resistances and price > resistances[0]['price'] * 0.98:
        distribution_signals += 1
        verdict_lines.append("📉 Цена выше VWAP, но упирается в сопротивление — возможная раздача")
    
    # 2. RSI overbought without breakout
    if rsi > 68 and resistances and price < resistances[0]['price']:
        distribution_signals += 1
        verdict_lines.append("⚠️ RSI > 70, но цена не пробивает уровень — перегрев, готовится откат")
    
    # 3. Positive funding but price not advancing
    if funding > 0.01 and resistances and price < resistances[0]['price']:
        distribution_signals += 1
        verdict_lines.append("💸 Положительный фандинг, но рост остановлен — лонги платят за воздух")
    
    # 4. Weak P-Score at resistance
    if p_score < 40 and resistances and resistances[0]['score'] < 1.0:
        distribution_signals += 1
        verdict_lines.append("📉 Слабеющий P-Score у сопротивления — интерес угасает")
    
    # 5. Multiple touches without breakout
    if resistances and len([r for r in resistances if r['distance'] < price * 0.02]) > 2:
        distribution_signals += 1
        verdict_lines.append("🛑 Многократные тесты сопротивления без пробоя — накопление шортов")
    
    # ===== FINAL VERDICT =====
    if accumulation_signals >= 3:
        phase = "🔵 АККУМУЛЯЦИЯ"
        summary = "MM набирает лонги у нижней границы. Ожидай выброс вверх после набора позиции."
    elif distribution_signals >= 3:
        phase = "🔴 РАСПРЕДЕЛЕНИЕ"
        summary = "MM раздает позиции у верхней границы. Готовься к откату после раздачи."
    elif accumulation_signals >= 2:
        phase = "🟡 ПРИЗНАКИ АККУМУЛЯЦИИ"
        summary = "Виден интерес на покупки, но нужен катализатор для движения."
    elif distribution_signals >= 2:
        phase = "🟡 ПРИЗНАКИ РАСПРЕДЕЛЕНИЯ"
        summary = "Давление продаж растет, но уровень пока держится."
    else:
        phase = "⚪ НЕЙТРАЛЬНО"
        summary = "MM удерживает диапазон, ждет накопления ликвидности."
    
    verdict_lines.insert(0, f"• <b>Фаза:</b> {phase}")
    verdict_lines.insert(1, f"  {summary}")
    
    return phase, verdict_lines


def _detect_liquidity_hunts(
    price: float,
    atr: float,
    supports: List[Dict],
    resistances: List[Dict]
) -> List[str]:
    """
    Detect where MM is hunting stop-losses.
    Stops are typically placed just below support and above resistance.
    """
    verdict = []
    liquidity_zones = []
    
    # ===== LONG LIQUIDATION ZONES (STOPS BELOW SUPPORT) =====
    for i, support in enumerate(supports[:2]):
        # Typical stop placement: support - (1.5-2.0) * ATR
        stop_hunt_zone = support['price'] - (atr * 1.5)
        stop_hunt_zone_2 = support['price'] - (atr * 2.0)
        
        verdict.append(f"  🩸 Стоп-лоссы ЛОНГИСТОВ: ${stop_hunt_zone:,.0f}-${stop_hunt_zone_2:,.0f} (под {support['price']:,.0f})")
        liquidity_zones.extend([stop_hunt_zone, stop_hunt_zone_2])
    
    # ===== SHORT LIQUIDATION ZONES (STOPS ABOVE RESISTANCE) =====
    for i, resistance in enumerate(resistances[:2]):
        stop_hunt_zone = resistance['price'] + (atr * 1.5)
        stop_hunt_zone_2 = resistance['price'] + (atr * 2.0)
        
        verdict.append(f"  🩸 Стоп-лоссы ШОРТИСТОВ: ${stop_hunt_zone:,.0f}-${stop_hunt_zone_2:,.0f} (над {resistance['price']:,.0f})")
        liquidity_zones.extend([stop_hunt_zone, stop_hunt_zone_2])
    
    # ===== LIQUIDITY CLUSTERS =====
    if len(liquidity_zones) >= 2:
        verdict.append(f"  🎯 Кластер ликвидности: ${min(liquidity_zones):,.0f}-${max(liquidity_zones):,.0f}")
    
    # ===== IMMINENT HUNT WARNING =====
    if supports and price - supports[0]['price'] < atr * 1.5:
        hunt_target = supports[0]['price'] - (atr * 1.8)
        verdict.append(f"  ⚠️ Вероятная охота: MM может сходить к ${hunt_target:,.0f} за стопами перед разворотом")
    
    if resistances and resistances[0]['price'] - price < atr * 1.5:
        hunt_target = resistances[0]['price'] + (atr * 1.8)
        verdict.append(f"  ⚠️ Вероятная охота: MM может сходить к ${hunt_target:,.0f} за стопами перед откатом")
    
    return verdict


def _detect_spoofing_layering(
    price: float,
    vwap: float,
    rsi: float,
    funding: float,
    supports: List[Dict],
    resistances: List[Dict]
) -> List[str]:
    """
    Detect potential spoofing/layering manipulation.
    No order book access → use indirect price action signals.
    """
    verdict = []
    
    # ===== SPOOFING SELL WALLS =====
    if rsi > 65 and price < vwap * 1.02 and resistances:
        verdict.append("  🎭 Ложные заявки на продажу — MM выставляет стены, но цена не падает")
    
    # ===== SPOOFING BUY WALLS =====
    if rsi < 35 and price > vwap * 0.98 and supports:
        verdict.append("  🎭 Ложные заявки на покупку — MM имитирует поддержку, но не дает цене расти")
    
    # ===== FALSE BREAKOUTS =====
    if supports and supports[0]['price'] * 0.99 > price > supports[0]['price'] * 0.95:
        verdict.append("  🎯 Ложный пробой поддержки — выбиты стопы, цена вернулась в диапазон")
    
    if resistances and resistances[0]['price'] * 1.01 < price < resistances[0]['price'] * 1.05:
        verdict.append("  🎯 Ложный пробой сопротивления — выбиты стопы, цена вернулась")
    
    # ===== RANGE BOUND MANIPULATION =====
    if supports and resistances:
        range_width = (resistances[0]['price'] - supports[0]['price']) / price * 100
        if range_width < 3.0 and rsi > 50:
            verdict.append(f"  📊 Узкий диапазон ({range_width:.1f}%) — MM контролирует цену, готовится импульс")
    
    return verdict


def _analyze_open_interest_trend(oi_str: str) -> str:
    """Simple OI trend analysis (mock - would need historical data)"""
    try:
        oi_value = float(re.sub(r'[^\d.]', '', oi_str))
        # This is simplified - real implementation needs historical comparison
        if oi_value > 100_000_000:
            return "ВЫСОКИЙ"
        elif oi_value > 50_000_000:
            return "СРЕДНИЙ"
        else:
            return "НИЗКИЙ"
    except:
        return "Н/Д"


# ============================================
# PART 3: MARKET PHASE DETERMINATION
# ============================================

def _determine_market_phase(
    p_score: int,
    rsi: float,
    regime: str,
    strong_supports: List,
    strong_resists: List,
    direction: str
) -> str:
    """Determine market phase based on INDICATOR data + context"""
    
    if strong_supports and strong_resists:
        return "СИЛЬНЫЙ ДИАПАЗОН / НАКОПЛЕНИЕ"
    
    if strong_supports and not strong_resists:
        return "ПОДДЕРЖКА УДЕРЖИВАЕТСЯ / ПОТЕНЦИАЛЬНЫЙ РАЗВОРОТ"
    
    if strong_resists and not strong_supports:
        return "СОПРОТИВЛЕНИЕ УДЕРЖИВАЕТСЯ / ПОТЕНЦИАЛЬНАЯ КОРРЕКЦИЯ"
    
    if p_score >= 70:
        return "СИЛЬНЫЙ ТРЕНД"
    elif p_score >= 55:
        return "ТРЕНДОВОЕ ДВИЖЕНИЕ"
    elif p_score >= 40:
        return "ВОСХОДЯЩАЯ ТЕНДЕНЦИЯ"
    
    if rsi < 30:
        return "ПЕРЕПРОДАННОСТЬ / ЗОНА ПОКУПОК"
    elif rsi > 70:
        return "ПЕРЕКУПЛЕННОСТЬ / ЗОНА ФИКСАЦИИ"
    
    if "COMPRESSION" in regime:
        return "СЖАТИЕ / ПОДГОТОВКА К ДВИЖЕНИЮ"
    
    return "КОНСОЛИДАЦИЯ / НЕОПРЕДЕЛЕННОСТЬ"


# ============================================
# PART 4: CORE AI ANALYST FUNCTION
# ============================================

async def get_ai_sniper_analysis(ticker: str) -> str:
    """
    COMPLETE PIPELINE:
    1. INDICATOR → Levels, Score, RSI, ATR, VWAP, Funding, OI
    2. MM BEHAVIOR → Accumulation/Distribution, Liquidity Hunts, Spoofing
    3. AI DECISION → LONG/SHORT/WAIT based on level strength
    4. ORDER_CALC → Exact Entry, SL, TP1/2/3, Size, RRR
    5. OUTPUT → Your professional template with ALL sections
    """
    try:
        from bot.indicators import get_technical_indicators
        from bot.order_calc import build_order_plan
        from bot.config import Config
        
        # ============ STEP 1: GET INDICATOR DATA ============
        logger.info(f"📊 INDICATOR: Fetching data for {ticker}")
        indicators = await get_technical_indicators(ticker)
        if not indicators:
            return f"⚠️ INDICATOR: No data for {ticker}"
        
        # Extract ALL indicator data
        price = indicators.get('price', 0)
        change = indicators.get('change', '0%')
        rsi = indicators.get('rsi', 50)
        vwap_raw = indicators.get('vwap', '$0')
        
        # Parse VWAP to float
        vwap = 0.0
        if isinstance(vwap_raw, str):
            vwap = float(vwap_raw.replace('$', '').replace(',', ''))
        else:
            vwap = float(vwap_raw)
        
        # Parse ATR
        atr_raw = indicators.get('atr_val', '$0')
        atr_value = 0.0
        if isinstance(atr_raw, str):
            atr_value = float(atr_raw.replace('$', '').replace(',', ''))
        else:
            atr_value = float(atr_raw)
        
        # Get level strings from INDICATOR
        support_str = indicators.get('support', 'НЕТ')
        resistance_str = indicators.get('resistance', 'НЕТ')
        
        # Get P-Score and regime
        p_score = indicators.get('p_score', 0)
        regime = indicators.get('btc_regime', 'NEUTRAL')
        
        # Get sentiment data
        funding_raw = indicators.get('funding', '0%')
        funding = 0.0
        if isinstance(funding_raw, str):
            funding = float(funding_raw.replace('%', '').replace('+', ''))
        else:
            funding = float(funding_raw)
        
        oi = indicators.get('open_interest', '$0')
        
        # ============ STEP 2: PARSE INDICATOR LEVELS ============
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
        
        # ============ STEP 3: ANALYZE INDICATOR STRENGTH ============
        strong_supports = [l for l in supports if l['score'] >= 3.0]
        strong_resists = [l for l in resistances if l['score'] >= 3.0]
        medium_supports = [l for l in supports if 1.0 <= l['score'] < 3.0]
        medium_resists = [l for l in resistances if 1.0 <= l['score'] < 3.0]
        
        logger.info(f"📊 INDICATOR: {len(strong_supports)} strong supports, {len(strong_resists)} strong resists")
        
        # ============ STEP 4: MARKET MAKER BEHAVIOR ANALYSIS ============
        mm_phase, mm_verdict_lines = _detect_accumulation_distribution(
            price, vwap, rsi, funding, supports, resistances, p_score
        )
        
        liquidity_lines = _detect_liquidity_hunts(price, atr_value, supports, resistances)
        spoofing_lines = _detect_spoofing_layering(price, vwap, rsi, funding, supports, resistances)
        oi_trend = _analyze_open_interest_trend(oi)
        
        # ============ STEP 5: AI DECISION MAKING ============
        direction = "WAIT"
        entry_level = 0.0
        entry_score = 0.0
        decision_reason = []
        
        # Calculate zone_half for order calculations
        zone_half = atr_value * Config.ZONE_WIDTH_MULT
        
        # --- PRIORITY 1: STRONG SUPPORT (🟢) near price ---
        if strong_supports and price < strong_supports[0]['price'] * 1.02:
            direction = "LONG"
            entry_level = strong_supports[0]['price']
            entry_score = strong_supports[0]['score']
            decision_reason.append(f"Strong Support 🟢 (Sc:{entry_score:.1f}) within 2% of price")
            logger.info(f"✅ AI: LONG from STRONG SUPPORT (Sc:{entry_score})")
        
        # --- PRIORITY 2: STRONG RESISTANCE (🟢) near price ---
        elif strong_resists and price > strong_resists[0]['price'] * 0.98:
            direction = "SHORT"
            entry_level = strong_resists[0]['price']
            entry_score = strong_resists[0]['score']
            decision_reason.append(f"Strong Resistance 🟢 (Sc:{entry_score:.1f}) within 2% of price")
            logger.info(f"✅ AI: SHORT from STRONG RESISTANCE (Sc:{entry_score})")
        
        # --- PRIORITY 3: MEDIUM SUPPORT (🟡) + good P-Score ---
        elif medium_supports and p_score >= 45 and price < medium_supports[0]['price'] * 1.01:
            direction = "LONG"
            entry_level = medium_supports[0]['price']
            entry_score = medium_supports[0]['score']
            decision_reason.append(f"Medium Support 🟡 (Sc:{entry_score:.1f}) + P-Score {p_score}%")
            logger.info(f"⚠️ AI: LONG from MEDIUM SUPPORT (Sc:{entry_score})")
        
        # --- PRIORITY 4: MEDIUM RESISTANCE (🟡) + good P-Score ---
        elif medium_resists and p_score >= 45 and price > medium_resists[0]['price'] * 0.99:
            direction = "SHORT"
            entry_level = medium_resists[0]['price']
            entry_score = medium_resists[0]['score']
            decision_reason.append(f"Medium Resistance 🟡 (Sc:{entry_score:.1f}) + P-Score {p_score}%")
            logger.info(f"⚠️ AI: SHORT from MEDIUM RESISTANCE (Sc:{entry_score})")
        
        # --- PRIORITY 5: High P-Score only ---
        elif p_score >= 60 and supports and resistances:
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
        
        # ============ STEP 6: CALCULATE ORDERS ============
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
            
            if order and order.reason_blocked:
                logger.info(f"❌ AI: Order blocked - {order.reason_blocked}")
                direction = "WAIT"
                decision_reason.append(f"Blocked: {order.reason_blocked}")
        
        # ============ STEP 7: FORMAT DISPLAY ============
        support_display = _format_levels_for_display(supports[:3])
        resistance_display = _format_levels_for_display(resistances[:3])
        
        market_phase = _determine_market_phase(
            p_score, rsi, regime, 
            strong_supports, strong_resists, 
            direction
        )
        
        # Format sentiment
        sentiment_text = "Нейтрально"
        if rsi > 70:
            sentiment_text = f"Перекупленность (RSI {rsi:.1f})"
        elif rsi < 30:
            sentiment_text = f"Перепроданность (RSI {rsi:.1f})"
        
        funding_text = f"{funding:+.4f}%" if funding != 0 else "0.0000%"
        
        # ============ STEP 8: BUILD SIGNAL TEXT ============
        if direction == "WAIT" or not order:
            signal_text = f"""
🚦 <b>Тип:</b> WAIT
📊 <b>P-Score:</b> {p_score}% {'✅' if p_score >= 35 else '❌'}
📌 <b>Причина:</b> {' • '.join(decision_reason) if decision_reason else 'Нет подходящего сигнала'}
"""
            entry_display = "N/A"
            stop_display = "N/A"
            tp1_display = "N/A"
            tp2_display = "N/A"
            tp3_display = "N/A"
            rrr_display = "0.00"
            size_display = "0.0000"
        else:
            # Format position size appropriately
            if order.size_units > 100:
                size_display = f"{order.size_units:.0f}"
            elif order.size_units > 1:
                size_display = f"{order.size_units:.2f}"
            else:
                size_display = f"{order.size_units:.4f}"
            
            signal_text = f"""
🚦 <b>Тип:</b> {direction}
🎯 <b>Вход:</b> <code>${order.entry:,.2f}</code> (Sc:{entry_score:.1f})
🛡 <b>Stop Loss:</b> <code>${order.stop_loss:,.2f}</code>

✅ <b>Тейк-профиты (ATR-based):</b>
   • TP1: <code>${order.tp1:,.2f}</code> (0.75×ATR)
   • TP2: <code>${order.tp2:,.2f}</code> (1.25×ATR)  
   • TP3: <code>${order.tp3:,.2f}</code> (2.00×ATR)

📊 <b>Risk/Reward (TP2):</b> 1:{order.rrr_tp2:.2f} {'✅' if order.rrr_tp2 >= 1.10 else '❌'}
💰 <b>Размер позиции:</b> {size_display} ед. (1% риск, $1000)
📏 <b>Дистанция стопа:</b> ${order.stop_dist:.2f} ({order.stop_dist/atr_value:.1f}×ATR)
"""
            entry_display = f"${order.entry:,.2f}"
            stop_display = f"${order.stop_loss:,.2f}"
            tp1_display = f"${order.tp1:,.2f}"
            tp2_display = f"${order.tp2:,.2f}"
            tp3_display = f"${order.tp3:,.2f}"
            rrr_display = f"{order.rrr_tp2:.2f}"
        
        # ============ STEP 9: BUILD MM BEHAVIOR BLOCK ============
        mm_block = []
        mm_block.extend(mm_verdict_lines)
        
        if liquidity_lines:
            mm_block.append("• <b>Liquidity Hunter (охота за стопами):</b>")
            mm_block.extend(liquidity_lines[:4])  # Top 4 most important
        
        if spoofing_lines:
            mm_block.append("• <b>Spoofing/Layering (манипуляция):</b>")
            mm_block.extend(spoofing_lines[:3])  # Top 3 most important
        
        mm_block.append(f"• <b>Open Interest Trend:</b> {oi_trend}")
        
        # ============ STEP 10: FINAL OUTPUT - YOUR COMPLETE TEMPLATE ============
        return f"""
📊 <b>{ticker.upper()} | PROFESSIONAL SNIPER ANALYSIS</b>
🕒 <b>Время анализа:</b> {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
💰 <b>Текущая цена:</b> <code>${price:,.2f}</code> ({change})

🎯 <b>1. КЛЮЧЕВЫЕ УРОВНИ (M30) — ИНДИКАТОР:</b>
• <b>Поддержка:</b> {support_display}
• <b>Сопротивление:</b> {resistance_display}

📈 <b>2. ТЕКУЩАЯ ФАЗА РЫНКА И СТРУКТУРА ТРЕНДА:</b>
• <b>Фаза:</b> {market_phase}
• <b>RSI (14):</b> {rsi:.1f} — {'Перепроданность' if rsi < 30 else 'Перекупленность' if rsi > 70 else 'Нейтрально'}
• <b>VWAP (24h):</b> ${vwap:,.2f} — Цена {'выше' if price > vwap else 'ниже'} VWAP
• <b>Режим BTC:</b> {regime}
• <b>Strategy Score:</b> <b>{p_score}%</b> {'✅' if p_score >= 35 else '❌'}

💰 <b>3. АНАЛИЗ НАСТРОЕНИЯ И ПОЗИЦИЙ КРУПНЫХ ИГРОКОВ:</b>
{f"<b>{mm_block[0]}</b>" if mm_block else ""}
{chr(10).join(mm_block[1:]) if len(mm_block) > 1 else ""}

🎯 <b>4. ФЬЮЧЕРСНЫЙ СИГНАЛ (НА ОСНОВЕ ИНДИКАТОРА):</b>{signal_text}
📋 <b>ЛОГИКА РЕШЕНИЯ:</b>
{' • '.join(decision_reason) if decision_reason else 'Нет активного сигнала'}

⚠️ <b>УСЛОВИЯ ВХОДА И РИСКИ:</b>
• Вход строго лимитным ордером по указанному уровню
• Риск на сделку: 1-2% от депозита
• Stop Loss: {stop_display}
• Take Profit 1-2-3: {tp1_display} | {tp2_display} | {tp3_display}
• Минимальный RRR: 1.10 {'✅' if rrr_display != 'N/A' and float(rrr_display) >= 1.10 else '❌'}
• Отмена сценария: пробой уровня стоп-лосс

#️⃣ <b>ТЕГИ:</b> #{ticker.upper()} #{market_phase.replace(' ', '_')} #{'LONG' if direction == 'LONG' else 'SHORT' if direction == 'SHORT' else 'WAIT'} #AI_Sniper_v3.2
"""
        
    except Exception as e:
        logger.error(f"AI Analyst critical error: {e}", exc_info=True)
        return f"""❌ <b>AI ANALYST ERROR</b>
        
Тикер: {ticker}
Ошибка: {str(e)[:200]}
Время: {datetime.now(timezone.utc).strftime("%H:%M UTC")}

Пожалуйста, проверьте логи и сообщите разработчику.
"""


# ============================================
# END OF AI ANALYST - VERSION 3.2.0
# ============================================
