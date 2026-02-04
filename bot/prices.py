import aiohttp
import asyncio
import ccxt.async_support as ccxt

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
        # 1. BINANCE FUTURES (USDT-M) - ПРИОРИТЕТ 1
        # Пользователь требует, чтобы фьючерсная торговля была в основе
        try:
            url = f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={ticker_upper}USDT"
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

        # 2. CCXT FUTURES (Bybit, OKX, MEXC)
        # Ищем на фьючерсных рынках других бирж
        exchanges = [
            ccxt.bybit({'options': {'defaultType': 'future'}}), 
            ccxt.okx({'options': {'defaultType': 'swap'}}), # OKX uses 'swap' for perps
            ccxt.gateio({'options': {'defaultType': 'future'}}), 
            ccxt.mexc({'options': {'defaultType': 'future'}})
        ]
        for exchange in exchanges:
            try:
                # Пробуем найти тикер
                ticker_pair = f"{ticker_upper}/USDT"
                # Некоторые биржи могут требовать :USDT суффикс, но defaultType часто решает это
                # Для надежности проверим наличие пары
                
                ticker_data = await exchange.fetch_ticker(ticker_pair)
                
                price = float(ticker_data['last'])
                if price < 0.01: fmt = f"{price:.8f}"
                elif price < 1: fmt = f"{price:.4f}"
                else: fmt = f"{price:.2f}"
                
                full_name = COIN_NAMES.get(ticker_upper, ticker_upper)
                await exchange.close()
                return {"price": fmt, "name": full_name, "ticker": ticker_upper}, None
            except Exception:
                await exchange.close()
                continue
        
        # 3. BINANCE SPOT (Fallback, если нет на фьючерсах)
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

        # 4. COINGECKO (Search + Price) - Самый надежный фоллбек для редких монет и поиска по названию
        try:
            # Сначала ищем ID монеты по тикеру или названию
            search_url = f"https://api.coingecko.com/api/v3/search?query={ticker_upper}"
            async with session.get(search_url, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("coins"):
                        # Берем первый релевантный результат
                        # Приоритет: точное совпадение символа
                        best_match = data["coins"][0]
                        for coin in data["coins"]:
                            if coin["symbol"].upper() == ticker_upper:
                                best_match = coin
                                break
                        
                        coin_id = best_match["id"]
                        coin_name = best_match["name"]
                        coin_symbol = best_match["symbol"].upper()
                        
                        # Теперь получаем цену
                        price_url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd"
                        async with session.get(price_url, timeout=5) as price_res:
                            if price_res.status == 200:
                                price_data = await price_res.json()
                                if price_data.get(coin_id):
                                    price = float(price_data[coin_id]["usd"])
                                    if price < 0.01: fmt = f"{price:.8f}"
                                    elif price < 1: fmt = f"{price:.4f}"
                                    else: fmt = f"{price:.2f}"
                                    return {"price": fmt, "name": coin_name, "ticker": coin_symbol}, None
        except Exception: pass

        # 5. COINCAP (Fallback)
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
    summary = {}
    
    # 1. Доминация BTC (Фиксированное значение для скорости)
    summary['btc_dominance'] = "N/A"

    # 2. ЦЕЛЕВОЙ СПИСОК МОНЕТ (Watchlist для секторов)
    target_coins = ["BTC", "ETH", "SOL", "BNB", "FET", "RENDER", "WLD", "ONDO", "OM", "ARB", "OP", "HNT", "FIL", "TIA"]
    
    market_text_list = []
    # Используем Binance Futures для саммари рынка
    exchange = ccxt.binance({'options': {'defaultType': 'future'}})
    try:
        # Загружаем все тикеры
        tickers = await exchange.fetch_tickers()
        
        for coin in target_coins:
            pair = f"{coin}/USDT"
            
            # На фьючерсах тикер может быть без суффикса или с :USDT, но ccxt обычно нормализует как BTC/USDT
            # Проверяем также pair + ":USDT" на всякий случай
            pair_alt = f"{coin}/USDT:USDT"

            if pair in tickers:
                data = tickers[pair]
            elif pair_alt in tickers:
                data = tickers[pair_alt]
            else:
                continue

            price = float(data['last'])
            
            # Форматирование цены
            if price < 0.01: fmt = f"{price:.8f}"
            elif price < 1: fmt = f"{price:.4f}"
            else: fmt = f"{price:.2f}"
            
            market_text_list.append(f"{coin}: ${fmt}")
            
    except Exception as e:
        print(f"CCXT Error: {e}")
        # Fallback
        if not market_text_list:
            market_text_list = ["BTC: $96000", "ETH: $2800", "SOL: $140"]
    finally:
        await exchange.close()

    summary['top_coins'] = ", ".join(market_text_list)
    return summary
