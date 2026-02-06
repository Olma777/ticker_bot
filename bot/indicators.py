import ccxt.async_support as ccxt
import asyncio

async def fetch_candles(ticker):
    """
    Скачивает 50 свечей 1h через CCXT (Binance Futures или fallback на Bybit).
    Возвращает список свечей: [[timestamp, open, high, low, close, volume], ...]
    """
    ticker_upper = ticker.upper().replace("USDT", "").replace("USD", "")
    symbol = f"{ticker_upper}/USDT"
    
    exchanges = [
        ccxt.binance({'options': {'defaultType': 'future'}}),
        ccxt.bybit({'options': {'defaultType': 'linear'}})
    ]
    
    for exchange in exchanges:
        try:
            # fetch_ohlcv(symbol, timeframe, since, limit)
            candles = await exchange.fetch_ohlcv(symbol, timeframe='1h', limit=50)
            if candles and len(candles) >= 50:
                return candles  # finally block will handle close
        except Exception as e:
            print(f"Error fetching candles from {exchange.id}: {e}")
            continue
        finally:
            await exchange.close()
            
    return []

def calculate_rsi(prices, period=14):
    """
    Считает RSI (14) на чистом Python.
    prices: список цен закрытия (от старых к новым).
    """
    if len(prices) < period + 1:
        return 50.0 # Недостаточно данных
    
    deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    gains = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]
    
    # Первая средняя (SMA)
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    
    if avg_loss == 0:
        return 100.0
    
    # Wilder's Smoothing
    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        
    if avg_loss == 0:
        return 100.0
        
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return round(rsi, 2)

async def get_technical_indicators(ticker):
    """
    Возвращает словарь с индикаторами: RSI, Trend, Support, Resistance.
    """
    candles = await fetch_candles(ticker)
    
    if not candles:
        return None
        
    # Распаковка данных (OHLCV)
    # [timestamp, open, high, low, close, volume]
    highs = [c[2] for c in candles]
    lows = [c[3] for c in candles]
    closes = [c[4] for c in candles]
    
    # 1. RSI (14)
    rsi = calculate_rsi(closes)
    
    # 2. Support & Resistance (Low/High за 50 часов)
    support = min(lows)
    resistance = max(highs)
    
    # 3. Trend (SMA 20)
    # Берем последние 20 цен
    if len(closes) >= 20:
        sma20 = sum(closes[-20:]) / 20
        current_price = closes[-1]
        trend = "BULLISH" if current_price > sma20 else "BEARISH"
    else:
        trend = "NEUTRAL"
        
    return {
        "rsi": rsi,
        "trend": trend,
        "support": support,
        "resistance": resistance,
        "current_price": closes[-1]
    }
