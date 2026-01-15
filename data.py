import aiohttp

# РАСШИРЕННАЯ ШПАРГАЛКА (TOP 150+)
# Используется только если CoinCap не смог определить имя
COIN_NAMES = {
    # TOP 10
    "BTC": "Bitcoin", "ETH": "Ethereum", "USDT": "Tether", "BNB": "BNB",
    "SOL": "Solana", "XRP": "XRP", "USDC": "USDC", "ADA": "Cardano",
    "AVAX": "Avalanche", "DOGE": "Dogecoin",
    
    # POPULAR L1/L2
    "TRX": "TRON", "DOT": "Polkadot", "LINK": "Chainlink", "MATIC": "Polygon",
    "TON": "Toncoin", "LTC": "Litecoin", "BCH": "Bitcoin Cash", "ATOM": "Cosmos",
    "NEAR": "NEAR Protocol", "APT": "Aptos", "ARB": "Arbitrum", "OP": "Optimism",
    "SUI": "Sui", "SEI": "Sei", "HBAR": "Hedera", "EGLD": "MultiversX",
    "ICP": "Internet Computer", "KAS": "Kaspa", "FTM": "Fantom", "INJ": "Injective",
    "ALGO": "Algorand", "XLM": "Stellar", "XMR": "Monero", "ETC": "Ethereum Classic",
    "VET": "VeChain", "EOS": "EOS", "FLOW": "Flow", "XTZ": "Tezos",

    # DEFI & INFRA
    "UNI": "Uniswap", "LDO": "Lido DAO", "MKR": "Maker", "AAVE": "Aave",
    "RUNE": "THORChain", "SNX": "Synthetix", "GRT": "The Graph", "RNDR": "Render",
    "FIL": "Filecoin", "AR": "Arweave", "THETA": "Theta Network", "JUP": "Jupiter",
    "TIA": "Celestia", "PYTH": "Pyth Network", "IMX": "Immutable",

    # MEME COINS
    "SHIB": "Shiba Inu", "PEPE": "Pepe", "WIF": "dogwifhat", "FLOKI": "Floki",
    "BONK": "Bonk", "BOME": "Book of Meme", "MEME": "Memecoin", "DOGS": "DOGS",
    "NOT": "Notcoin", "BRETT": "Brett", "POPCAT": "Popcat",

    # AI & GAMING
    "FET": "Fetch.ai", "TAO": "Bittensor", "WLD": "Worldcoin", "AXS": "Axie Infinity",
    "SAND": "The Sandbox", "MANA": "Decentraland", "GALA": "Gala", "APE": "ApeCoin",
    "BEAM": "Beam", "QNT": "Quant"
}

async def get_crypto_price(ticker):
    """
    Возвращает словарь с данными.
    Логика:
    1. Ищем в CoinCap (там есть полные имена и ранг).
    2. Если нет -> Ищем в Binance и берем имя из шпаргалки COIN_NAMES.
    3. Если нет в шпаргалке -> Имя будет равно Тикеру.
    """
    ticker_upper = ticker.upper().replace("USDT", "").replace("USD", "")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    async with aiohttp.ClientSession(headers=headers) as session:
        
        # --- PLAN A: COINCAP (Лучший вариант) ---
        try:
            url = f"https://api.coincap.io/v2/assets?search={ticker_upper}"
            async with session.get(url, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    for coin in data['data']:
                        # Точное совпадение тикера
                        if coin['symbol'] == ticker_upper:
                            price = float(coin['priceUsd'])
                            
                            if price < 1: fmt_price = f"{price:.6f}"
                            else: fmt_price = f"{price:.2f}"

                            return {
                                "price": fmt_price,
                                "name": coin['name'],       # Берем имя отсюда (например "Solana")
                                "rank": coin['rank'],       # Берем ранг отсюда
                                "ticker": coin['symbol']
                            }, None
        except Exception:
            pass # Если CoinCap упал, идем к Plan B

        # --- PLAN B: BINANCE (Запасной) ---
        try:
            url = f"https://api.binance.com/api/v3/ticker/price?symbol={ticker_upper}USDT"
            async with session.get(url, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    price = float(data["price"])
                    fmt_price = f"{price:g}"
                    
                    # Ищем имя в нашей огромной шпаргалке
                    # Если там нет ключа ticker_upper, вернется сам ticker_upper
                    full_name = COIN_NAMES.get(ticker_upper, ticker_upper)
                    
                    return {
                        "price": fmt_price,
                        "name": full_name,  # Берем из шпаргалки
                        "rank": "?",
                        "ticker": ticker_upper
                    }, None
        except Exception:
            pass

    return None, True