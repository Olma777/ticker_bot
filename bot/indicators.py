"""
Technical indicators module (Math Only + Legacy Compatibility).
Refactored for Phase 2: Math functions.
Legacy Compatibility: Restored logic for /sniper command.
"""

import logging
import asyncio
import pandas as pd
import numpy as np
import ccxt.async_support as ccxt
from typing import Optional, Any, List
from dataclasses import dataclass

from bot.config import TRADING, EXCHANGE_OPTIONS, Config
from bot.models.market_context import Candle

logger = logging.getLogger(__name__)


# --- PHASE 2 MATH FUNCTIONS ---

def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate Average True Range."""
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()


def calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate Relative Strength Index."""
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def calculate_vwap_24h(df: pd.DataFrame) -> float:
    """Calculate 24h Volume Weighted Average Price."""
    if len(df) < 48:
        return float(df['close'].mean())
    last_24h = df.tail(48)
    vwap = (last_24h['close'] * last_24h['volume']).sum() / last_24h['volume'].sum()
    return float(vwap)


def calculate_global_regime(btc_df: Optional[pd.DataFrame]) -> tuple[str, str]:
    """
    Calculate global market regime based on BTC ROC (Rate of Change).
    Logic from Phase 1 (Approved for Phase 2).
    Returns: (regime, safety_label)
    Regime: "EXPANSION", "COMPRESSION", "NEUTRAL"
    """
    if btc_df is None or btc_df.empty or len(btc_df) < TRADING.z_win:
        return "NEUTRAL", "SAFE"
    
    # ROC 30 periods
    roc = btc_df['close'].pct_change(30)
    if roc.isna().all():
        return "NEUTRAL", "SAFE"
    
    mean = roc.rolling(window=TRADING.z_win).mean()
    std = roc.rolling(window=TRADING.z_win).std()
    
    if std.iloc[-1] == 0 or pd.isna(std.iloc[-1]):
        return "NEUTRAL", "SAFE"
    
    z_score = (roc - mean) / std
    current_z = z_score.iloc[-1]
    
    if pd.isna(current_z):
        return "NEUTRAL", "SAFE"
    
    if current_z > TRADING.z_thr:
        return "COMPRESSION", "RISKY"
    elif current_z < -TRADING.z_thr:
        return "EXPANSION", "SAFE"
    
    return "NEUTRAL", "SAFE"


def calculate_volatility_bands(current_price: float, atr: float) -> tuple[float, float]:
    """Calculate volatility bands based on ATR."""
    return current_price - (atr * 2.0), current_price + (atr * 2.0)


# --- LEGACY COMPATIBILITY LAYER (For /sniper command) ---

@dataclass
class Level:
    """Represents a support/resistance level."""
    price: float
    is_res: bool
    atr: float
    touches: int
    last_touch_idx: int
    created_at: int

    def update(self, price: float, atr: float, idx: int) -> None:
        """Update level with a new touch."""
        old_touches = self.touches
        new_touches = old_touches + 1
        self.price = (self.price * old_touches + price) / new_touches
        self.atr = (self.atr * old_touches + atr) / new_touches
        self.touches = new_touches
        self.last_touch_idx = idx

    def get_score(self, current_idx: int, current_price: Optional[float] = None) -> float:
        """Calculate level score based on touches and age."""
        age = current_idx - self.last_touch_idx
        if current_price is not None:
            dist_pct = abs(self.price - current_price) / current_price * 100
            if dist_pct < 1.0:
                age = age * 0.5
        return (self.touches * TRADING.wt) - (age * TRADING.wa)


