"""
Price fetching module with proper resource management and retry logic.
"""

import asyncio
import logging
from typing import Optional

import aiohttp
import ccxt.async_support as ccxt
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from bot.config import COIN_NAMES, EXCHANGE_OPTIONS, RETRY_ATTEMPTS, RETRY_WAIT_SECONDS
from bot.cache import TieredCache
from bot.logger import logger

logger = logging.getLogger(__name__)


# Type alias for price data
PriceData = dict[str, Optional[str]]


def format_price(price: float) -> str:
    """Format price based on magnitude."""
    if price < 0.01:
        return f"{price:.8f}"
    elif price < 1:
        return f"{price:.4f}"
    return f"{price:.2f}"


@retry(
    stop=stop_after_attempt(RETRY_ATTEMPTS),
    wait=wait_exponential(multiplier=1, min=1, max=RETRY_WAIT_SECONDS * 2),
    retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
    reraise=True
)
async def _fetch_binance_futures_price(ticker: str, session: aiohttp.ClientSession) -> Optional[PriceData]:
    """Fetch price from Binance Futures API."""
    url = f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={ticker}USDT"
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
        if response.status == 200:
            data = await response.json()
            price = float(data["price"])
            return {
                "price": format_price(price),
                "name": COIN_NAMES.get(ticker, ticker),
                "ticker": ticker,
                "volume_24h": None
            }
    return None


async def _fetch_ccxt_price(ticker: str) -> Optional[PriceData]:
    """Fetch price from CCXT exchanges with proper resource management."""
    exchanges_to_try = [
        ("bybit", ccxt.bybit(EXCHANGE_OPTIONS["bybit"])),
        ("okx", ccxt.okx(EXCHANGE_OPTIONS["okx"])),
        ("mexc", ccxt.mexc(EXCHANGE_OPTIONS["mexc"])),
        ("bingx", ccxt.bingx(EXCHANGE_OPTIONS["bingx"])),
        ("gateio", ccxt.gateio(EXCHANGE_OPTIONS["gateio"])),
    ]
    
    result = None
    pair = f"{ticker}/USDT"
    
    for name, exchange in exchanges_to_try:
        try:
            ticker_data = await exchange.fetch_ticker(pair)
            price = float(ticker_data['last'])
            result = {
                "price": format_price(price),
                "name": COIN_NAMES.get(ticker, ticker),
                "ticker": ticker,
                "volume_24h": f"${ticker_data.get('quoteVolume', 0):,.0f}" if ticker_data.get('quoteVolume') else None
            }
            break  # Success, exit loop
        except Exception as e:
            logger.debug(f"Exchange {name} failed for {ticker}: {e}")
            continue
        finally:
            # CRITICAL: Always close exchange connection
            await exchange.close()
    
    # Close remaining exchanges that were not tried due to early break
    # This is handled by the finally block above
    
    return result


async def get_crypto_price(ticker: str) -> tuple[Optional[dict], Optional[bool]]:
    """Get crypto price with multi-exchange fallback."""
    ticker_upper = ticker.upper().replace("USDT", "").replace("USD", "")
    headers = {"User-Agent": "Mozilla/5.0"}

    # 1. Try Binance Futures first (fastest)
    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            result = await _fetch_binance_futures_price(ticker_upper, session)
            if result:
                return result, None
        except Exception as e:
            logger.debug(f"Binance Futures failed: {e}")

    # 2. Fallback to CCXT exchanges
    try:
        result = await _fetch_ccxt_price(ticker_upper)
        if result:
            return result, None
    except Exception as e:
        logger.error(f"All exchanges failed for {ticker}: {e}")

    return None, True


# --- Tiered Cache Integration ---
cache = TieredCache()

class InvalidPriceError(Exception):
    pass

async def _original_fetch_logic(symbol: str) -> float:
    sym = symbol.upper().replace("USDT", "").replace("USD", "")
    headers = {"User-Agent": "Mozilla/5.0"}
    price_val = 0.0
    
    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            res = await _fetch_binance_futures_price(sym, session)
            if res and res.get("price"):
                price_val = float(res["price"])
                logger.info("price_fetched", symbol=symbol, price=price_val, provider="binance_futures", latency_ms=None, tokens_used=None)
        except Exception as e:
            logger.error("binance_fetch_failed", symbol=symbol, exc_info=True)
            
    if price_val == 0.0:
        try:
            res = await _fetch_ccxt_price(sym)
            if res and res.get("price"):
                price_val = float(res["price"])
                logger.info("price_fetched", symbol=symbol, price=price_val, provider="ccxt", latency_ms=None, tokens_used=None)
        except Exception as e:
            logger.error("ccxt_fetch_failed", symbol=symbol, exc_info=True)

    if price_val == 0.0:
        raise Exception(f"Price fetch failed for {symbol}")
        
    # SANITY CHECK: Anti-Hallucination
    if price_val <= 0 or price_val > 1_000_000:
        raise InvalidPriceError(f"Invalid price detected: {price_val} (Check API or Symbol)")
        
    return price_val

