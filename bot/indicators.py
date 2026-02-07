import ccxt.async_support as ccxt
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)

async def fetch_candles(ticker, timeframe='1h', limit=200):
    """Скачивает свечи (OHLCV)"""
    exchange = ccxt.binance({'enableRateLimit': True, 'options': {'defaultType': 'future'}})
    try:
        symbol = f"{ticker.upper()}/USDT"
        ohlcv = await exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
        return df
    except Exception as e:
        logger.error(f"Error fetching candles for {ticker}: {e}")
        return None
    finally:
        await exchange.close()

def calculate_atr(df, period=14):
    df['tr'] = np.maximum(df['high'] - df['low'], 
                          np.maximum(abs(df['high'] - df['close'].shift(1)), 
                                     abs(df['low'] - df['close'].shift(1))))
    return df['tr'].rolling(window=period).mean()

def find_pivots(df, left=4, right=4):
    """Поиск локальных High/Low (аналог ta.pivothigh/low)"""
    df['isPivotHigh'] = df['high'].rolling(window=left+right+1, center=True).max() == df['high']
    df['isPivotLow'] = df['low'].rolling(window=left+right+1, center=True).min() == df['low']
    return df

def calculate_market_regime(df):
    """Эмуляция логики Regime (Expansion/Compression) на основе полос Боллинджера и ATR"""
    # Если волатильность падает (Squeeze) -> COMPRESSION
    # Если волатильность растет -> EXPANSION
    
    df['std'] = df['close'].rolling(window=20).std()
    df['upper'] = df['close'].rolling(window=20).mean() + (df['std'] * 2)
    df['lower'] = df['close'].rolling(window=20).mean() - (df['std'] * 2)
    df['bandwidth'] = (df['upper'] - df['lower']) / df['close'].rolling(window=20).mean()
    
    # Сравниваем текущую ширину канала с средней за 50 свечей
    avg_bandwidth = df['bandwidth'].rolling(window=50).mean().iloc[-1]
    curr_bandwidth = df['bandwidth'].iloc[-1]
    
    # Safety check for NaN (insufficient data)
    if pd.isna(avg_bandwidth) or pd.isna(curr_bandwidth):
        return "NEUTRAL"
    
    if curr_bandwidth < avg_bandwidth * 0.8:
        return "COMPRESSION"
    elif curr_bandwidth > avg_bandwidth * 1.2:
        return "EXPANSION"
    else:
        return "NEUTRAL"

async def get_technical_indicators(ticker):
    df = await fetch_candles(ticker, limit=100)
    if df is None or df.empty: return None

    # 1. Данные
    current_price = df['close'].iloc[-1]
    df['atr'] = calculate_atr(df)
    
    # 2. Pivot Points & Levels (Trend Level PRO Logic)
    df = find_pivots(df)
    
    supports = []
    resistances = []
    
    # Собираем пивоты за последние 50 свечей
    recent_df = df.iloc[-50:]
    
    for i, row in recent_df.iterrows():
        if row['isPivotHigh']:
            resistances.append(row['high'])
        if row['isPivotLow']:
            supports.append(row['low'])
            
    # Фильтрация и поиск ближайших (Top-3)
    supports.sort() # От меньшего к большему
    resistances.sort()
    
    # Ищем ближайшие к текущей цене
    s1 = max([s for s in supports if s < current_price], default=df['low'].min())
    r1 = min([r for r in resistances if r > current_price], default=df['high'].max())
    
    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs)).iloc[-1]
    
    # Trend (SMA 50)
    sma_50 = df['close'].rolling(window=50).mean().iloc[-1]
    trend = "BULLISH" if current_price > sma_50 else "BEARISH"
    
    # Regime
    regime = calculate_market_regime(df)
    
    # Safety Score
    is_safe = "SAFE" if regime != "COMPRESSION" else "RISKY"

    # Pivot Point (Classic: (H + L + C) / 3 of previous candle)
    prev_high = df['high'].iloc[-2]
    prev_low = df['low'].iloc[-2]
    prev_close = df['close'].iloc[-2]
    pivot = (prev_high + prev_low + prev_close) / 3

    return {
        "price": current_price,
        "rsi": round(rsi, 1),
        "trend": trend,
        "regime": regime,
        "safety": is_safe,
        "pivot": round(pivot, 4),
        "s1": round(s1, 4),
        "r1": round(r1, 4),
        "atr": round(df['atr'].iloc[-1], 4)
    }
