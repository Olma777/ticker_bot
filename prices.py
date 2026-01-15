import aiohttp

# Шпаргалка имен (на случай если CoinCap не найдет)
COIN_NAMES = {
    "BTC": "Bitcoin", "ETH": "Ethereum", "USDT": "Tether", "BNB": "BNB",
    "SOL": "Solana", "XRP": "XRP", "USDC": "USDC", "ADA": "Cardano",
    "AVAX": "Avalanche", "DOGE": "Dogecoin", "TRX": "TRON", "DOT": "Polkadot",
    "LINK": "Chainlink", "MATIC": "Polygon", "TON": "Toncoin", "SHIB": "Shiba Inu",
    "LTC": "Litecoin", "BCH": "Bitcoin Cash", "ATOM": "Cosmos", "UNI": "Uniswap",
    "ICP": "Internet Computer", "NEAR": "NEAR Protocol", "APT": "Aptos", 
    "ARB": "Arbitrum", "OP": "Optimism", "PEPE": "Pepe"
}

async def get_crypto_price(ticker):
    """
    Возвращает словарь с данными: {price, name, rank, ticker}
    """
    ticker_upper = ticker.upper().replace("USDT", "").replace("USD", "")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

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
        except Exception:
            pass 

        # 2. BINANCE
        try:
            url = f"https://api.binance.com/api/v3/ticker/price?symbol={ticker_upper}USDT"
            async with session.get(url, timeout=5) as response:
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

    return None, True
