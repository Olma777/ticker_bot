"""
Sentiment Data Component.
Fetches Funding Rate and Open Interest.
"""

import logging
import asyncio
from typing import Optional

import ccxt.async_support as ccxt

from bot.config import Config, EXCHANGE_OPTIONS
from bot.decision_models import SentimentContext

logger = logging.getLogger("DecisionEngine-Sentiment")


async def load_sentiment(symbol: str) -> SentimentContext:
    """
    Fetches Funding Rate and Open Interest.
    Returns SentimentContext.
    """
    exchange_id = "binance"
    options = EXCHANGE_OPTIONS.get(exchange_id, {})
    
    try:
        exchange_class = getattr(ccxt, exchange_id)
        async with exchange_class(options) as exchange:
            # Parallel fetch
            funding_task = exchange.fetch_funding_rate(symbol)
            ticker_task = exchange.fetch_ticker(symbol)  # Often contains Open Interest
            
            try:
                # Funding Rate
                funding_data = await funding_task
                funding_rate = funding_data.get('fundingRate')
                
                # Open Interest (Try ticker first, might need specific endpoint)
                # Note: CCXT mapping varies. For Binance valid.
                # If ticker doesn't have it, we accept None.
                # Ideally use fetch_open_interest if supported.
                open_interest = None
                if exchange.has['fetchOpenInterest']:
                     oi_data = await exchange.fetch_open_interest(symbol)
                     open_interest = oi_data.get('openInterestValue') # Quote currency value
                
                if funding_rate is None:
                     raise ValueError("Funding rate missing")

                return SentimentContext(
                    funding=funding_rate,
                    open_interest=open_interest,
                    data_quality="OK"
                )

            except Exception as inner_e:
                logger.warning(f"Partial sentiment fail for {symbol}: {inner_e}")
                return SentimentContext(
                    funding=None,
                    open_interest=None,
                    data_quality="DEGRADED"
                )
                
    except Exception as e:
        logger.error(f"Failed to fetch sentiment for {symbol}: {e}")
        return SentimentContext(
            funding=None,
            open_interest=None,
            data_quality="DEGRADED"
        )
