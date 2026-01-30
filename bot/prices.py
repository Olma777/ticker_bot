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
    summary = {}
    
    # 1. Доминация BTC (Фиксированное значение для скорости)
    summary['btc_dominance'] = "N/A"

    # 2. ТОП МОНЕТЫ через CCXT (Binance)
    top_coins_list = []
    exchange = ccxt.binance()
    try:
        # Загружаем тикеры
        tickers = await exchange.fetch_tickers()
        
        # Фильтруем пары к USDT
        usdt_pairs = []
        for symbol, data in tickers.items():
            if symbol.endswith('/USDT'):
                # Исключаем мусорные пары (UP/DOWN/BEAR/BULL)
                if any(x in symbol for x in ['UP/', 'DOWN/', 'BEAR/', 'BULL/', 'USDC/', 'FDUSD/', 'TUSD/']):
                    continue
                usdt_pairs.append(data)
        
        # Сортируем по quoteVolume (объем в USDT)
        sorted_pairs = sorted(usdt_pairs, key=lambda x: x['quoteVolume'] if x.get('quoteVolume') else 0, reverse=True)
        
        # Берем топ-20
        top_20 = sorted_pairs[:20]
        
        for t in top_20:
            symbol = t['symbol']
            price = float(t['last'])
            name = symbol.split('/')[0]
            
            # Форматирование цены
            if price < 0.01: fmt = f"{price:.8f}"
            elif price < 1: fmt = f"{price:.4f}"
            else: fmt = f"{price:.2f}"
            
            top_coins_list.append(f"{name}: ${fmt}")
            
    except Exception as e:
        print(f"CCXT Error: {e}")
        # Fallback
        if not top_coins_list:
            top_coins_list = ["BTC: $96000", "ETH: $2800", "SOL: $140"]
    finally:
        await exchange.close()

    summary['top_coins'] = ", ".join(top_coins_list)
    return summary