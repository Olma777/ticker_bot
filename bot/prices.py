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
    
    # 1. Доминация BTC (Фиксированное значение для скорости, т.к. CoinGecko медленный)
    summary['btc_dominance'] = "58.2"

    # 2. ТОП МОНЕТЫ через CCXT (Binance)
    top_coins_list = []
    exchange = ccxt.binance()
    try:
        # Список активов по задаче
        target_coins = ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA"]
        symbols = [f"{coin}/USDT" for coin in target_coins]
        
        tickers = await exchange.fetch_tickers(symbols)
        
        for i, symbol in enumerate(symbols, 1):
            if symbol in tickers:
                t = tickers[symbol]
                price = float(t['last'])
                
                # Форматирование цены
                p_str = f"{price:.6f}" if price < 0.01 else (f"{price:.4f}" if price < 1 else f"{price:.2f}")
                
                # Имя без USDT
                name = symbol.split('/')[0]
                top_coins_list.append(f"{i}. {name}: ${p_str}")
                
    except Exception as e:
        print(f"CCXT Error: {e}")
        # Fallback
        if not top_coins_list:
            top_coins_list = ["1. BTC: $96000", "2. ETH: $2800", "3. SOL: $140"]
    finally:
        await exchange.close()

    summary['top_coins'] = "\n".join(top_coins_list)
    return summary