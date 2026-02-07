import ccxt.async_support as ccxt
import pandas as pd
import numpy as np
import logging
import asyncio

logger = logging.getLogger(__name__)

# --- SETTINGS (PRODUCTION) ---
SETTINGS = {
    'timeframe': '30m', 
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

async def fetch_ohlcv_data(exchange, symbol, limit=1500):
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
                reaction_dist = SETTINGS['kReact'] * p['atr']
                confirmed = False
                window_low = np.min(low[p['idx'] : i+1])
                window_high = np.max(high[p['idx'] : i+1])
                
                if p['is_res']:
                    if (p['price'] - window_low) >= reaction_dist: confirmed = True
                else:
                    if (window_high - p['price']) >= reaction_dist: confirmed = True
                
                if confirmed:
                    merged = False
                    merge_tol = SETTINGS['mergeATR'] * p['atr']
                    for lvl in levels:
                        if lvl.is_res == p['is_res'] and abs(lvl.price - p['price']) < merge_tol:
                            lvl.update(p['price'], p['atr'], i)
                            merged = True
                            break
                    if not merged: levels.append(Level(p['price'], p['is_res'], p['atr'], i))
            else: active_pending.append(p)
        pending = active_pending

    current_idx = len(df) - 1
    active_supports = []
    active_resistances = []
    current_price = close[-1]
    
    for lvl in levels:
        age_total = current_idx - lvl.created_at
        if age_total < SETTINGS['Tmin']: continue
        score = lvl.get_score(current_idx)
        if score < SETTINGS['scMin']: continue
        
        dist_pct = abs(lvl.price - current_price) / current_price * 100
        if dist_pct > SETTINGS['maxDistPct']: continue
            
        data = {'price': lvl.price, 'score': score}
        if lvl.is_res and lvl.price > current_price: active_resistances.append(data)
        elif not lvl.is_res and lvl.price < current_price: active_supports.append(data)
    
    # SORT BY DISTANCE (Closest First)
    active_supports.sort(key=lambda x: abs(x['price'] - current_price))
    active_resistances.sort(key=lambda x: abs(x['price'] - current_price))
    
    return active_supports[:5], active_resistances[:5]

def calculate_p_score(regime, rsi, s1_score, r1_score, current_price, s1_price, r1_price):
    """
    Рассчитывает P-Score (0-100%) и возвращает форматированный текст.
    """
    score = 50 
    details = ["База: 50%"]
    
    # 1. Regime
    if regime == "EXPANSION": 
        score += 10
        details.append("Режим: +10% (EXPANSION)")
    elif regime in ["COMPRESSION", "NEUTRAL"]: 
        score -= 10
        details.append(f"Режим: -10% ({regime})")
    
    # 2. Level Strength & Proximity
    dist_s1 = abs(current_price - s1_price)
    dist_r1 = abs(current_price - r1_price)
    
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
    
    # 3. RSI Modifier (Optimized)
    if (is_support_target and rsi < 35) or (not is_support_target and rsi > 65):
        score += 5
        details.append("RSI: +5% (Бонус за экстремум)")
    else:
        details.append("RSI: ±0% (Нет бонуса)")
    
    final_score = max(0, min(100, int(score)))
    
    # Format for Telegram
    return final_score, "\n       • ".join(details)

async def get_technical_indicators(ticker):
    exchange = ccxt.binance({'enableRateLimit': True, 'options': {'defaultType': 'future'}})
    try:
        target_task = fetch_ohlcv_data(exchange, f"{ticker.upper()}/USDT", limit=1500)
        btc_task = fetch_ohlcv_data(exchange, "BTC/USDT", limit=1500)
        df, btc_df = await asyncio.gather(target_task, btc_task)
        if df is None or df.empty: return None

        df['atr'] = calculate_atr(df)
        regime, safety = calculate_global_regime(btc_df)
        supports, resistances = process_levels(df)
        
        current_price = df['close'].iloc[-1]
        
        sup_str = " | ".join([f"${s['price']:.4f} (Score: {s['score']:.1f})" for s in supports]) if supports else "НЕТ УРОВНЕЙ"
        res_str = " | ".join([f"${r['price']:.4f} (Score: {r['score']:.1f})" for r in resistances]) if resistances else "НЕТ УРОВНЕЙ"
        
        # Fallbacks if list is empty (unlikely with scMin=-100)
        s1 = supports[0]['price'] if supports else df['low'].min()
        r1 = resistances[0]['price'] if resistances else df['high'].max()
        s1_score = supports[0]['score'] if supports else 0.0
        r1_score = resistances[0]['score'] if resistances else 0.0

        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs)).iloc[-1]
        
        sma_50 = df['close'].rolling(window=50).mean().iloc[-1]
        trend = "BULLISH" if current_price > sma_50 else "BEARISH"

        # --- P-SCORE CALCULATION ---
        p_score, p_score_details = calculate_p_score(
            regime, rsi, s1_score, r1_score, current_price, s1, r1
        )

        return {
            "price": current_price,
            "rsi": round(rsi, 1),
            "trend": trend,
            "regime": regime,
            "safety": safety,
            "s1": round(s1, 4),
            "r1": round(r1, 4),
            "s1_score": round(s1_score, 1),
            "r1_score": round(r1_score, 1),
            "p_score": p_score,
            "p_score_details": p_score_details, 
            "supports_list": sup_str, 
            "resistances_list": res_str
        }
    finally:
        await exchange.close()
