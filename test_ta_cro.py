
import asyncio
import sys
import os

# Add current directory to path
sys.path.append(os.getcwd())

from bot.technical_analysis import TechnicalAnalyzer

async def test_cro_candles():
    print("--- Testing Technical Analysis for CRO ---")
    ta = TechnicalAnalyzer()
    
    # 1. Try Futures (should fail for CRO if not listed)
    print("Fetching candles for CRO/USDT...")
    df = await ta.fetch_candles("CRO", "1h", limit=100)
    
    if not df.empty:
        print(f"SUCCESS: Fetched {len(df)} candles.")
        print(f"Last close: {df['close'].iloc[-1]}")
    else:
        print("FAILURE: Could not fetch candles (empty DataFrame).")
        
    await ta.exchange.close()

if __name__ == "__main__":
    asyncio.run(test_cro_candles())
