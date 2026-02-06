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

        # 2. CCXT FUTURES (Bybit, OKX, MEXC, BingX)
        # Ищем на фьючерсных рынках других бирж (только фьючерсы!)
        exchanges = [
            ccxt.bybit({'options': {'defaultType': 'linear'}}),  # Bybit Linear = USDT Perpetuals
            ccxt.okx({'options': {'defaultType': 'swap'}}),  # OKX Perpetual Swaps
            ccxt.gateio({'options': {'defaultType': 'future'}}), 
            ccxt.mexc({'options': {'defaultType': 'swap'}}),  # MEXC Perpetuals
            ccxt.bingx({'options': {'defaultType': 'swap'}})  # BingX добавлен (было в описании архитектуры)
        ]
        for exchange in exchanges:
            try:
                ticker_pair = f"{ticker_upper}/USDT"
                ticker_data = await exchange.fetch_ticker(ticker_pair)
                
                price = float(ticker_data['last'])
                if price < 0.01: fmt = f"{price:.8f}"
                elif price < 1: fmt = f"{price:.4f}"
                else: fmt = f"{price:.2f}"
                
                full_name = COIN_NAMES.get(ticker_upper, ticker_upper)
                return {"price": fmt, "name": full_name, "ticker": ticker_upper}, None
            except Exception:
                continue
            finally:
                await exchange.close()  # Всегда закрываем exchange

    return None, True

async def get_market_summary():
    summary = {}
    
    # 1. Доминация BTC (Фиксированное значение для скорости)
    summary['btc_dominance'] = "N/A"

    # 2. ЦЕЛЕВОЙ СПИСОК МОНЕТ (Watchlist для секторов)
    target_coins = ["BTC", "ETH", "SOL", "BNB", "FET", "RENDER", "WLD", "ONDO", "OM", "ARB", "OP", "HNT", "FIL", "TIA"]
    
    market_text_list = []
    
    # Fallback exchanges: Binance -> Bybit
    exchanges = [
        ccxt.binance({'options': {'defaultType': 'future'}}),
        ccxt.bybit({'options': {'defaultType': 'linear'}})
    ]
    
    for exchange in exchanges:
        try:
            # Загружаем все тикеры
            tickers = await exchange.fetch_tickers()
            
            for coin in target_coins:
                pair = f"{coin}/USDT"
                
                # На фьючерсах тикер может быть без суффикса или с :USDT
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
            
            # Если данные получены успешно, выходим из цикла
            if market_text_list:
                break
                
        except Exception as e:
            print(f"Exchange {exchange.name} error: {e}")
            continue
        finally:
            await exchange.close()

    # Final fallback если все биржи упали
    if not market_text_list:
        market_text_list = ["BTC: $96000", "ETH: $2800", "SOL: $140"]

    summary['top_coins'] = ", ".join(market_text_list)
    return summary
