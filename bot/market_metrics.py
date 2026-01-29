import asyncio
import aiohttp
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Constants based on Pine Script
ROC_LEN = 30
Z_WIN = 180
Z_THR = 1.25

# CoinGecko IDs
# Stables
STABLES = ['tether', 'usd-coin']
# Total3 Proxy (Top Alts excluding BTC/ETH)
TOP_ALTS = [
    'binancecoin', 'solana', 'ripple', 'cardano', 'avalanche-2',
    'dogecoin', 'tron', 'polkadot', 'chainlink', 'shiba-inu'
]

async def fetch_coingecko_history(session, coin_id, days=365):
    """
    Fetches daily market cap history for a coin from CoinGecko.
    """
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    params = {
        'vs_currency': 'usd',
        'days': days,
        'interval': 'daily'
    }
    try:
        async with session.get(url, params=params) as response:
            if response.status == 429:
                print(f"Rate limit hit for {coin_id}, waiting 60s...")
                await asyncio.sleep(60) # Wait longer for rate limit reset
                return await fetch_coingecko_history(session, coin_id, days)
            
            if response.status != 200:
                print(f"Error fetching {coin_id}: Status {response.status}")
                return None

            data = await response.json()
            if 'market_caps' not in data:
                print(f"Error fetching {coin_id}: {data}")
                return None
            
            # Convert to DataFrame
            df = pd.DataFrame(data['market_caps'], columns=['timestamp', 'market_cap'])
            df['date'] = pd.to_datetime(df['timestamp'], unit='ms').dt.normalize()
            df.set_index('date', inplace=True)
            # Handle duplicates if any
            df = df[~df.index.duplicated(keep='last')]
            return df['market_cap']
    except Exception as e:
        print(f"Exception fetching {coin_id}: {e}")
        return None

async def get_market_regime():
    async with aiohttp.ClientSession() as session:
        print("Fetching data from CoinGecko (sequentially to avoid rate limits)...")
        
        # 1. Fetch Stables
        usdt_series = None
        usdc_series = None
        
        # Fetch USDT
        usdt_series = await fetch_coingecko_history(session, 'tether')
        await asyncio.sleep(2) # Delay
        
        # Fetch USDC
        usdc_series = await fetch_coingecko_history(session, 'usd-coin')
        await asyncio.sleep(2) # Delay
        
        if usdt_series is None or usdc_series is None:
            print("Failed to fetch stablecoin data.")
            return None
            
        # 2. Fetch Alts
        alt_series_list = []
        for coin in TOP_ALTS:
            print(f"Fetching {coin}...")
            s = await fetch_coingecko_history(session, coin)
            alt_series_list.append(s)
            await asyncio.sleep(2) # Delay between calls
            
        # 3. Process Data
        print("Processing data...")
        
        # Create a common dataframe based on USDT index
        df = pd.DataFrame(index=usdt_series.index).join(usdt_series.rename('USDT'))
        df = df.join(usdc_series.rename('USDC'))
        
        # Calculate Liquidity (USDT + USDC)
        df['LIQ'] = df['USDT'] + df['USDC']
        
        # Calculate Total3 Proxy
        df['TOTAL3'] = 0.0
        valid_alts = 0
        for i, s in enumerate(alt_series_list):
            if s is not None:
                # Reindex to match df
                s_reindexed = s.reindex(df.index, method='ffill')
                df[f'ALT_{i}'] = s_reindexed
                df['TOTAL3'] += df[f'ALT_{i}'].fillna(0)
                valid_alts += 1
        
        if valid_alts < 5:
            print(f"Warning: Only {valid_alts} altcoins fetched for Total3 proxy.")
            
        # Drop rows with NaN in critical columns
        df.dropna(subset=['LIQ', 'TOTAL3'], inplace=True)
        
        # 4. Apply Formulas (Pine Script Logic)
        # spread = roc(total3, rocLen) - roc(liq, rocLen)
        # meanS = sma(spread, zWin)
        # stdS = stdev(spread, zWin)
        # zVal = (spread - meanS) / stdS
        
        # ROC = (current - prev) / prev * 100
        df['ROC_TOTAL3'] = df['TOTAL3'].pct_change(ROC_LEN) * 100
        df['ROC_LIQ'] = df['LIQ'].pct_change(ROC_LEN) * 100
        
        df['SPREAD'] = df['ROC_TOTAL3'] - df['ROC_LIQ']
        
        df['MEAN_S'] = df['SPREAD'].rolling(window=Z_WIN).mean()
        df['STD_S'] = df['SPREAD'].rolling(window=Z_WIN).std()
        
        # Avoid division by zero
        df['Z_SCORE'] = (df['SPREAD'] - df['MEAN_S']) / df['STD_S']
        
        # Get latest valid value
        latest = df.iloc[-1]
        z_val = latest['Z_SCORE']
        
        # Determine Regime
        regime = "NEUTRAL"
        if pd.isna(z_val):
            regime = "INSUFFICIENT_DATA"
        elif z_val > Z_THR:
            regime = "COMPRESSION"
        elif z_val < -Z_THR:
            regime = "EXPANSION"
            
        return {
            "status": regime,
            "z_score": z_val if not pd.isna(z_val) else 0.0,
            "date": latest.name.strftime('%Y-%m-%d')
        }

if __name__ == "__main__":
    try:
        result = asyncio.run(get_market_regime())
        print("\n--- Market Regime Result ---")
        print(result)
    except Exception as e:
        print(f"Error: {e}")
