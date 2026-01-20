import aiohttp
import asyncio

# Словарь имен для красивого вывода
COIN_NAMES = {
    "BTC": "Bitcoin", "ETH": "Ethereum", "USDT": "Tether", "BNB": "BNB",
    "SOL": "Solana", "XRP": "XRP", "USDC": "USDC", "ADA": "Cardano",
    "AVAX": "Avalanche", "DOGE": "Dogecoin", "TON": "Toncoin", 
    "PEPE": "Pepe", "SHIB": "Shiba Inu", "SUI": "Sui", "ARB": "Arbitrum",
    "APT": "Aptos", "LDO": "Lido DAO", "OP": "Optimism", "TIA": "Celestia"
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

# --- УСИЛЕННАЯ ФУНКЦИЯ ДЛЯ DAILY BRIEFING ---
async def get_market_summary():
    """
    Собирает 'Железобетонные' данные для брифинга:
    1. Доминация BTC (CoinCap -> Fallback CoinGecko)
    2. Цена BTC (через get_crypto_price)
    3. ТОП ГЕЙНЕРЫ (Binance API) - Самый надежный источник
    """
    headers = {"User-Agent": "Mozilla/5.0"}
    summary = {}

    async with aiohttp.ClientSession(headers=headers) as session:
        # --- 1. ДОМИНАЦИЯ BTC ---
        dominance = "Unknown"
        # Попытка А: CoinCap
        try:
            async with session.get("https://api.coincap.io/v2/global", timeout=3) as response:
                if response.status == 200:
                    data = await response.json()
                    dom = float(data['data']['bitcoinDominancePercentage'])
                    dominance = f"{dom:.2f}"
        except: pass
        
        # Попытка Б: CoinGecko (если CoinCap упал)
        if dominance == "Unknown":
            try:
                async with session.get("https://api.coingecko.com/api/v3/global", timeout=3) as response:
                    if response.status == 200:
                        data = await response.json()
                        dom = float(data['data']['market_cap_percentage']['btc'])
                        dominance = f"{dom:.2f}"
            except: pass
        
        summary['btc_dominance'] = dominance

        # --- 2. ЦЕНА BTC ---
        btc_data, _ = await get_crypto_price("BTC")
        summary['btc_price'] = btc_data['price'] if btc_data else "Unknown"

        # --- 3. ТОП ГЕЙНЕРЫ (СЕКТОР ДНЯ) ЧЕРЕЗ BINANCE ---
        # Это даст реальных лидеров, а не ошибку API
        top_movers = []
        try:
            url = "https://api.binance.com/api/v3/ticker/24hr"
            async with session.get(url, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    # Фильтруем: только USDT пары, объем > 10M$ (чтобы убрать мусор)
                    valid_coins = []
                    for ticker in data:
                        symbol = ticker['symbol']
                        if symbol.endswith("USDT"):
                            vol = float(ticker['quoteVolume'])
                            if vol > 10_000_000: # Объем > 10 млн$
                                change = float(ticker['priceChangePercent'])
                                clean_sym = symbol.replace("USDT", "")
                                # Исключаем стейблы и левередж токены (UP/DOWN)
                                if "UP" not in clean_sym and "DOWN" not in clean_sym and clean_sym not in ["USDC", "FDUSD", "USDT"]:
                                    valid_coins.append({"symbol": clean_sym, "change": change})
                    
                    # Сортируем по росту (Топ-5 лидеров)
                    valid_coins.sort(key=lambda x: x['change'], reverse=True)
                    top_5 = valid_coins[:5]
                    
                    # Формируем строку: "SUI (+15%), SEI (+12%)"
                    top_movers = [f"{c['symbol']} ({c['change']:+.1f}%)" for c in top_5]
        except: pass

        if top_movers:
            summary['top_coins'] = ", ".join(top_movers)
        else:
            # Аварийный вариант (если даже Binance лежит)
            summary['top_coins'] = "BTC, ETH, SOL (Binance Data Unavailable)"

    return summary