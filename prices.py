import aiohttp

# Словарь имен для красивого вывода
COIN_NAMES = {
    "BTC": "Bitcoin", "ETH": "Ethereum", "USDT": "Tether", "BNB": "BNB",
    "SOL": "Solana", "XRP": "XRP", "USDC": "USDC", "ADA": "Cardano",
    "AVAX": "Avalanche", "DOGE": "Dogecoin", "TON": "Toncoin", 
    "PEPE": "Pepe", "SHIB": "Shiba Inu"
}

async def get_crypto_price(ticker):
    """
    Ищет цену в 3 источниках: CoinCap -> Binance -> DexScreener.
    """
    ticker_upper = ticker.upper().replace("USDT", "").replace("USD", "")
    headers = {"User-Agent": "Mozilla/5.0"}

    async with aiohttp.ClientSession(headers=headers) as session:
        # 1. COINCAP
        try:
            url = f"https://api.coincap.io/v2/assets?search={ticker_upper}"
            async with session.get(url, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    for coin in data['data']:
                        if coin['symbol'] == ticker_upper:
                            price = float(coin['priceUsd'])
                            fmt_price = f"{price:.6f}" if price < 1 else f"{price:.2f}"
                            return {
                                "price": fmt_price,
                                "name": coin['name'],
                                "rank": coin['rank'],
                                "ticker": coin['symbol']
                            }, None
        except Exception: pass 

        # 2. BINANCE
        try:
            url = f"https://api.binance.com/api/v3/ticker/price?symbol={ticker_upper}USDT"
            async with session.get(url, timeout=3) as response:
                if response.status == 200:
                    data = await response.json()
                    price = float(data["price"])
                    fmt_price = f"{price:g}"
                    full_name = COIN_NAMES.get(ticker_upper, ticker_upper)
                    return {
                        "price": fmt_price,
                        "name": full_name,
                        "rank": "?",
                        "ticker": ticker_upper
                    }, None
        except Exception: pass

        # 3. DEXSCREENER
        try:
            url = f"https://api.dexscreener.com/latest/dex/search?q={ticker_upper}"
            async with session.get(url, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    pairs = data.get('pairs', [])
                    if pairs:
                        best_pair = pairs[0]
                        price = float(best_pair['priceUsd'])
                        if price < 0.01: fmt_price = f"{price:.8f}"
                        elif price < 1: fmt_price = f"{price:.4f}"
                        else: fmt_price = f"{price:.2f}"
                        chain = best_pair.get('chainId', 'DEX').capitalize()
                        full_name = best_pair['baseToken']['name']
                        return {
                            "price": fmt_price,
                            "name": f"{full_name} ({chain})",
                            "rank": "DEX",
                            "ticker": ticker_upper
                        }, None
        except Exception: pass

    return None, True

# --- ФУНКЦИЯ ДЛЯ DAILY BRIEFING ---
async def get_market_summary():
    """
    Собирает данные для утреннего брифинга:
    1. Доминация BTC
    2. Цена BTC
    3. Топ монет (для поиска нарратива)
    """
    headers = {"User-Agent": "Mozilla/5.0"}
    summary = {}

    async with aiohttp.ClientSession(headers=headers) as session:
        # 1. Доминация BTC (CoinCap Global)
        try:
            async with session.get("https://api.coincap.io/v2/global", timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    summary['btc_dominance'] = f"{float(data['data']['bitcoinDominancePercentage']):.2f}"
                else:
                    summary['btc_dominance'] = "N/A"
        except:
            summary['btc_dominance'] = "Unknown"

        # 2. Цена BTC
        btc_data, _ = await get_crypto_price("BTC")
        summary['btc_price'] = btc_data['price'] if btc_data else "Unknown"

        # 3. Топ монет (ищем нарративы)
        try:
            async with session.get("https://api.coincap.io/v2/assets?limit=15", timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    coins_list = []
                    for coin in data['data']:
                        sym = coin['symbol']
                        change = float(coin['changePercent24Hr'])
                        if sym not in ["USDT", "USDC", "FDUSD"]:
                            coins_list.append(f"{sym} ({change:+.2f}%)")
                    summary['top_coins'] = ", ".join(coins_list[:10])
                else:
                    summary['top_coins'] = "Bitcoin, Ethereum, Solana"
        except:
            summary['top_coins'] = "Top alts unavailable"

    return summary