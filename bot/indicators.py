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


def process_levels(
    df: pd.DataFrame, 
    max_dist_pct: float = 30.0
) -> tuple[List[dict], List[dict]]:
    """Process OHLCV data to find support/resistance levels."""
    levels: List[Level] = []
    pending: List[dict] = []
    
    if 'atr' not in df.columns:
        df['atr'] = calculate_atr(df)
    
    atr = df['atr'].values
    high = df['high'].values
    low = df['low'].values
    L, R = 4, 4
    start_idx = max(TRADING.atr_len, L + R)
    
    for i in range(start_idx, len(df) - R):
        if np.isnan(atr[i]):
            continue
        
        is_pivot_h = True
        is_pivot_l = True
        
        for j in range(1, L + 1):
            if high[i] < high[i-j] or high[i] < high[i+j]:
                is_pivot_h = False
            if low[i] > low[i-j] or low[i] > low[i+j]:
                is_pivot_l = False
        
        if is_pivot_h:
            pending.append({
                'idx': i, 'price': high[i], 'is_res': True, 
                'atr': atr[i], 'check_at': i + TRADING.react_bars
            })
        if is_pivot_l:
            pending.append({
                'idx': i, 'price': low[i], 'is_res': False, 
                'atr': atr[i], 'check_at': i + TRADING.react_bars
            })
        
        active_pending: List[dict] = []
        for p in pending:
            if i >= p['check_at']:
                reaction_dist = TRADING.k_react * p['atr']
                confirmed = False
                window_low = np.min(low[p['idx']:i+1])
                window_high = np.max(high[p['idx']:i+1])
                
                if p['is_res']:
                    if (p['price'] - window_low) >= reaction_dist:
                        confirmed = True
                else:
                    if (window_high - p['price']) >= reaction_dist:
                        confirmed = True
                
                if confirmed:
                    merged = False
                    merge_tol = TRADING.merge_atr * p['atr']
                    for lvl in levels:
                        if lvl.is_res == p['is_res'] and abs(lvl.price - p['price']) < merge_tol:
                            lvl.update(p['price'], p['atr'], i)
                            merged = True
                            break
                    if not merged:
                        levels.append(Level(
                            price=p['price'],
                            is_res=p['is_res'],
                            atr=p['atr'],
                            touches=1,
                            last_touch_idx=i,
                            created_at=i
                        ))
            else:
                active_pending.append(p)
        pending = active_pending

    current_idx = len(df) - 1
    current_price = df['close'].iloc[-1]
    active_supports: List[dict] = []
    active_resistances: List[dict] = []
    
    for lvl in levels:
        score = lvl.get_score(current_idx, current_price)
        dist_pct = abs(lvl.price - current_price) / current_price * 100
        if dist_pct > max_dist_pct:
            continue
        data = {'price': lvl.price, 'score': score}
        if lvl.is_res and lvl.price > current_price:
            active_resistances.append(data)
        elif not lvl.is_res and lvl.price < current_price:
            active_supports.append(data)
    
    active_supports.sort(key=lambda x: abs(x['price'] - current_price))
    active_resistances.sort(key=lambda x: abs(x['price'] - current_price))
    return active_supports[:3], active_resistances[:3]


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
    
    if (is_support_target and rsi < 35) or (not is_support_target and rsi > 65):
        score += 5
        details.append("• RSI Контекст: +5% (Контртренд)")
    else:
        details.append("• RSI Контекст: 0% (Нейтрально)")
    
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
    
    def empty_response(reason: str) -> dict[str, Any]:
        return {
            "action": "WAIT", "reason": reason,
            "entry": 0, "stop": 0, "tp1": 0, "tp2": 0, "tp3": 0,
            "risk_pct": 0, "position_size": 0, "risk_amount": 0, "rrr": 0
        }

    if p_score < 35:
        return empty_response(f"Strategy Score {p_score}% низкий (нужно >35%).")
    if is_sup_target and rsi > 70:
        return empty_response("RSI > 70 у поддержки (Overbought).")
    if not is_sup_target and rsi < 30:
        return empty_response("RSI < 30 у сопротивления (Oversold).")

    funding_threshold = 0.0003
    if funding > funding_threshold and is_sup_target and current_price < vwap:
        return empty_response(f"Sentiment Trap: Фандинг перегрет ({(funding*100):.3f}%) + Цена < VWAP.")
    if funding < -funding_threshold and not is_sup_target and current_price > vwap:
        return empty_response(f"Sentiment Trap: Фандинг отрицательный ({(funding*100):.3f}%) + Цена > VWAP.")

    stop_buffer = atr * 1.5
    if is_sup_target:
        action = "LONG"
        entry = s1
        stop = s1 - stop_buffer
        dist = abs(r1 - s1)
        tp1 = entry + (dist * 0.3)
        tp2 = entry + (dist * 0.6)
        tp3 = r1 - (atr * 0.2)
    else:
        action = "SHORT"
        entry = r1
        stop = r1 + stop_buffer
        dist = abs(r1 - s1)
        tp1 = entry - (dist * 0.3)
        tp2 = entry - (dist * 0.6)
        tp3 = s1 + (atr * 0.2)

    risk_amount_usd = capital * (risk_percent / 100.0)
    price_diff = abs(entry - stop)
    
    if price_diff > 0 and entry > 0:
        position_size = risk_amount_usd / price_diff
        risk_pct_distance = (price_diff / entry) * 100
        potential_profit = abs(tp3 - entry)
        rrr = potential_profit / price_diff
    else:
        position_size = 0
        risk_pct_distance = 0
        rrr = 0

    return {
        "action": action,
        "reason": f"Setup Valid. Score: {p_score}%. RRR: 1:{rrr:.1f}",
        "entry": entry, "stop": stop, "tp1": tp1, "tp2": tp2, "tp3": tp3,
        "risk_pct": round(risk_pct_distance, 2),
        "position_size": position_size,
        "risk_amount": round(risk_amount_usd, 2),
        "rrr": round(rrr, 1)
    }


async def get_technical_indicators(ticker: str) -> Optional[dict[str, Any]]:
    """Get all technical indicators for a ticker (Legacy for /sniper)."""
    exchange = ccxt.binance(EXCHANGE_OPTIONS["binance"])
    
    try:
        # Fetch data in parallel
        m30_task = fetch_ohlcv_data(exchange, f"{ticker.upper()}/USDT", TRADING.timeframe, limit=1500)
        btc_task = fetch_ohlcv_data(exchange, "BTC/USDT", TRADING.timeframe, limit=1500)
        funding_task = fetch_funding_rate(exchange, f"{ticker.upper()}/USDT")
        oi_task = fetch_open_interest(exchange, f"{ticker.upper()}/USDT")

        df, btc_df, funding_rate, open_interest = await asyncio.gather(
            m30_task, btc_task, funding_task, oi_task
        )
        
        if df is None or df.empty:
            return None

        df['atr'] = calculate_atr(df)
        df['rsi'] = calculate_rsi(df)
        regime, safety = calculate_global_regime(btc_df)
        m30_sup, m30_res = process_levels(df, max_dist_pct=30.0)
        
        current_price = df['close'].iloc[-1]
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
            "strategy": strat
        }
    finally:
        await exchange.close()
