import aiohttp

async def get_crypto_price(ticker):
    """
    Возвращает словарь с полной информацией:
    {
        "price": "4.29",
        "name": "Internet Computer",
        "rank": "25",
        "ticker": "ICP"
    }
    """
    ticker_upper = ticker.upper().replace("USDT", "").replace("USD", "")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    async with aiohttp.ClientSession(headers=headers) as session:
        
        # --- ИСТОЧНИК 1: COINCAP (Дает РЕЙТИНГ и ИМЯ) ---
        try:
            url = f"https://api.coincap.io/v2/assets?search={ticker_upper}"
            async with session.get(url, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    for coin in data['data']:
                        if coin['symbol'] == ticker_upper:
                            price = float(coin['priceUsd'])
                            
                            if price < 1:
                                fmt_price = f"{price:.6f}"
                            else:
                                fmt_price = f"{price:.2f}"

                            return {
                                "price": fmt_price,
                                "name": coin['name'],
                                "rank": coin['rank'],
                                "ticker": coin['symbol']
                            }, None
        except Exception:
            pass 

        # --- ИСТОЧНИК 2: BINANCE (Запасной) ---
        try:
            url = f"https://api.binance.com/api/v3/ticker/price?symbol={ticker_upper}USDT"
            async with session.get(url, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    price = float(data["price"])
                    fmt_price = f"{price:g}"
                    
                    return {
                        "price": fmt_price,
                        "name": ticker_upper,
                        "rank": "?",
                        "ticker": ticker_upper
                    }, None
        except Exception:
            pass

    return None, True