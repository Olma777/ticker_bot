import aiohttp

async def get_crypto_price(ticker):
    """
    Ищет цену на Binance, затем на Coinbase, затем на CryptoCompare.
    Возвращает (цена, ошибка).
    """
    ticker = ticker.upper().replace("USDT", "").replace("USD", "")
    
    # Притворяемся браузером (обязательно!)
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    async with aiohttp.ClientSession(headers=headers) as session:
        
        # --- ПОПЫТКА 1: BINANCE (Самый быстрый) ---
        try:
            # Binance хочет формат BTCUSDT
            url = f"https://api.binance.com/api/v3/ticker/price?symbol={ticker}USDT"
            async with session.get(url, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    price = float(data["price"])
                    # :g убирает лишние нули (150.5000 -> 150.5)
                    return f"{price:g}", None
        except Exception:
            pass # Если ошибка, молча идем к следующему источнику

        # --- ПОПЫТКА 2: COINBASE (Если на Бинансе нет) ---
        try:
            # Coinbase хочет формат BTC-USD
            url = f"https://api.coinbase.com/v2/prices/{ticker}-USD/spot"
            async with session.get(url, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    price = data["data"]["amount"]
                    return str(price), None
        except Exception:
            pass

        # --- ПОПЫТКА 3: CRYPTOCOMPARE (Для редких монет) ---
        try:
            url = f"https://min-api.cryptocompare.com/data/price?fsym={ticker}&tsyms=USD"
            async with session.get(url, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    if "USD" in data:
                        return str(data["USD"]), None
        except Exception:
            pass

    # Если нигде не нашли
    return None, True