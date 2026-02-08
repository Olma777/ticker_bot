import ccxt.async_support as ccxt
import pandas as pd
import numpy as np
import logging
import asyncio

logger = logging.getLogger(__name__)

# --- SETTINGS ---
SETTINGS = {
    'timeframe': '30m', 
    'swing_timeframe': '1d', 
    'reactBars': 24,    
    'kReact': 1.3,
    'mergeATR': 0.6,
    'Wt': 1.0,          
    'Wa': 0.35,         
    'Tmin': 5,          
    'scMin': -100.0,    
    'maxDistPct': 50.0, 
    'atrLen': 14,
    'zWin': 180,        
    'zThr': 1.25
}

class Level:
    def __init__(self, price, is_res, atr, created_at):
        self.price = price
        self.is_res = is_res
        self.atr = atr
        self.touches = 1
        self.last_touch_idx = created_at
        self.created_at = created_at

    def update(self, price, atr, idx):
        old_touches = self.touches
        new_touches = old_touches + 1
        self.price = (self.price * old_touches + price) / new_touches
        self.atr = (self.atr * old_touches + atr) / new_touches 
        self.touches = new_touches
        self.last_touch_idx = idx

    def get_score(self, current_idx):
        age = current_idx - self.last_touch_idx
        return (self.touches * SETTINGS['Wt']) - (age * SETTINGS['Wa'])

