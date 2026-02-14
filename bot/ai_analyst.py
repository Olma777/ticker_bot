"""
AI Analyst Module - FINAL VERSION
INDICATOR DRIVEN + MM BEHAVIOR + ORDER CALC
Complete integration of all requirements.
"""

import logging
import re
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple
from bot.models.market_context import MarketContext
from bot.kevlar import check_safety_v2
from bot.formatting import format_price_universal as _format_price


def draw_bar(value, total=100, length=10):
    """
    Draw a progress bar using '▓' and '░' characters.
    
    Args:
        value: Current value
        total: Maximum value (default 100)
        length: Length of the bar in characters (default 10)
    
    Returns:
        String representing the progress bar
    """
    # Calculate the percentage
    percentage = min(100, max(0, (value / total) * 100)) if total > 0 else 0
    
    # Calculate how many filled characters we need
    filled_length = int(length * percentage / 100)
    
    # Create the bar
    bar = '▓' * filled_length + '░' * (length - filled_length)
    
    return bar

logger = logging.getLogger(__name__)


# ============================================
# PART 1: INDICATOR DATA PARSING
# ============================================

def _parse_levels(level_str: str, current_price: float) -> List[Dict]:
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
                    'distance': abs(current_price - price),
                    'score': score,
                    'is_support': is_support,
                    'strength': 'STRONG' if score >= 3.0 else 'MEDIUM' if score >= 1.0 else 'WEAK'
                })
        except Exception:
            continue
    return levels



# Helper _format_price replaced by import from bot.formatting