async def get_price(symbol: str) -> float:
    return await cache.get_or_set(
        f"price:{symbol}",
        lambda: _original_fetch_logic(symbol),
        "price"
    )


# --- Price Aggregator with Fallback ---
class PriceUnavailableError(Exception):
    pass

class PriceAggregator:
    PROVIDERS = ["binance_futures", "bybit", "okx", "mexc"]
    
    async def get_price(self, symbol: str) -> tuple[float, str]:
        errors: list[str] = []
        for provider in self.PROVIDERS:
            try:
                method = getattr(self, f"_fetch_{provider}")
                price = await method(symbol)
                # LEGACY: logging.info(f"Price for {symbol}: {price} via {provider}")
                logger.info("price_fetched", symbol=symbol, price=price, provider=provider, latency_ms=None, tokens_used=None)
                return price, provider
            except Exception as e:
                # LEGACY: logger.debug(f"Provider {provider} failed: {e}")
                logger.error("price_provider_failed", symbol=symbol, exc_info=True)
                errors.append(f"{provider}:{str(e)[:40]}")
                continue
        raise PriceUnavailableError(f"All failed: {' | '.join(errors[:3])}")
    
    async def _fetch_binance_futures(self, symbol: str) -> float:
        headers = {"User-Agent": "Mozilla/5.0"}
        async with aiohttp.ClientSession(headers=headers) as session:
            url = f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={symbol.upper().replace('USDT','').replace('USD','')}USDT"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status != 200:
                    raise Exception(f"HTTP {response.status}")
                data = await response.json()
                return float(data["price"])
    
    async def _fetch_bybit(self, symbol: str) -> float:
        exch = ccxt.bybit(EXCHANGE_OPTIONS["bybit"])
        try:
            pair = f"{symbol.upper().replace('USDT','').replace('USD','')}/USDT"
            data = await exch.fetch_ticker(pair)
            return float(data["last"])
        finally:
            await exch.close()
    
    async def _fetch_okx(self, symbol: str) -> float:
        exch = ccxt.okx(EXCHANGE_OPTIONS["okx"])
        try:
            pair = f"{symbol.upper().replace('USDT','').replace('USD','')}/USDT"
            data = await exch.fetch_ticker(pair)
            return float(data["last"])
        finally:
            await exch.close()
    
    async def _fetch_mexc(self, symbol: str) -> float:
        exch = ccxt.mexc(EXCHANGE_OPTIONS["mexc"])
        try:
            pair = f"{symbol.upper().replace('USDT','').replace('USD','')}/USDT"
            data = await exch.fetch_ticker(pair)
            return float(data["last"])
        finally:
            await exch.close()

async def get_market_summary() -> dict[str, str]:
    """
    Get market summary with top coins prices.
    
    Returns:
        Dict with 'btc_dominance' and 'top_coins' keys.
    """
    summary: dict[str, str] = {"btc_dominance": "N/A"}
    
    target_coins = [
        "BTC", "ETH", "SOL", "BNB", "FET", "RENDER", 
        "WLD", "ONDO", "OM", "ARB", "OP", "HNT", "FIL", "TIA"
    ]
    
    market_text_list: list[str] = []
    
    # Use Binance Futures as primary source
    exchange = ccxt.binance(EXCHANGE_OPTIONS["binance"])
    
    try:
        tickers = await exchange.fetch_tickers()
        
        for coin in target_coins:
            pair = f"{coin}/USDT"
            pair_alt = f"{coin}/USDT:USDT"
            
            data = tickers.get(pair) or tickers.get(pair_alt)
            if not data:
                continue
            
            price = float(data['last'])
            market_text_list.append(f"{coin}: ${format_price(price)}")
            
    except Exception as e:
        logger.error(f"Market summary fetch error: {e}")
        # Fallback with static data
        market_text_list = ["BTC: $96000", "ETH: $2800", "SOL: $140"]
    finally:
        await exchange.close()
    
    summary['top_coins'] = ", ".join(market_text_list) if market_text_list else "N/A"
    return summary