async def fetch_ohlcv_data(exchange, symbol, timeframe, limit=1500):
    try:
        ohlcv = await exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        if not ohlcv: return None
        df = pd.DataFrame(ohlcv, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
        return df
    except Exception as e:
        logger.error(f"Error fetching {symbol} {timeframe}: {e}")
        return None

async def fetch_funding_rate(exchange, symbol):
    try:
        funding = await exchange.fetch_funding_rate(symbol)
        return funding['fundingRate'] if funding else 0.0
    except Exception:
        return 0.0

async def fetch_open_interest(exchange, symbol):
    try:
        oi = await exchange.fetch_open_interest(symbol)
        return oi['openInterestAmount'] if oi else 0.0
    except Exception:
        return 0.0

def calculate_atr(df, period=14):
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()

def calculate_rsi(df, period=14):
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_global_regime(btc_df):
    if btc_df is None or len(btc_df) < SETTINGS['zWin']: return "NEUTRAL", "SAFE"
    roc = btc_df['close'].pct_change(30)
    mean = roc.rolling(window=SETTINGS['zWin']).mean()
    std = roc.rolling(window=SETTINGS['zWin']).std()
    if std.iloc[-1] == 0 or pd.isna(std.iloc[-1]): return "NEUTRAL", "SAFE"
    z_score = (roc - mean) / std
    current_z = z_score.iloc[-1]
    if pd.isna(current_z): return "NEUTRAL", "SAFE"
    if current_z > SETTINGS['zThr']: regime = "COMPRESSION"
    elif current_z < -SETTINGS['zThr']: regime = "EXPANSION"
    else: regime = "NEUTRAL"
    safety = "RISKY" if regime == "COMPRESSION" else "SAFE"
    return regime, safety

def process_levels(df, timeframe_scaler=1.0, max_dist_pct=50.0):
    levels = []
    pending = []
    atr = df['atr'].values
    high = df['high'].values
    low = df['low'].values
    close = df['close'].values
    
    L, R = 4, 4 
    start_idx = max(SETTINGS['atrLen'], L + R)
    
    for i in range(start_idx, len(df) - R):
        is_pivot_h = True
        is_pivot_l = True
        for j in range(1, L + 1):
            if high[i] < high[i-j] or high[i] < high[i+j]: is_pivot_h = False
            if low[i] > low[i-j] or low[i] > low[i+j]: is_pivot_l = False
            
        if is_pivot_h: pending.append({'idx': i, 'price': high[i], 'is_res': True, 'atr': atr[i], 'check_at': i + SETTINGS['reactBars']})
        if is_pivot_l: pending.append({'idx': i, 'price': low[i], 'is_res': False, 'atr': atr[i], 'check_at': i + SETTINGS['reactBars']})
            
        active_pending = []
        for p in pending:
            if i >= p['check_at']:
                reaction_dist = SETTINGS['kReact'] * p['atr'] * timeframe_scaler
                confirmed = False
                window_low = np.min(low[p['idx'] : i+1])
                window_high = np.max(high[p['idx'] : i+1])
                
                if p['is_res']:
                    if (p['price'] - window_low) >= reaction_dist: confirmed = True
                else:
                    if (window_high - p['price']) >= reaction_dist: confirmed = True
                
                if confirmed:
                    merged = False
                    merge_tol = SETTINGS['mergeATR'] * p['atr'] * timeframe_scaler
                    for lvl in levels:
                        if lvl.is_res == p['is_res'] and abs(lvl.price - p['price']) < merge_tol:
                            lvl.update(p['price'], p['atr'], i)
                            merged = True
                            break
                    if not merged: levels.append(Level(p['price'], p['is_res'], p['atr'], i))
            else: active_pending.append(p)
        pending = active_pending

    current_idx = len(df) - 1
    current_price = close[-1]
    active_supports = []
    active_resistances = []
    
    for lvl in levels:
        score = lvl.get_score(current_idx)
        # DISTANCE FILTER
        dist_pct = abs(lvl.price - current_price) / current_price * 100
        if dist_pct > max_dist_pct: continue
        
        data = {'price': lvl.price, 'score': score}
        if lvl.is_res and lvl.price > current_price: active_resistances.append(data)
        elif not lvl.is_res and lvl.price < current_price: active_supports.append(data)
    
    active_supports.sort(key=lambda x: abs(x['price'] - current_price))
    active_resistances.sort(key=lambda x: abs(x['price'] - current_price))
    
    return active_supports[:3], active_resistances[:3]

def estimate_liquidation_levels(current_price, atr):
    long_liq = current_price - (atr * 2.0) 
    short_liq = current_price + (atr * 2.0)
    return long_liq, short_liq

def calculate_p_score(regime, rsi, s1_score, r1_score, current_price, s1, r1):
    score = 50 
    details = ["База: 50%"]
    
    if regime == "EXPANSION": 
        score += 10
        details.append("Режим: +10% (EXPANSION)")
    elif regime in ["COMPRESSION", "NEUTRAL"]: 
        score -= 10
        details.append(f"Режим: -10% ({regime})")
    
    dist_s1 = abs(current_price - s1)
    dist_r1 = abs(current_price - r1)
    
    if dist_s1 < dist_r1:
        target_score = s1_score
        is_support_target = True
    else:
        target_score = r1_score
        is_support_target = False
        
    if target_score >= 3.0: 
        score += 15
        details.append("Уровень: +15% (Strong)")
    elif target_score < 1.0: 
        score -= 20
        details.append("Уровень: -20% (Weak)")
    else:
        details.append("Уровень: ±0% (Medium)")
    
    if (is_support_target and rsi < 35) or (not is_support_target and rsi > 65):
        score += 5
        details.append("RSI: +5% (Бонус за экстремум)")
    else:
        details.append("RSI: ±0% (Нет бонуса)")
    
    final_score = max(0, min(100, int(score)))
    return final_score, "\n       • ".join(details), is_support_target

def get_swing_strategy(daily_price, daily_s1, daily_r1, daily_rsi, daily_atr):
    """ SWING STRATEGY (DAILY) """
    if daily_rsi > 70:
        return "WAIT", "RSI Daily перегрет (>70)", "N/A", "N/A", "N/A"
    if daily_rsi < 30:
        return "WAIT", "RSI Daily перепродан (<30)", "N/A", "N/A", "N/A"

    dist_s = abs(daily_price - daily_s1)
    dist_r = abs(daily_price - daily_r1)
    
    if dist_s < dist_r: # Closer to Support
        if daily_rsi < 55:
            return "LONG", "Отскок от Daily Support", f"${daily_s1:.4f}", f"${(daily_s1 - daily_atr):.4f}", f"${daily_r1:.4f}"
    else: # Closer to Resistance
        if daily_rsi > 45:
            return "SHORT", "Отбой от Daily Resistance", f"${daily_r1:.4f}", f"${(daily_r1 + daily_atr):.4f}", f"${daily_s1:.4f}"
            
    return "WAIT", "Цена в середине Daily диапазона", "N/A", "N/A", "N/A"

def get_sniper_strategy(p_score, current_price, m30_s1, m30_r1, m30_atr, is_sup_target):
    """ SNIPER STRATEGY (M30) - Returns structured data even if WAIT """
    
    # Base strategy calculation regardless of P-Score
    stop_buffer = m30_atr * 1.5
    
    if is_sup_target: # Potential LONG
        action = "LONG"
        entry = m30_s1
        stop = m30_s1 - stop_buffer
        tp = m30_r1
    else: # Potential SHORT
        action = "SHORT"
        entry = m30_r1
        stop = m30_r1 + stop_buffer
        tp = m30_s1
        
    # Decision Logic
    if p_score < 40:
        return "WAIT", f"P-Score {p_score}% слишком низкий", "N/A", "N/A", "N/A"
        
    return action, f"P-Score {p_score}% > 40%, вход от уровня", f"${entry:.4f}", f"${stop:.4f}", f"${tp:.4f}"

async def get_technical_indicators(ticker):
    exchange = ccxt.binance({'enableRateLimit': True, 'options': {'defaultType': 'future'}})
    try:
        m30_task = fetch_ohlcv_data(exchange, f"{ticker.upper()}/USDT", SETTINGS['timeframe'], limit=1500)
        daily_task = fetch_ohlcv_data(exchange, f"{ticker.upper()}/USDT", SETTINGS['swing_timeframe'], limit=365)
        btc_task = fetch_ohlcv_data(exchange, "BTC/USDT", SETTINGS['timeframe'], limit=1500)
        funding_task = fetch_funding_rate(exchange, f"{ticker.upper()}/USDT")
        oi_task = fetch_open_interest(exchange, f"{ticker.upper()}/USDT")

        df, daily_df, btc_df, funding_rate, open_interest = await asyncio.gather(
            m30_task, daily_task, btc_task, funding_task, oi_task
        )
        
        if df is None or df.empty or daily_df is None: return None

        df['atr'] = calculate_atr(df)
        df['rsi'] = calculate_rsi(df)
        daily_df['atr'] = calculate_atr(daily_df)
        daily_df['rsi'] = calculate_rsi(daily_df)
        regime, safety = calculate_global_regime(btc_df)
        
        # Levels with DISTANCE FILTER (20% for Daily to avoid noise)
        m30_sup, m30_res = process_levels(df, max_dist_pct=30.0)
        daily_sup, daily_res = process_levels(daily_df, timeframe_scaler=2.0, max_dist_pct=20.0)
        
        current_price = df['close'].iloc[-1]
        daily_price = daily_df['close'].iloc[-1]
        daily_atr = daily_df['atr'].iloc[-1]
        m30_atr = df['atr'].iloc[-1]
        m30_rsi = df['rsi'].iloc[-1]
        daily_rsi = daily_df['rsi'].iloc[-1]
        liq_long, liq_short = estimate_liquidation_levels(current_price, m30_atr)
        
        price_24h = df['close'].iloc[-49] if len(df) >= 49 else df['open'].iloc[0]
        change_str = f"{((current_price - price_24h) / price_24h) * 100:+.2f}"
        
        def fmt_lvls(lvls): return " | ".join([f"${l['price']:.4f} (Sc:{l['score']:.1f})" for l in lvls]) if lvls else "НЕТ (слишком далеко)"
        
        m30_s1 = m30_sup[0]['price'] if m30_sup else df['low'].min()
        m30_r1 = m30_res[0]['price'] if m30_res else df['high'].max()
        m30_s1_score = m30_sup[0]['score'] if m30_sup else 0.0
        m30_r1_score = m30_res[0]['score'] if m30_res else 0.0
        
        daily_s1 = daily_sup[0]['price'] if daily_sup else daily_df['low'].min()
        daily_r1 = daily_res[0]['price'] if daily_res else daily_df['high'].max()

        p_score, p_score_details, is_sup_target = calculate_p_score(
            regime, m30_rsi, m30_s1_score, m30_r1_score, current_price, m30_s1, m30_r1
        )
        
        # Strategies
        swing_action, swing_reason, swing_entry, swing_stop, swing_tp = get_swing_strategy(
            daily_price, daily_s1, daily_r1, daily_rsi, daily_atr
        )
        
        sniper_action, sniper_reason, sniper_entry, sniper_stop, sniper_tp = get_sniper_strategy(
            p_score, current_price, m30_s1, m30_r1, m30_atr, is_sup_target
        )

        return {
            "price": current_price,
            "change": change_str,
            "m30_rsi": round(m30_rsi, 1),
            "daily_rsi": round(daily_rsi, 1),
            "regime": regime,
            "funding": f"{funding_rate:.4f}%",
            "open_interest": f"${open_interest:,.0f}" if open_interest else "N/A",
            "daily_sup": fmt_lvls(daily_sup),
            "daily_res": fmt_lvls(daily_res),
            "m30_sup": fmt_lvls(m30_sup),
            "m30_res": fmt_lvls(m30_res),
            "liq_long": f"${liq_long:.4f}",
            "liq_short": f"${liq_short:.4f}",
            "p_score": p_score,
            "p_score_details": p_score_details,
            "swing_strat": {
                "action": swing_action, "reason": swing_reason, "entry": swing_entry, "stop": swing_stop, "tp": swing_tp
            },
            "sniper_strat": {
                "action": sniper_action, "reason": sniper_reason, "entry": sniper_entry, "stop": sniper_stop, "tp": sniper_tp
            }
        }
    finally:
        await exchange.close()