def _format_levels_for_display(levels: List[Dict], count: int = 3) -> str:
    """Format INDICATOR levels with proper emoji based on SCORE.
    Webhook levels have high positive scores (1-10+).
    Local levels have negative scores (-100 to 0). Use neutral icon for those.
    """
    if not levels:
        return "НЕТ"
    result = []
    for level in levels[:count]:
        sc = level.get('score', 0)
        if sc >= 3.0:
            emoji = "🟢"  # Strong (webhook confirmed)
        elif sc >= 1.0:
            emoji = "🟡"  # Medium
        elif sc >= -2.0:
            emoji = "⚪"  # Neutral / locally calculated
        else:
            emoji = "🔴"  # Weak
        result.append(f"{emoji} {_format_price(level['price'])} (Sc:{sc:.1f})")
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
        dist_vwap = ((vwap - price) / vwap) * 100
        dist_support = ((supports[0]['price'] - price) / supports[0]['price']) * 100
        verdict_lines.append(f"📈 Price is {dist_vwap:.1f}% below VWAP, holding {dist_support:.1f}% above support")
    
    # 2. RSI recovering from oversold (30→45)
    if 35 <= rsi <= 48:
        accumulation_signals += 1
        rsi_change = rsi - 30 if rsi > 30 else 0
        verdict_lines.append(f"🔄 RSI {rsi:.1f} recovering from oversold (+{rsi_change:.1f} points)")
    
    # 3. Negative funding but price not falling
    if funding < -0.005 and supports and price > supports[0]['price'] * 0.99:
        accumulation_signals += 1
        verdict_lines.append(f"💰 Funding {funding*100:.3f}% negative, price holding support")
    
    # 4. Strong support with high P-Score
    if p_score >= 50 and supports and supports[0]['score'] >= 2.0:
        accumulation_signals += 1
        verdict_lines.append(f"🎯 P-Score {p_score} with strong support (score: {supports[0]['score']:.1f})")
    
    # 5. Price coiling near support (low volatility)
    if supports and abs(price - supports[0]['price']) / price < 0.01:
        accumulation_signals += 1
        dist_percent = abs(price - supports[0]['price']) / price * 100
        verdict_lines.append(f"📊 Price coiling {dist_percent:.1f}% near support")
    
    # ===== DISTRIBUTION SIGNALS (MM SELLING) =====
    
    # 1. Price above VWAP but rejecting resistance
    if price > vwap and resistances and price > resistances[0]['price'] * 0.98:
        distribution_signals += 1
        dist_vwap = ((price - vwap) / vwap) * 100
        dist_resistance = ((price - resistances[0]['price']) / resistances[0]['price']) * 100
        verdict_lines.append(f"📉 Price is {dist_vwap:.1f}% above VWAP, rejecting {dist_resistance:.1f}% below resistance")
    
    # 2. RSI overbought without breakout
    if rsi > 68 and resistances and price < resistances[0]['price']:
        distribution_signals += 1
        verdict_lines.append(f"⚠️ RSI {rsi:.1f} overbought, price below resistance")
    
    # 3. Positive funding but price not advancing
    if funding > 0.01 and resistances and price < resistances[0]['price']:
        distribution_signals += 1
        verdict_lines.append(f"💸 Funding {funding*100:.3f}% positive, price stalled at resistance")
    
    # 4. Weak P-Score at resistance
    if p_score < 40 and resistances and resistances[0]['score'] < 1.0:
        distribution_signals += 1
        verdict_lines.append(f"📉 P-Score {p_score} weak at resistance (score: {resistances[0]['score']:.1f})")
    
    # 5. Multiple touches without breakout
    if resistances and len([r for r in resistances if r['distance'] < price * 0.02]) > 2:
        distribution_signals += 1
        touch_count = len([r for r in resistances if r['distance'] < price * 0.02])
        verdict_lines.append(f"🛑 {touch_count} resistance touches without breakout")
    
    # ===== FINAL VERDICT =====
    if accumulation_signals >= 3:
        phase = "🔵 ACCUMULATION"
        summary = f"Accumulation signals: {accumulation_signals}, distribution: {distribution_signals}"
    elif distribution_signals >= 3:
        phase = "🔴 DISTRIBUTION"
        summary = f"Distribution signals: {distribution_signals}, accumulation: {accumulation_signals}"
    elif accumulation_signals >= 2:
        phase = "🟡 ACCUMULATION SIGNS"
        summary = f"Accumulation signals: {accumulation_signals}, distribution: {distribution_signals}"
    elif distribution_signals >= 2:
        phase = "🟡 DISTRIBUTION SIGNS"
        summary = f"Distribution signals: {distribution_signals}, accumulation: {accumulation_signals}"
    else:
        phase = "⚪ NEUTRAL"
        summary = f"Accumulation: {accumulation_signals}, distribution: {distribution_signals}"
    
    verdict_lines.insert(0, f"• <b>Phase:</b> {phase}")
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
    РЕАЛЬНЫЕ стопы: 3-5% от уровня (НЕ ATR!)
    """
    verdict = []
    liquidity_zones = []
    
    # ===== LONG LIQUIDATION ZONES (СТОПЫ ПОД ПОДДЕРЖКОЙ) =====
    # ФИЛЬТР: Только ближайшие уровни (5%)
    relevant_supports = [s for s in supports[:2] if abs(s['price'] - price) / price < 0.05]
    
    # ===== FORMATTER HELPER =====
    def _fmt_price_for_liq(p: float) -> str:
        if p < 1:
            return f"${p:.4f}"
        elif p < 100:
            return f"${p:.2f}"
        else:
            return f"${p:,.0f}"

    for i, support in enumerate(relevant_supports):
        # РЕАЛЬНЫЕ стопы: -3% и -5%
        stop_hunt_zone = support['price'] * 0.97  # -3%
        stop_hunt_zone_2 = support['price'] * 0.95  # -5%
        
        verdict.append(
            f"  🩸 Стоп-лоссы ЛОНГИСТОВ: "
            f"{_fmt_price_for_liq(stop_hunt_zone_2)}-{_fmt_price_for_liq(stop_hunt_zone)} "
            f"(под {_fmt_price_for_liq(support['price'])})"
        )
        liquidity_zones.extend([stop_hunt_zone, stop_hunt_zone_2])
    
    # ===== SHORT LIQUIDATION ZONES (СТОПЫ НАД СОПРОТИВЛЕНИЕМ) =====
    # ФИЛЬТР: Только ближайшие уровни (5%)
    relevant_resistances = [r for r in resistances[:2] if abs(r['price'] - price) / price < 0.05]
    
    for i, resistance in enumerate(relevant_resistances):
        stop_hunt_zone = resistance['price'] * 1.03  # +3%
        stop_hunt_zone_2 = resistance['price'] * 1.05  # +5%
        
        verdict.append(
            f"  🩸 Стоп-лоссы ШОРТИСТОВ: "
            f"{_fmt_price_for_liq(resistance['price'])}-{_fmt_price_for_liq(stop_hunt_zone_2)} "
            f"(над {_fmt_price_for_liq(resistance['price'])})"
        )
        liquidity_zones.extend([stop_hunt_zone, stop_hunt_zone_2])
    
    # ===== LIQUIDITY CLUSTERS =====
    if len(liquidity_zones) >= 2:
        verdict.append(
            f"  🎯 Кластер ликвидности: "
            f"{_fmt_price_for_liq(min(liquidity_zones))}-{_fmt_price_for_liq(max(liquidity_zones))}"
        )
    
    # ===== IMMINENT HUNT WARNING =====
    if supports:
        dist_to_support = (price - supports[0]['price']) / price * 100
        if 0 < dist_to_support < 3.0:  # Цена в 3% от поддержки
            hunt_target = supports[0]['price'] * 0.95
            verdict.append(
                f"  ⚠️ Вероятная охота: MM может сходить к "
                f"{_fmt_price_for_liq(hunt_target)} за стопами перед разворотом"
            )
    
    if resistances:
        dist_to_resist = (resistances[0]['price'] - price) / price * 100
        if 0 < dist_to_resist < 3.0:  # Цена в 3% от сопротивления
            hunt_target = resistances[0]['price'] * 1.05
            verdict.append(
                f"  ⚠️ Вероятная охота: MM может сходить к "
                f"{_fmt_price_for_liq(hunt_target)} за стопами перед откатом"
            )
    
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


# ============ STEP 3.5: UNIVERSAL VALIDATION ============

def validate_entry_for_any_ticker(
    price: float,
    entry: float,
    direction: str,
    supports: List[Dict],
    resistances: List[Dict],
    atr: float
) -> Tuple[bool, str]:
    """
    Universal entry validation for any ticker (BTC, SHIB, etc.).
    Checks for Air Entry and Direction mismatch.
    Score check REMOVED — local levels have negative scores by design.
    """
    if direction == "WAIT" or entry == 0:
        return False, "No entry signal"

    # 2. Direction vs Level Type & Proximity
    if direction == "LONG":
        # Entry must be near a SUPPORT level
        if not supports:
            return False, "No support levels for LONG"
        
        nearest = min(supports, key=lambda x: abs(x['price'] - entry))
        
        # Rule: < 5% Distance from Level (Air Entry Protection)
        dist_pct = abs(entry - nearest['price']) / entry
        if dist_pct > 0.05:
             return False, f"Air Entry: Too far from support ({dist_pct*100:.2f}% > 5%)"

    elif direction == "SHORT":
        # Entry must be near a RESISTANCE level
        if not resistances:
            return False, "No resistance levels for SHORT"
            
        nearest = min(resistances, key=lambda x: abs(x['price'] - entry))
        
        # Rule: < 5% Distance from Level
        dist_pct = abs(entry - nearest['price']) / entry
        if dist_pct > 0.05:
             return False, f"Air Entry: Too far from resistance ({dist_pct*100:.2f}% > 5%)"

    return True, "Valid"


async def get_ai_sniper_analysis(ticker: str) -> Dict:
    """
    COMPLETE PIPELINE с гарантированной инициализацией всех переменных
    """
    # ============ ИНИЦИАЛИЗАЦИЯ ВСЕХ ПЕРЕМЕННЫХ (ОБЯЗАТЕЛЬНО) ============
    direction = "WAIT"
    entry_level = 0.0
    order = None
    ai_analysis = ""
    supports = []
    resistances = []
    indicators = None
    price = 0.0
    atr_value = 0.0
    p_score = 0
    kevlar_res = None
    ctx = None
    
    try:
        from bot.indicators import get_technical_indicators
        from bot.order_calc import build_order_plan
        from bot.config import Config
        from bot.models.market_context import MarketContext
        from bot.prices import get_price
        
        logger.info(f"📊 INDICATOR: Fetching data for {ticker}")
        
        # ============ STEP 1: GET INDICATOR DATA ============
        indicators = await get_technical_indicators(ticker)
        if not indicators:
            return {
                "status": "ERROR", 
                "reason": f"No data for {ticker}", 
                "symbol": ticker,
                "type": "WAIT",
                "sl": 0, "tp1": 0, "tp2": 0, "tp3": 0, "rrr": 0
            }
        
        # Извлечение данных с проверками (P0 FIX: Real-time Price)
        # price = indicators.get('price', 0) <- OLD
        try:
             price = await get_price(ticker, force_refresh=True)
        except Exception as e:
             logger.warning(f"Force refresh price failed, utilizing indicator price: {e}")
             price = indicators.get('price', 0)
        atr_raw = indicators.get('atr_val', '$0')
        if isinstance(atr_raw, str):
            atr_value = float(atr_raw.replace('$', '').replace(',', ''))
        else:
            atr_value = float(atr_raw)

        # Валидация данных
        if price <= 0 or atr_value <= 0:
            return {
                "status": "ERROR",
                "reason": f"Invalid market data (Price={price}, ATR={atr_value})",
                "symbol": ticker,
                "type": "WAIT",
                "sl": 0, "tp1": 0, "tp2": 0, "tp3": 0, "rrr": 0
            }

        change = indicators.get('change', '0%')
        rsi = indicators.get('rsi', 50)
        vwap_raw = indicators.get('vwap', '$0')
        vwap = float(vwap_raw.replace('$', '').replace(',', '')) if isinstance(vwap_raw, str) else float(vwap_raw)
            
        funding_raw = indicators.get('funding', '0%')
        funding = float(funding_raw.replace('%', '').replace('+', '')) / 100.0 if isinstance(funding_raw, str) else float(funding_raw)
            
        p_score = indicators.get('p_score', 0)
        regime = indicators.get('btc_regime', 'NEUTRAL')
        regime_safety = indicators.get('regime_safety', 'UNKNOWN')
        level_source = indicators.get('level_source', 'LOCAL')
        
        # ============ STEP 2: BUILD CONTEXT ============
        ctx = MarketContext(
            symbol=ticker,
            price=price,
            btc_regime=regime.split()[0].lower(),
            atr=atr_value,
            vwap=vwap,
            funding_rate=funding,
            timestamp=datetime.now(),
            candle_open=0, candle_high=0, candle_low=0, candle_close=0,
            data_quality="OK",
            rsi=rsi,
            candles=indicators.get('candles', [])
        )

        # ============ STEP 3: GET LEVELS (TradingView → Local Fallback) ============
        # Priority: raw dicts from MarketDataProvider (already resolved in indicators.py)
        supports = indicators.get('supports_raw', [])
        resistances = indicators.get('resistances_raw', [])
        
        # Fallback: parse formatted strings (legacy path)
        if not supports and not resistances:
            support_str = indicators.get('support', 'НЕТ')
            resistance_str = indicators.get('resistance', 'НЕТ')
            supports = _parse_levels(support_str, price)
            resistances = _parse_levels(resistance_str, price)
            level_source = "LOCAL_PARSED"
        
        # Ensure 'distance' field exists for all levels
        for lvl in supports + resistances:
            if 'distance' not in lvl:
                lvl['distance'] = abs(price - lvl['price'])
        
        logger.info(f"📊 {ticker} Levels [{level_source}]: {len(supports)} SUP, {len(resistances)} RES")

        # ============ STEP 3B: REGIME SAFETY ADJUSTMENT ============
        # RISKY regime = raise P-Score threshold for entry (soft gate, not hard block)
        min_pscore_for_entry = 35  # default
        if regime_safety == 'RISKY':
            min_pscore_for_entry = 40  # need stronger signal in risky markets
            logger.info(f"⚠️ {ticker}: BTC regime RISKY → P-Score threshold raised to {min_pscore_for_entry}")

        # ============ STEP 4: AI DECISION MAKING ============
        # Use ALL available levels — don't hard-filter by score
        # Score is informational (webhook levels have high scores, local have negative — but both are valid)
        
        # DIAGNOSTIC LOGGING
        sup_info = [f"${l['price']}(Sc:{l.get('score',0):.1f})" for l in supports]
        res_info = [f"${l['price']}(Sc:{l.get('score',0):.1f})" for l in resistances]
        logger.info(f"📊 {ticker} STEP 4: p_score={p_score}, min_threshold={min_pscore_for_entry}, price=${price}")
        logger.info(f"   Supports: {sup_info}")
        logger.info(f"   Resists:  {res_info}")
        
        # Strategy side hint from get_intraday_strategy
        strat = indicators.get('strategy', {})
        strat_side = strat.get('side', 'NEUTRAL')
        strat_action = strat.get('action', 'WAIT')
        logger.info(f"   Strategy hint: side={strat_side}, action={strat_action}")
        
        if p_score >= min_pscore_for_entry:
            # Find nearest support below price
            sups_below = [l for l in supports if l['price'] < price]
            if sups_below:
                best_support = min(sups_below, key=lambda x: abs(x['price'] - price))
                sup_dist = (price - best_support['price']) / price
            else:
                best_support = None
                sup_dist = 999
            
            # Find nearest resistance above price
            ress_above = [l for l in resistances if l['price'] > price]
            if ress_above:
                best_resist = min(ress_above, key=lambda x: abs(x['price'] - price))
                res_dist = (best_resist['price'] - price) / price
            else:
                best_resist = None
                res_dist = 999
            
            sup_label = f"${best_support['price']}" if best_support else "NONE"
            res_label = f"${best_resist['price']}" if best_resist else "NONE"
            logger.info(f"   Nearest SUP: {sup_label} @ {sup_dist*100:.1f}%")
            logger.info(f"   Nearest RES: {res_label} @ {res_dist*100:.1f}%")
            
            # Decision: closer to support → LONG, closer to resistance → SHORT
            max_dist = 0.05  # 5% maximum distance to consider a level
            
            if sup_dist < res_dist and sup_dist <= max_dist and best_support:
                direction = "LONG"
                entry_level = best_support['price']
                logger.info(f"   → LONG from SUP ${entry_level} (dist {sup_dist*100:.1f}%)")
            elif res_dist <= sup_dist and res_dist <= max_dist and best_resist:
                direction = "SHORT"
                entry_level = best_resist['price']
                logger.info(f"   → SHORT from RES ${entry_level} (dist {res_dist*100:.1f}%)")
            elif strat_side in ("LONG", "SHORT") and strat_action == "TRADE":
                # Use strategy hint as fallback
                if strat_side == "LONG" and best_support and sup_dist <= max_dist:
                    direction = "LONG"
                    entry_level = best_support['price']
                elif strat_side == "SHORT" and best_resist and res_dist <= max_dist:
                    direction = "SHORT"
                    entry_level = best_resist['price']
                logger.info(f"   → {direction} from strategy hint")
            
            if direction == "WAIT":
                logger.warning(f"   ❌ No level within {max_dist*100:.0f}%")
        else:
            logger.info(f"   ❌ P-Score {p_score} < {min_pscore_for_entry} → skipping level scan")
        
        # ============ STEP 4B: ANTI-TRAP (only block if VERY close to opposite level) ============
        # More lenient: only block if within 0.3% of opposite strong level (webhook levels score > 3)
        strong_resists = [l for l in resistances if l.get('score', 0) >= 3.0]
        strong_supports = [l for l in supports if l.get('score', 0) >= 3.0]
        
        if direction == "LONG" and strong_resists:
            nearest_res = min(strong_resists, key=lambda x: abs(x['price'] - price))
            if nearest_res['price'] > price and (nearest_res['price'] - price) / price < 0.003:
                logger.warning(f"⚠️ ANTI-TRAP: LONG blocked — price too close to STRONG RES {nearest_res['price']}")
                direction = "WAIT"
                entry_level = 0.0
        
        if direction == "SHORT" and strong_supports:
            nearest_sup = min(strong_supports, key=lambda x: abs(x['price'] - price))
            if nearest_sup['price'] < price and (price - nearest_sup['price']) / price < 0.003:
                logger.warning(f"⚠️ ANTI-TRAP: SHORT blocked — price too close to STRONG SUP {nearest_sup['price']}")
                direction = "WAIT"
                entry_level = 0.0
        
        logger.info(f"   FINAL DECISION: {direction} entry={entry_level}")

        # ============ STEP 5: KEVLAR CHECK (after levels for accurate distance) ============
        strat = indicators.get('strategy', {})
        start_side = strat.get('side', 'NEUTRAL')
        event_type = "SUPPORT" if direction == "LONG" or start_side == "LONG" else "RESISTANCE" if direction == "SHORT" or start_side == "SHORT" else "CHECK"
        
        # Use nearest level for Kevlar distance check (not current price)
        kevlar_level = entry_level if entry_level > 0 else price
        
        from bot.kevlar import check_safety_v2
        kevlar_res = check_safety_v2({"event": event_type, "level": str(kevlar_level)}, ctx, p_score)
        
        if not kevlar_res.passed:
            return {
                "status": "BLOCKED",
                "reason": kevlar_res.blocked_by,
                "symbol": ticker,
                "p_score": p_score,
                "kevlar_passed": False,
                "type": "WAIT",
                "sl": 0, "tp1": 0, "tp2": 0, "tp3": 0, "rrr": 0
            }
        
        # ============ STEP 5B: MARKET MAKER BEHAVIOR ANALYSIS ============
        mm_phase, mm_verdict_lines = _detect_accumulation_distribution(
            price, vwap, rsi, funding, supports, resistances, p_score
        )
        
        liquidity_lines = _detect_liquidity_hunts(price, atr_value, supports, resistances)
        
        # ============ STEP 6: UNIVERSAL VALIDATION ============
        if direction != "WAIT":
            is_valid, val_reason = validate_entry_for_any_ticker(
                price, entry_level, direction, supports, resistances, atr_value
            )
            if not is_valid:
                logger.warning(f"⛔ VALIDATION BLOCKED {ticker}: {val_reason}")
                return {
                    "status": "BLOCKED",
                    "reason": f"Validation Failed: {val_reason}",
                    "symbol": ticker,
                    "type": "WAIT",
                    "p_score": p_score,
                    "sl": 0, "tp1": 0, "tp2": 0, "tp3": 0, "rrr": 0
                }

        # ============ STEP 7: CALCULATE ORDERS ============
        if direction != "WAIT" and entry_level > 0:
            order = build_order_plan(
                side=direction,
                level=entry_level,
                zone_half=atr_value * Config.ZONE_WIDTH_MULT,
                atr=atr_value,
                capital=1000.0,
                risk_pct=1.0
            )
            
            if order and order.reason_blocked:
                return {
                    "status": "BLOCKED",
                    "reason": f"Order Blocked: {order.reason_blocked}",
                    "symbol": ticker,
                    "type": "WAIT",
                    "p_score": p_score,
                    "sl": 0, "tp1": 0, "tp2": 0, "tp3": 0, "rrr": 0
                }
        else:
            # Build detailed reason for diagnostics
            reasons = []
            if p_score < min_pscore_for_entry:
                reasons.append(f"P-Score {p_score} < {min_pscore_for_entry}")
            all_levels = supports + resistances
            if not all_levels:
                reasons.append("No levels found")
            else:
                nearest = min(all_levels, key=lambda x: abs(x['price'] - price))
                d = abs(nearest['price'] - price) / price * 100
                reasons.append(f"Nearest level ${nearest['price']:.4f} @ {d:.1f}% (max 5%)")
            
            detail = "; ".join(reasons) if reasons else "Unknown"
            logger.warning(f"⛔ {ticker} NO TRADE: {detail}")
            
            return {
                "status": "BLOCKED", 
                "reason": f"No valid setup: {detail}", 
                "symbol": ticker,
                "type": "WAIT",
                "p_score": p_score,
                "sl": 0, "tp1": 0, "tp2": 0, "tp3": 0, "rrr": 0
            }

        # ============ STEP 7: AI CONTEXTUAL ANALYSIS ============
        # Теперь direction ТОЧНО не "WAIT", можно безопасно использовать
        try:
            if p_score >= Config.P_SCORE_THRESHOLD:
                # Подготовка данных для AI
                all_context_supports = [l for l in supports if l['distance'] / price <= Config.MAX_DIST_PCT / 100]
                all_context_resists = [l for l in resistances if l['distance'] / price <= Config.MAX_DIST_PCT / 100]
                
                from bot.analysis import _generate_ai_contextual_analysis
                ai_analysis = await _generate_ai_contextual_analysis(
                    ticker=ticker,
                    price=price,
                    change=change,
                    rsi=rsi,
                    funding=funding,
                    oi=indicators.get('open_interest', 'N/A'),
                    supports=all_context_supports,  # Pass ALL relevant levels
                    resistances=all_context_resists,
                    p_score=p_score,
                    mm_phase=mm_phase,
                    mm_verdict=mm_verdict_lines,
                    liquidity_hunts=liquidity_lines,
                    spoofing_signals=_detect_spoofing_layering(price, vwap, rsi, funding, supports, resistances),
                    btc_regime=regime,
                    direction=direction,
                    entry=entry_level
                )
        except Exception as e:
            logger.error(f"AI analysis integration failed: {e}")
            ai_analysis = "⚠️ AI-анализ временно недоступен"

        # ============ STEP 8: RETURN SUCCESS ============
        # Гарантированно order существует (проверено выше)
        if order is None:
            return {
                "status": "BLOCKED",
                "reason": "Order calculation failed",
                "symbol": ticker,
                "type": "WAIT",
                "p_score": p_score,
                "sl": 0, "tp1": 0, "tp2": 0, "tp3": 0, "rrr": 0
            }
        
        # Форматирование уровней для отображения
        visible_supports = [l for l in supports if l['distance'] / price <= Config.MAX_DIST_PCT / 100]
        visible_resists = [l for l in resistances if l['distance'] / price <= Config.MAX_DIST_PCT / 100]
        visible_supports.sort(key=lambda x: x['distance'])
        visible_resists.sort(key=lambda x: x['distance'])
        
        return {
            "status": "OK",
            "type": "TRADE",
            "symbol": ticker,
            "side": direction.lower(),
            "entry": entry_level,
            "sl": order.stop_loss, # Renamed from stop
            "tp1": order.tp1,
            "tp2": order.tp2,
            "tp3": order.tp3,
            "rrr": order.rrr_tp2,
            "p_score": p_score,
            "kevlar_passed": True,
            "kevlar_reason": "Passed",
            
            # ========= NEW FIELDS =========
            "mm_phase": mm_phase,
            "mm_verdict": mm_verdict_lines,
            "liquidity_hunts": liquidity_lines,
            "spoofing_signals": _detect_spoofing_layering(price, vwap, rsi, funding, supports, resistances),
            "strong_supports": _format_levels_for_display(visible_supports, 5), # Show up to 5
            "strong_resists": _format_levels_for_display(visible_resists, 5),   # Show up to 5
            "ai_analysis": ai_analysis,
            
            # Logic
            "logic_setup": f"Setup found: {direction} from {_format_price(entry_level)}",
            "logic_summary": mm_verdict_lines[0].lstrip("• ").strip() if mm_verdict_lines else "Market Neutral",
            
            "rsi": rsi,
            "change": float(change.replace('%', '').replace('+', '')) if '%' in change else 0.0,
            "current_price": price
        }
        
    except Exception as e:
        logger.error(f"AI Analyst critical error: {e}", exc_info=True)
        return {
            "status": "ERROR",
            "reason": str(e),
            "symbol": ticker,
            "type": "WAIT",
            "sl": 0, "tp1": 0, "tp2": 0, "tp3": 0, "rrr": 0
        }


# ============================================
# END OF AI ANALYST - VERSION 3.2.0
# ============================================
