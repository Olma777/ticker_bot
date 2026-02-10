"""
Sentiment Module (Phase 2).
Fetches Funding Rate and Open Interest.
"""

import logging
import ccxt.async_support as ccxt
from bot.config import EXCHANGE_OPTIONS
from bot.decision_models import SentimentContext

logger = logging.getLogger(__name__)


async def get_sentiment(symbol: str) -> SentimentContext:
    """
    Fetch Funding and OI.
    """
    exchange_id = "binance"
    options = EXCHANGE_OPTIONS.get(exchange_id, {})
    exchange_class = getattr(ccxt, exchange_id)
    
    async with exchange_class(options) as exchange:
        try:
            formatted_symbol = symbol.upper()
            if "/" not in formatted_symbol:
                formatted_symbol += "/USDT"
                
            # Fetch Funding
            funding_resp = await exchange.fetch_funding_rate(formatted_symbol)
            funding = float(funding_resp['fundingRate']) if funding_resp else 0.0
            
            # Fetch OI
            try:
                oi_resp = await exchange.fetch_open_interest(formatted_symbol)
                oi = float(oi_resp['openInterestAmount']) if oi_resp else 0.0
            except Exception:
                oi = 0.0 # Not all pairs support OI
                
            # Basic "Hot" logic (Placeholder)
            # Real implementation would compare to Avg OI, but for now:
            is_hot = False 
            
            return SentimentContext(
                funding=funding,
                open_interest=oi,
                is_hot=is_hot,
                data_quality="OK"
            )
            
        except Exception as e:
            logger.error(f"Sentiment Error {symbol}: {e}")
            return SentimentContext(
                funding=0.0, open_interest=0.0, is_hot=False, data_quality="DEGRADED"
            )
