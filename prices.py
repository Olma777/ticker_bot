import aiohttp

# Шпаргалка имен (на случай если источник не отдаст имя)
COIN_NAMES = {
    "BTC": "Bitcoin", "ETH": "Ethereum", "USDT": "Tether", "BNB": "BNB",
    "SOL": "Solana", "XRP": "XRP", "USDC": "USDC", "ADA": "Cardano",
    "AVAX": "Avalanche", "DOGE": "Dogecoin", "TON": "Toncoin", 
    "PEPE": "Pepe", "SHIB": "Shiba Inu"
}

async def get_crypto_price(ticker):
    """
    Ищет цену в 3 источниках: CoinCap -> Binance -> DexScreener (DEX).
    """
    ticker_upper = ticker.upper().replace("USDT", "").replace("USD", "")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    async with aiohttp.ClientSession(headers=headers) as session:
        
        # --- 1. COINCAP (Топовые монеты + Рейтинг) ---
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
        except Exception:
            pass 

        # --- 2. BINANCE (Биржевые цены) ---
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
        except Exception:
            pass

        # --- 3. DEXSCREENER (Мем-коины, Щиткоины, Новинки) ---
        # Самый мощный поиск: находит всё, что есть на DEX (Uniswap, Raydium и т.д.)
        try:
            # Ищем пары по тикеру
            url = f"https://api.dexscreener.com/latest/dex/search?q={ticker_upper}"
            async with session.get(url, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    pairs = data.get('pairs', [])
                    
                    if pairs:
                        # Берем самую ликвидную пару (первую в списке)
                        best_pair = pairs[0]
                        price = float(best_pair['priceUsd'])
                        
                        # Красивый формат цены (для мемов с кучей нулей: 0.00004)
                        if price < 0.01:
                            fmt_price = f"{price:.8f}"
                        elif price < 1:
                            fmt_price = f"{price:.4f}"
                        else:
                            fmt_price = f"{price:.2f}"

                        # Определяем сеть (Solana, Base, Ethereum)
                        chain = best_pair.get('chainId', 'DEX').capitalize()
                        full_name = best_pair['baseToken']['name']
                        
                        return {
                            "price": fmt_price,
                            "name": f"{full_name} ({chain})", # Добавляем название сети
                            "rank": "DEX", # У таких монет нет официального ранга
                            "ticker": ticker_upper
                        }, None
        except Exception:
            pass

    return None, True