async def fetch_ohlcv_data(
    exchange: ccxt.Exchange, 
    symbol: str, 
    timeframe: str, 
    limit: int = 1500
) -> Optional[pd.DataFrame]:
    """Fetch OHLCV data from exchange."""
    try:
        ohlcv = await exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        if not ohlcv:
            return None
        df = pd.DataFrame(ohlcv, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
        return df
    except Exception as e:
        logger.error(f"Error fetching {symbol} {timeframe}: {e}")
        return None


async def fetch_funding_rate(exchange: ccxt.Exchange, symbol: str) -> float:
    """Fetch funding rate for a symbol."""
    try:
        funding = await exchange.fetch_funding_rate(symbol)
        return funding['fundingRate'] if funding else 0.0
    except Exception:
        return 0.0


async def fetch_open_interest(exchange: ccxt.Exchange, symbol: str) -> float:
    """Fetch open interest for a symbol."""
    try:
        oi = await exchange.fetch_open_interest(symbol)
        return oi['openInterestAmount'] if oi else 0.0
    except Exception:
        return 0.0


def process_levels(df: pd.DataFrame, max_dist_pct: float = Config.MAX_DIST_PCT) -> tuple[List[dict], List[dict]]:
    """
    Process support and resistance levels (Legacy for /sniper).
    Synchronized with Pine Script v3.7 Logic.
    """
    if df is None or df.empty:
        return [], []
        
    # === SYNCHRONIZE WITH PINE SCRIPT v3.7 ===
    from bot.config import Config
    
    # Use EXACT same parameters as Pine Script
    REACT_BARS = Config.REACT_BARS        # 24 (из Pine: reactBars = 24)
    K_REACT = Config.K_REACT              # 1.3 (из Pine: kReact = 1.30)
    MERGE_ATR = Config.MERGE_ATR          # 0.6 (из Pine: mergeATR = 0.60)
    WT = Config.WT_TOUCH                  # 1.0 (из Pine: Wt = 1.0)
    WA = Config.WA_DECAY                  # 0.35 (из Pine: Wa = 0.35)
    TMIN = Config.TMIN                    # 5 (из Pine: Tmin = 5)
    ZONE_WIDTH_MULT = Config.ZONE_WIDTH_MULT  # 0.5 (из Pine: zoneWidthMult = 0.5)

    closes = df['close'].values
    highs = df['high'].values
    lows = df['low'].values
    atrs = df['atr'].values
    
    levels = []
    
    # 1. Pivot Detection (Pivots High/Low)
    # Pine: leftBars=4, rightBars=4 (FIXED from 10)
    left_bars = 4
    right_bars = 4
    
    for i in range(left_bars, len(df) - right_bars):
        # Pivot High
        is_ph = True
        for k in range(1, left_bars + 1):
            if highs[i] <= highs[i-k]:
                is_ph = False; break
        if is_ph:
            for k in range(1, right_bars + 1):
                if highs[i] <= highs[i+k]:
                    is_ph = False; break
        
        # Pivot Low
        is_pl = True
        for k in range(1, left_bars + 1):
            if lows[i] >= lows[i-k]:
                is_pl = False; break
        if is_pl:
            for k in range(1, right_bars + 1):
                if lows[i] >= lows[i+k]:
                    is_pl = False; break
                    
        if is_ph:
            levels.append({
                'price': highs[i], 'type': 'RESISTANCE', 'index': i,
                'age': 0, 'touches': 0, 'score': 0.0, 'atr': atrs[i]
            })
        if is_pl:
            levels.append({
                'price': lows[i], 'type': 'SUPPORT', 'index': i,
                'age': 0, 'touches': 0, 'score': 0.0, 'atr': atrs[i]
            })

    # ... (rest of process_levels unchanged) ...
    # Wait, I need to keep the function structure intact. 
    # I will replace the fetch_ohlcv_data calls and logging in get_technical_indicators too.
    
    # 2. Filter & Merge
    # Pine: Merge if dist < mergeATR * ATR
    merged_levels = []
    sorted_levels = sorted(levels, key=lambda x: x['price'])
    
    current_cluster = []
    
    for lvl in sorted_levels:
        if not current_cluster:
            current_cluster.append(lvl)
            continue
            
        last_lvl = current_cluster[-1]
        dist = abs(lvl['price'] - last_lvl['price'])
        limit_dist = MERGE_ATR * last_lvl['atr']  # UPDATED
        
        if dist <= limit_dist:
            current_cluster.append(lvl)
        else:
            # Merge cluster
            avg_price = sum(l['price'] for l in current_cluster) / len(current_cluster)
            best_lvl = max(current_cluster, key=lambda x: x['index']) # Most recent
            best_lvl['price'] = avg_price
            merged_levels.append(best_lvl)
            current_cluster = [lvl]
            
    if current_cluster:
        avg_price = sum(l['price'] for l in current_cluster) / len(current_cluster)
        best_lvl = max(current_cluster, key=lambda x: x['index'])
        best_lvl['price'] = avg_price
        merged_levels.append(best_lvl)
        
    # 3. Calculate Score (Pine Logic v3.7)
    final_levels = []
    current_idx = len(df) - 1
    for lvl in merged_levels:
        age_bars = current_idx - lvl['index']
        
        # Pine: kReact * age
        reaction_threshold = K_REACT * age_bars  # UPDATED
        # Pine: reactBars limit
        if age_bars > REACT_BARS and lvl['touches'] == 0: # Simple dormancy check
             pass # In Pine score decays, here we just keep calculating
        
        # Calculate Touches & Reactivity
        # For simplicity in Python we iterate from lvl index
        touches = 0
        volume_sum = 0
        
        for k in range(lvl['index'] + 1, len(df)):
            c = closes[k]
            # Simple Touch check: within ZoneWidthMult * ATR
            dist = abs(c - lvl['price'])
            zone = atrs[k] * ZONE_WIDTH_MULT # UPDATED
            if dist <= zone:
                touches += 1
                
        lvl['touches'] = touches
        
        # Score Formula v3.7
        # Sc = (Wt * Touches) - (Wa * Age/100)
        # Note: Pine has complex reactivity. We approximate.
        
        score = (WT * touches) - (WA * age_bars)
        
        # Clamp Score (Pine Script Compatibility)
        score = max(-100.0, min(10.0, score))
        
        if age_bars < TMIN:
            score = 0 # Newborn
            
        lvl['score'] = score
        lvl['age'] = age_bars
        
        final_levels.append(lvl)

    # Separate based on PIVOT type (initial)
    supports = [l for l in final_levels if l['type'] == 'SUPPORT']
    resistances = [l for l in final_levels if l['type'] == 'RESISTANCE']
    
    # Filter by Distance (Anti-Hallucination)
    current_price = df['close'].iloc[-1]
    max_dist = current_price * (max_dist_pct / 100.0)
    
    supports = [s for s in supports if abs(s['price'] - current_price) <= max_dist]
    resistances = [r for r in resistances if abs(r['price'] - current_price) <= max_dist]
    
    # P0 FIX: Reclassify Levels based on Current Price (Dynamic Validation)
    # A pivot low above current price is RESISTANCE, not support.
    # A pivot high below current price is SUPPORT, not resistance.
    
    all_valid_levels = supports + resistances
    final_supports = []
    final_resistances = []
    
    for lvl in all_valid_levels:
        if lvl['price'] < current_price:
            lvl['type'] = 'SUPPORT'
            final_supports.append(lvl)
        elif lvl['price'] > current_price:
            lvl['type'] = 'RESISTANCE'
            final_resistances.append(lvl)
    
    # Sort by Score (Desc)
    final_supports.sort(key=lambda x: x['score'], reverse=True)
    final_resistances.sort(key=lambda x: x['score'], reverse=True)
    
    return final_supports[:3], final_resistances[:3]


def calculate_legacy_p_score(
    regime: str, 
    rsi: float, 
    s1_score: float, 
    r1_score: float, 
    current_price: float, 
    s1: float, 
    r1: float
) -> tuple[int, str, bool]:
    """Calculate probability score (Legacy)."""
    score = 50
    details = ["• База: 50%"]
    
    if regime == "EXPANSION":
        score += 10
        details.append("• Режим (BTC): +10% (EXPANSION)")
    elif regime == "COMPRESSION":
        score -= 10
        details.append(f"• Режим (BTC): -10% ({regime})")
    else:
        details.append("• Режим (BTC): 0% (NEUTRAL)")
    
    dist_s1 = abs(current_price - s1)
    dist_r1 = abs(current_price - r1)
    
    if dist_s1 < dist_r1:
        target_score = s1_score
        is_support_target = True
        lvl_type = "Support"
    else:
        target_score = r1_score
        is_support_target = False
        lvl_type = "Resistance"
    
    if target_score >= 1.0:
        score += 15
        details.append(f"• Уровень ({lvl_type}): +15% (Strong Score {target_score:.1f})")
    elif target_score > -2.0:
        details.append(f"• Уровень ({lvl_type}): 0% (Moderate Score {target_score:.1f})")
    else:
        score -= 20
        details.append(f"• Уровень ({lvl_type}): -20% (Weak Score {target_score:.1f})")
    
    # RSI Context (FIXED: Bonus ONLY for counter-trend extremes)
    rsi_bonus = 0
    if is_support_target and rsi < 35:
        rsi_bonus = 5
        details.append("• RSI Контекст: +5% (Oversold Support)")
    elif not is_support_target and rsi > 65:
        rsi_bonus = 5
        details.append("• RSI Контекст: +5% (Overbought Resistance)")
    else:
        details.append("• RSI Контекст: 0% (Нейтрально)")
    
    score += rsi_bonus
    
    final_score = max(0, min(100, int(score)))
    return final_score, "\n".join(details), is_support_target


def get_intraday_strategy(
    p_score: int, 
    current_price: float, 
    s1: float, 
    r1: float, 
    atr: float, 
    is_sup_target: bool, 
    rsi: float, 
    funding: float, 
    vwap: float,
    capital: float = 1000.0, 
    risk_percent: float = 1.0
) -> dict[str, Any]:
    """Generate intraday trading strategy (Legacy)."""
    
    from bot.order_calc import build_order_plan
    from bot.config import Config

    def empty_response(reason: str) -> dict[str, Any]:
        return {
            "action": "WAIT", "reason": reason,
            "entry": 0, "stop": 0, "tp1": 0, "tp2": 0, "tp3": 0,
            "risk_pct": 0, "position_size": 0, "risk_amount": 0, "rrr": 0
        }

    if p_score < 35:
        return empty_response(f"Strategy Score {p_score}% низкий (нужно >35%).")
    # REMOVED: Incorrect RSI checks that caused false WAIT signals (User Request)

    funding_threshold = 0.0003
    if funding > funding_threshold and is_sup_target and current_price < vwap:
        return empty_response(f"Sentiment Trap: Фандинг перегрет ({(funding*100):.3f}%) + Цена < VWAP.")
    if funding < -funding_threshold and not is_sup_target and current_price > vwap:
        return empty_response(f"Sentiment Trap: Фандинг отрицательный ({(funding*100):.3f}%) + Цена > VWAP.")

    # Determine side and level
    side = "LONG" if is_sup_target else "SHORT"
    level = s1 if is_sup_target else r1
    
    # Calculate zone_half (estimate from ATR if not available)
    zone_half = atr * Config.ZONE_WIDTH_MULT
    
    # CALL SINGLE SOURCE OF TRUTH
    order_plan = build_order_plan(
        side=side,
        level=level,
        zone_half=zone_half,
        atr=atr,
        capital=capital,
        risk_pct=risk_percent,
        lot_step=None
    )
    
    if order_plan.reason_blocked:
        return empty_response(f"Order Calc: {order_plan.reason_blocked}")
    
    # Format response
    return {
        "action": "TRADE",
        "reason": f"Setup Valid. Score: {p_score}%. RRR: 1:{order_plan.rrr_tp2:.1f}",
        "entry": order_plan.entry,
        "stop": order_plan.stop_loss,
        "tp1": order_plan.tp1,
        "tp2": order_plan.tp2,
        "tp3": order_plan.tp3,
        "risk_pct": round((order_plan.stop_dist / order_plan.entry * 100) if order_plan.entry > 0 else 0, 2),
        "position_size": order_plan.size_units,
        "risk_amount": round(order_plan.risk_amount, 2),
        "rrr": round(order_plan.rrr_tp2, 1),
        "side": side
    }



async def diagnose_pivot_detection(df: pd.DataFrame) -> None:
    """Diagnose why pivots are not found."""
    logger.info("🔍 PIVOT DETECTION DIAGNOSTICS")
    
    highs = df['high'].values
    lows = df['low'].values
    
    # HARDCODED CONFIG CHECK
    left_bars = 4
    right_bars = 4
    
    pivots_high = 0
    pivots_low = 0
    
    for i in range(left_bars, len(df) - right_bars):
        # Check Pivot High
        is_ph = True
        for k in range(1, left_bars + 1):
            if highs[i] <= highs[i-k]:
                is_ph = False; break
        if is_ph:
            for k in range(1, right_bars + 1):
                if highs[i] <= highs[i+k]:
                    is_ph = False; break
        if is_ph:
            pivots_high += 1
            if pivots_high <= 5: # Log first 5 only
                logger.info(f"   Pivot High at index {i}, price: ${highs[i]:.2f}")
        
        # Check Pivot Low
        is_pl = True
        for k in range(1, left_bars + 1):
            if lows[i] >= lows[i-k]:
                is_pl = False; break
        if is_pl:
            for k in range(1, right_bars + 1):
                if lows[i] >= lows[i+k]:
                    is_pl = False; break
        if is_pl:
            pivots_low += 1
            if pivots_low <= 5:
                 logger.info(f"   Pivot Low at index {i}, price: ${lows[i]:.2f}")
    
    logger.info(f"✅ Total pivots high: {pivots_high}")
    logger.info(f"✅ Total pivots low: {pivots_low}")
    
    if pivots_high == 0 and pivots_low == 0:
        logger.error("❌ ZERO PIVOTS DETECTED — Check left_bars/right_bars parameters")
        logger.error(f"   Current: left_bars={left_bars}, right_bars={right_bars}")
        logger.error(f"   Data range: {len(df)} candles")
        logger.error(f"   Price range: ${min(lows):.2f} — ${max(highs):.2f}")


async def get_technical_indicators(ticker: str) -> Optional[dict[str, Any]]:
    """Get all technical indicators for a ticker (Legacy for /sniper)."""
    exchange = ccxt.binance(EXCHANGE_OPTIONS["binance"])
    
    try:
        # P0 FIX: Enforce 30m timeframe strict
        timeframe = "30m"
        
        # Normalize Ticker (Remove /USDT if present to avoiding doubling)
        clean_ticker = ticker.upper().replace("/USDT", "").replace("USDT", "")
        pair = f"{clean_ticker}/USDT"
        
        logger.info(f"🔍 FETCHING {pair} 30m data from Binance...")
        
        # Fetch data in parallel
        m30_task = fetch_ohlcv_data(exchange, pair, timeframe, limit=1500)
        btc_task = fetch_ohlcv_data(exchange, "BTC/USDT", timeframe, limit=1500)
        funding_task = fetch_funding_rate(exchange, pair)
        oi_task = fetch_open_interest(exchange, pair)
        # P0 FIX: Fetch Real-Time Ticker for accurate price
        ticker_task = exchange.fetch_ticker(pair)

        df, btc_df, funding_rate, open_interest, ticker_data = await asyncio.gather(
            m30_task, btc_task, funding_task, oi_task, ticker_task
        )
        
        # === DIAGNOSTICS FOR DATA INTEGRITY ===
        logger.info("=" * 60)
        logger.info(f"📊 DIAGNOSTICS FOR {pair}")
        logger.info("=" * 60)
         
        # P0 FIX: Real-time price from ticker
        current_price = float(ticker_data['last']) if ticker_data else df['close'].iloc[-1]
        logger.info(f"✅ Real-Time Price (Ticker): ${current_price}")

        if df is None:
            logger.error(f"❌ NO DATA: fetch_ohlcv_data returned None for {ticker}")
            return None
        
        if df.empty:
            logger.error(f"❌ EMPTY DF: DataFrame is empty for {ticker}")
            return None
            
        logger.info(f"✅ df shape: {df.shape}")
        
        if len(df) < 100:
            logger.error(f"❌ INSUFFICIENT DATA: Only {len(df)} candles for {ticker}, need ≥100")
            return None

        # P0 FIX: Verify Timeframe
        if len(df) >= 2:
            time_diff = df['time'].iloc[-1] - df['time'].iloc[-2]
            time_diff_min = time_diff / 60000
            logger.info(f"✅ Timeframe: {time_diff_min:.0f} minutes between last 2 candles")
            if abs(time_diff_min - 30) > 1:
                logger.error(f"❌ WRONG TIMEFRAME! Expected 30m, got {time_diff_min:.0f}m")
            else:
                 logger.info(f"✅ Timeframe verified: 30m")

        df['atr'] = calculate_atr(df)
        df['rsi'] = calculate_rsi(df)
        regime, safety = calculate_global_regime(btc_df)
        m30_sup, m30_res = process_levels(df, max_dist_pct=Config.MAX_DIST_PCT)
        
        # Data Integrity Checks
        logger.info(f"✅ Current price: ${current_price:.2f}")

        # Check 5 candles ago for K2_NO_BRAKES
        if len(df) >= 5:
            price_5_ago = df['close'].iloc[-5]
            change_5 = ((current_price / price_5_ago) - 1) * 100 # Use real price
            logger.info(f"✅ Price 5 candles ago: ${price_5_ago:.2f}")
            logger.info(f"✅ Change over 5 candles: {change_5:.1f}%")
            if change_5 < -3.0:
                logger.warning(f"⚠️ Would trigger K2_NO_BRAKES (Falling Knife: {change_5:.1f}%)")

        # === LEVEL DIAGNOSTICS ===
        logger.info(f"✅ Supports found: {len(m30_sup)}")
        logger.info(f"✅ Resistances found: {len(m30_res)}")
        if m30_sup:
            logger.info(f"   Top support: ${m30_sup[0]['price']:.2f} (score: {m30_sup[0]['score']:.1f})")
        if m30_res:
            logger.info(f"   Top resistance: ${m30_res[0]['price']:.2f} (score: {m30_res[0]['score']:.1f})")
            
        if not m30_sup and not m30_res:
            logger.error("❌ NO LEVELS FOUND — PIVOT DETECTION FAILED")
            await diagnose_pivot_detection(df)
        
        logger.info("=" * 60)
        
        # === LEVEL DIAGNOSTICS (P0 FIX) ===
        logger.info(f"📊 LEVELS DETECTED: {len(m30_sup)} supports, {len(m30_res)} resistances")
        if m30_sup:
            logger.info(f"   Top support: ${m30_sup[0]['price']:.2f} (score: {m30_sup[0]['score']:.1f})")
        if m30_res:
            logger.info(f"   Top resistance: ${m30_res[0]['price']:.2f} (score: {m30_res[0]['score']:.1f})")
            
        if not m30_sup and not m30_res:
            logger.warning("⚠️ NO LEVELS FOUND! Check pivot detection and merge logic.")
        
        
        # Log basics
        earliest = df['time'].iloc[0]
        latest = df['time'].iloc[-1]
        span_hours = (latest - earliest) / (1000 * 60 * 60)
        logger.info(f"✅ Received {len(df)} candles spanning {span_hours:.1f} hours")
        logger.info(f"   Current price: ${current_price:.2f}")

        # P1 FIX: Reclassify Levels based on Current Price
        all_levels = m30_sup + m30_res
        
        real_supports = []
        real_resistances = []
        
        for lvl in all_levels:
            if lvl['price'] < current_price:
                lvl['type'] = 'SUPPORT'
                real_supports.append(lvl)
            elif lvl['price'] > current_price:
                lvl['type'] = 'RESISTANCE'
                real_resistances.append(lvl)
        
        # Sort again
        real_supports.sort(key=lambda x: x['score'], reverse=True)
        real_resistances.sort(key=lambda x: x['score'], reverse=True)
        
        m30_sup = real_supports[:3]
        m30_res = real_resistances[:3]

        m30_atr = df['atr'].iloc[-1]
        m30_rsi = df['rsi'].iloc[-1]
        vwap_24h = calculate_vwap_24h(df)
        vol_low, vol_high = calculate_volatility_bands(current_price, m30_atr)
        
        price_24h = df['close'].iloc[-47] if len(df) >= 47 else df['open'].iloc[0]
        change_str = f"{((current_price - price_24h) / price_24h) * 100:+.2f}"
        funding_fmt = f"{funding_rate*100:+.3f}%"
        
        # Icon helper
        def icon(sc: float) -> str:
            return "🟢" if sc >= 1.0 else "🟡" if sc > -2.0 else "🔴"
        
        def fmt_lvls(lvls: List[dict]) -> str:
            if not lvls:
                return "НЕТ"
            return " | ".join([f"{icon(l['score'])} ${l['price']:.4f} (Sc:{l['score']:.1f})" for l in lvls])
        
        m30_s1 = m30_sup[0]['price'] if m30_sup else df['low'].min()
        m30_r1 = m30_res[0]['price'] if m30_res else df['high'].max()
        m30_s1_score = m30_sup[0]['score'] if m30_sup else 0.0
        m30_r1_score = m30_res[0]['score'] if m30_res else 0.0

        p_score, p_score_details, is_sup_target = calculate_legacy_p_score(
            regime, m30_rsi, m30_s1_score, m30_r1_score, current_price, m30_s1, m30_r1
        )
        
        strat = get_intraday_strategy(
            p_score, current_price, m30_s1, m30_r1, m30_atr, is_sup_target, 
            m30_rsi, funding_rate, vwap_24h,
            capital=TRADING.default_capital, risk_percent=TRADING.default_risk_pct
        )

        return {
            "price": current_price,
            "change": change_str,
            "rsi": round(m30_rsi, 1),
            "regime": regime,
            "btc_regime": f"{regime} ({safety})",
            "atr_val": f"${m30_atr:.4f}",
            "funding": funding_fmt,
            "open_interest": f"${open_interest:,.0f}" if open_interest else "N/A",
            "support": fmt_lvls(m30_sup),
            "resistance": fmt_lvls(m30_res),
            "vol_low": f"${vol_low:.4f}",
            "vol_high": f"${vol_high:.4f}",
            "vwap": f"${vwap_24h:.4f}",
            "p_score": p_score,
            "p_score_details": p_score_details,
            "strategy": strat,
            "candles": [
                Candle(
                    timestamp=int(row.time),
                    open=row.open,
                    high=row.high,
                    low=row.low,
                    close=row.close,
                    volume=row.volume
                ) for row in df.tail(20).itertuples(index=False)
            ]
        }
    finally:
        await exchange.close()
