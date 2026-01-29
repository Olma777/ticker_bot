import aiohttp
import asyncio

# Словарь имен
COIN_NAMES = {
    "BTC": "Bitcoin", "ETH": "Ethereum", "USDT": "Tether", "BNB": "BNB",
    "SOL": "Solana", "XRP": "XRP", "USDC": "USDC", "ADA": "Cardano",
    "AVAX": "Avalanche", "DOGE": "Dogecoin", "TON": "Toncoin", 
    "PEPE": "Pepe", "SHIB": "Shiba Inu", "SUI": "Sui", "ARB": "Arbitrum",
    "APT": "Aptos", "LDO": "Lido DAO", "OP": "Optimism", "TIA": "Celestia"
}

async def get_crypto_price(ticker):
    ticker_upper = ticker.upper().replace("USDT", "").replace("USD", "")
    headers = {"User-Agent": "Mozilla/5.0"}

    async with aiohttp.ClientSession(headers=headers) as session:
        # 1. BINANCE
        try:
            url = f"https://api.binance.com/api/v3/ticker/price?symbol={ticker_upper}USDT"
            async with session.get(url, timeout=3) as response:
                if response.status == 200:
                    data = await response.json()
                    price = float(data["price"])
                    if price < 0.01: fmt = f"{price:.8f}"
                    elif price < 1: fmt = f"{price:.4f}"
                    else: fmt = f"{price:.2f}"
                    
                    full_name = COIN_NAMES.get(ticker_upper, ticker_upper)
                    return {"price": fmt, "name": full_name, "ticker": ticker_upper}, None
        except Exception: pass

        # 2. COINCAP
        try:
            url = f"https://api.coincap.io/v2/assets?search={ticker_upper}"
            async with session.get(url, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    for coin in data['data']:
                        if coin['symbol'] == ticker_upper:
                            price = float(coin['priceUsd'])
                            fmt = f"{price:.6f}" if price < 1 else f"{price:.2f}"
                            return {"price": fmt, "name": coin['name'], "ticker": coin['symbol']}, None
        except Exception: pass

    return None, True

async def get_market_summary():
    headers = {"User-Agent": "Mozilla/5.0"}
    summary = {}

    async with aiohttp.ClientSession(headers=headers) as session:
        # ДОМИНАЦИЯ
        dominance = "56.5" # Fallback
        try:
            async with session.get("https://api.coingecko.com/api/v3/global", timeout=3) as response:
                if response.status == 200:
                    data = await response.json()
                    dom = float(data['data']['market_cap_percentage']['btc'])
                    dominance = f"{dom:.2f}"
        except: pass
        summary['btc_dominance'] = dominance

        # ТОП МОНЕТЫ (Binance)
        top_coins_list = []
        try:
            url = "https://api.binance.com/api/v3/ticker/24hr"
            async with session.get(url, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    valid_coins = []
                    for t in data:
                        sym = t['symbol']
                        if sym.endswith("USDT"):
                            vol = float(t['quoteVolume'])
                            if vol > 15_000_000: # Фильтр объема
                                pure_sym = sym.replace("USDT", "")
                                if pure_sym not in ["USDC", "FDUSD", "USDT", "TUSD", "DAI", "WBTC"]:
                                    change = float(t['priceChangePercent'])
                                    price = float(t['lastPrice'])
                                    valid_coins.append({"symbol": pure_sym, "change": change, "price": price})
                    
                    # Топ-3 лидера
                    valid_coins.sort(key=lambda x: x['change'], reverse=True)
                    top3 = valid_coins[:3]
                    
                    # Формируем список для ИИ: "1. TIA: $12.50"
                    for i, c in enumerate(top3, 1):
                        p = c['price']
                        p_str = f"{p:.6f}" if p < 0.01 else (f"{p:.4f}" if p < 1 else f"{p:.2f}")
                        top_coins_list.append(f"{i}. {c['symbol']}: ${p_str}")
        except: pass

        if not top_coins_list:
            top_coins_list = ["1. BTC: $96000", "2. ETH: $2800", "3. SOL: $140"]

        summary['top_coins'] = "\n".join(top_coins_list)

    return summary