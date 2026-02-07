import ccxt.async_support as ccxt
import pandas as pd
import numpy as np
import logging
import asyncio

logger = logging.getLogger(__name__)

# --- SETTINGS (MATCHING PINE SCRIPT v3.7 EXACTLY) ---
SETTINGS = {
    'timeframe': '30m', 
    'reactBars': 24,    
    'kReact': 1.3,
    'mergeATR': 0.6,
    'Wt': 1.0,          # Weight per touch
    'Wa': 0.35,         # Age Penalty (Fixed per Audit)
    'Tmin': 5,          # Min Age (bars)
    'scMin': 0.0,       # Min Score Threshold
    'maxDistPct': 30.0, # Max distance from price (%)
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
        # Weighted average for Price AND ATR
        old_touches = self.touches
        new_touches = old_touches + 1
        
        self.price = (self.price * old_touches + price) / new_touches
        self.atr = (self.atr * old_touches + atr) / new_touches 
        
        self.touches = new_touches
        self.last_touch_idx = idx

    def get_score(self, current_idx):
        # Formula: (Touches * Wt) - (AgeFromLastTouch * Wa)
        age = current_idx - self.last_touch_idx
        return (self.touches * SETTINGS['Wt']) - (age * SETTINGS['Wa'])

async def fetch_ohlcv_data(exchange, symbol, limit=300):
    try:
        ohlcv = await exchange.fetch_ohlcv(symbol, SETTINGS['timeframe'], limit=limit)
        if not ohlcv: return None
        df = pd.DataFrame(ohlcv, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
        return df
    except Exception as e:
        logger.error(f"Error fetching {symbol}: {e}")
        return None

def calculate_atr(df, period=14):
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()

def calculate_global_regime(btc_df):
    """
    Pine Logic Proxy:
    Uses BTC Momentum Z-Score as a proxy for Market Regime.
    High Z-Score (> 1.25) = COMPRESSION (Squeeze risk).
    Low Z-Score (< -1.25) = EXPANSION (Trend).
    """
    if btc_df is None or len(btc_df) < SETTINGS['zWin']:
        return "NEUTRAL", "SAFE"
    
    # 1. ROC (Rate of Change / Momentum) Length 30
    roc = btc_df['close'].pct_change(30)
    
    # 2. Z-Score Calculation (Window 180)
    mean = roc.rolling(window=SETTINGS['zWin']).mean()
    std = roc.rolling(window=SETTINGS['zWin']).std()
    
    if std.iloc[-1] == 0 or pd.isna(std.iloc[-1]): return "NEUTRAL", "SAFE"
    
    z_score = (roc - mean) / std
    current_z = z_score.iloc[-1]
    
    if pd.isna(current_z): return "NEUTRAL", "SAFE"
    
    # Pine Logic: High Z-Score = Compression
    if current_z > SETTINGS['zThr']:
        regime = "COMPRESSION"
    elif current_z < -SETTINGS['zThr']:
        regime = "EXPANSION"
    else:
        regime = "NEUTRAL"
        
    safety = "RISKY" if regime == "COMPRESSION" else "SAFE"
    return regime, safety

def process_levels(df):
    levels = []
    pending = []
    
    atr = df['atr'].values
    high = df['high'].values
    low = df['low'].values
    close = df['close'].values
    
    L, R = 4, 4 
    start_idx = max(SETTINGS['atrLen'], L + R)
    
    for i in range(start_idx, len(df) - R):
        # 1. Pivot Detection
        is_pivot_h = True
        is_pivot_l = True
        
        for j in range(1, L + 1):
            if high[i] < high[i-j] or high[i] < high[i+j]: is_pivot_h = False
            if low[i] > low[i-j] or low[i] > low[i+j]: is_pivot_l = False
            
        if is_pivot_h:
            pending.append({'idx': i, 'price': high[i], 'is_res': True, 'atr': atr[i], 'check_at': i + SETTINGS['reactBars']})
        if is_pivot_l:
            pending.append({'idx': i, 'price': low[i], 'is_res': False, 'atr': atr[i], 'check_at': i + SETTINGS['reactBars']})
            
        # 2. Reaction Check
        active_pending = []
        for p in pending:
            if i >= p['check_at']:
                reaction_dist = SETTINGS['kReact'] * p['atr']
                confirmed = False
                
                window_low = np.min(low[p['idx'] : i+1])
                window_high = np.max(high[p['idx'] : i+1])
                
                if p['is_res']:
                    if (p['price'] - window_low) >= reaction_dist: confirmed = True
                else:
                    if (window_high - p['price']) >= reaction_dist: confirmed = True
                
                if confirmed:
                    # 3. Merge Logic
                    merged = False
                    merge_tol = SETTINGS['mergeATR'] * p['atr']
                    for lvl in levels:
                        if lvl.is_res == p['is_res'] and abs(lvl.price - p['price']) < merge_tol:
                            lvl.update(p['price'], p['atr'], i)
                            merged = True
                            break
                    if not merged:
                        levels.append(Level(p['price'], p['is_res'], p['atr'], i))
            else:
                active_pending.append(p)
        pending = active_pending

    # 4. Filtering & Scoring
    current_idx = len(df) - 1
    active_supports = []
    active_resistances = []
    current_price = close[-1]
    
    for lvl in levels:
        # Tmin Filter
        age_total = current_idx - lvl.created_at
        if age_total < SETTINGS['Tmin']: continue

        score = lvl.get_score(current_idx)
        
        # scMin Filter
        if score < SETTINGS['scMin']: continue
            
        # maxDistPct Filter
        dist_pct = abs(lvl.price - current_price) / current_price * 100
        if dist_pct > SETTINGS['maxDistPct']: continue
            
        data = {'price': lvl.price, 'score': score}
        if lvl.is_res and lvl.price > current_price:
            active_resistances.append(data)
        elif not lvl.is_res and lvl.price < current_price:
            active_supports.append(data)
                
    active_supports.sort(key=lambda x: x['score'], reverse=True)
    active_resistances.sort(key=lambda x: x['score'], reverse=True)
    
    return active_supports[:3], active_resistances[:3]

async def get_technical_indicators(ticker):
    exchange = ccxt.binance({'enableRateLimit': True, 'options': {'defaultType': 'future'}})
    try:
        target_task = fetch_ohlcv_data(exchange, f"{ticker.upper()}/USDT", limit=500)
        btc_task = fetch_ohlcv_data(exchange, "BTC/USDT", limit=500)
        
        df, btc_df = await asyncio.gather(target_task, btc_task)
        if df is None or df.empty: return None

        df['atr'] = calculate_atr(df)
        
        regime, safety = calculate_global_regime(btc_df)
        supports, resistances = process_levels(df)
        
        current_price = df['close'].iloc[-1]
        
        # --- LOGIC FOR AI ---
        s1 = supports[0]['price'] if supports else df['low'].min()
        r1 = resistances[0]['price'] if resistances else df['high'].max()
        
        s1_score = supports[0]['score'] if supports else 0.0
        r1_score = resistances[0]['score'] if resistances else 0.0

        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs)).iloc[-1]
        
        sma_50 = df['close'].rolling(window=50).mean().iloc[-1]
        trend = "BULLISH" if current_price > sma_50 else "BEARISH"

        return {
            "price": current_price,
            "rsi": round(rsi, 1),
            "trend": trend,
            "regime": regime,
            "safety": safety,
            "s1": round(s1, 4),
            "r1": round(r1, 4),
            "s1_score": round(s1_score, 1),
            "r1_score": round(r1_score, 1)
        }
    finally:
        await exchange.close()
