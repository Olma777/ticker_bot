
import asyncio
import sys
import os

# Add current directory to path so we can import bot modules
sys.path.append(os.getcwd())

from bot.technical_analysis import TechnicalAnalyzer
from bot.prices import get_crypto_price, get_market_summary

async def test_futures_switch():
    print("--- Testing TechnicalAnalyzer (Futures) ---")
    try:
        ta = TechnicalAnalyzer()
        # Fetch BTC candles
        df = await ta.fetch_candles("BTC", "1h", limit=5)
        print(f"Fetched {len(df)} candles for BTC (Futures)")
        if not df.empty:
            print("Last candle close:", df['close'].iloc[-1])
            # Check if volume looks like futures (often higher than spot, but hard to verify programmatically without comparison. 
            # Mainly checking if it doesn't crash)
        await ta.exchange.close()
    except Exception as e:
        print(f"TechnicalAnalyzer Error: {e}")

    print("\n--- Testing Price Fetching (Futures Priority) ---")
    try:
        # Test BTC (Should hit Binance Futures)
        price_data, err = await get_crypto_price("BTC")
        print(f"BTC Price Data: {price_data}")
        
        # Test CRO (Should hit CCXT Futures or CoinGecko)
        price_data_cro, err_cro = await get_crypto_price("CRO")
        print(f"CRO Price Data: {price_data_cro}")
        
    except Exception as e:
        print(f"Price Fetching Error: {e}")

    print("\n--- Testing Market Summary (Futures) ---")
    try:
        summary = await get_market_summary()
        print(f"Market Summary Top Coins: {summary.get('top_coins', 'N/A')[:100]}...")
    except Exception as e:
        print(f"Market Summary Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_futures_switch())
