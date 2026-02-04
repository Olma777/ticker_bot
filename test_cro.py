
import aiohttp
import asyncio

async def test_cro():
    ticker = "CRO"
    ticker_upper = ticker.upper()
    headers = {"User-Agent": "Mozilla/5.0"}
    
    async with aiohttp.ClientSession(headers=headers) as session:
        print("--- Testing Binance ---")
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={ticker_upper}USDT"
        try:
            async with session.get(url, timeout=3) as response:
                print(f"Binance Status: {response.status}")
                if response.status == 200:
                    data = await response.json()
                    print(f"Binance Data: {data}")
                else:
                    print(f"Binance Error: {await response.text()}")
        except Exception as e:
            print(f"Binance Exception: {e}")

        print("\n--- Testing CoinCap ---")
        url = f"https://api.coincap.io/v2/assets?search={ticker_upper}"
        try:
            async with session.get(url, timeout=5) as response:
                print(f"CoinCap Status: {response.status}")
                if response.status == 200:
                    data = await response.json()
                    found = False
                    for coin in data['data']:
                        print(f"CoinCap found: {coin['symbol']} ({coin['name']}) - ID: {coin['id']}")
                        if coin['symbol'] == ticker_upper:
                            found = True
                            print("MATCH FOUND!")
                    if not found:
                        print("No exact match found in CoinCap")
        except Exception as e:
            print(f"CoinCap Exception: {e}")

asyncio.run(test_cro())
