"""
Market Data Component (Phase 2).
Fetches FRESH data from Binance via CCXT.
Calculates indicators using refactored math module.
Updated to populate Candle Data.
"""

import logging
import asyncio
import pandas as pd
import ccxt.async_support as ccxt
from typing import Optional

from bot.config import Config, EXCHANGE_OPTIONS, TRADING
from bot.decision_models import MarketContext
from bot.models.market_context import MarketContext as DTOContext
from bot.indicators import (
    calculate_atr, 
    calculate_rsi, 
    calculate_vwap_24h,
    calculate_global_regime,
    fetch_funding_rate
)
from bot.prices import get_price
from bot.prices import PriceAggregator, PriceUnavailableError

logger = logging.getLogger(__name__)


async def fetch_ohlcv(
    exchange: ccxt.Exchange, 
    symbol: str, 
    timeframe: str, 
    limit: int
) -> Optional[pd.DataFrame]:
    """Fetch OHLCV data safely."""
    try:
        ohlcv = await exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        if not ohlcv:
            return None
        df = pd.DataFrame(ohlcv, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
        return df
    except Exception as e:
        logger.error(f"Error fetching {symbol}: {e}")
        return None


async def get_market_context(symbol: str) -> MarketContext:
    """
    Fetch market context (Price, ATR, RSI, VWAP, Regime, Candle).
    """
    # Initialize Exchange
    exchange_id = "binance"
    options = EXCHANGE_OPTIONS.get(exchange_id, {})
    exchange_class = getattr(ccxt, exchange_id)
    
    async with exchange_class(options) as exchange:
        try:
            # Parallel Fetch: Symbol M30 + BTC M30 (for Regime)
            # Symbol format: Ensure UPPER/USDT
            formatted_symbol = symbol.upper()
            if "/" not in formatted_symbol:
                formatted_symbol += "/USDT"
            
            # Fetch Tasks
            target_task = fetch_ohlcv(exchange, formatted_symbol, TRADING.timeframe, 100)
            btc_task = fetch_ohlcv(exchange, "BTC/USDT", TRADING.timeframe, 300) # Need more for Regime
            
            df_target, df_btc = await asyncio.gather(target_task, btc_task)
            
            # Use Fallback if target data failed
            if df_target is None or df_target.empty or len(df_target) < 50:
                logger.warning(f"Insufficient data for {symbol}")
                return MarketContext(
                    price=0.0, atr=0.0, rsi=50.0, vwap=0.0, 
                    regime="NEUTRAL", 
                    candle_open=0.0, candle_high=0.0, candle_low=0.0, candle_close=0.0,
                    data_quality="DEGRADED"
                )

            # Calculations
            current_price = float(df_target['close'].iloc[-1])
            candle = df_target.iloc[-1]
            c_open = float(candle['open'])
            c_high = float(candle['high'])
            c_low = float(candle['low'])
            c_close = float(candle['close'])
            
            # ATR
            atr_series = calculate_atr(df_target)
            atr = float(atr_series.iloc[-1])
            
            # RSI
            rsi_series = calculate_rsi(df_target)
            rsi = float(rsi_series.iloc[-1])
            
            # VWAP
            vwap = calculate_vwap_24h(df_target)
            
            # Regime (BTC ROC)
            regime_label, _ = calculate_global_regime(df_btc)
            
            # Data Quality Check
            quality = "OK"
            if atr == 0 or vwap == 0:
                quality = "DEGRADED"

            try:
                aggregator = PriceAggregator()
                fetched_price, _prov = await aggregator.get_price(symbol)
                current_price = float(fetched_price)
            except PriceUnavailableError:
                pass

            return MarketContext(
                price=current_price,
                atr=atr,
                rsi=rsi,
                vwap=vwap,
                regime=regime_label,
                candle_open=c_open,
                candle_high=c_high,
                candle_low=c_low,
                candle_close=c_close,
                data_quality=quality
            )

        except Exception as e:
            logger.error(f"Market Context Error: {e}")
            return MarketContext(
                price=0.0, atr=0.0, rsi=50.0, vwap=0.0, 
                regime="NEUTRAL",
                candle_open=0.0, candle_high=0.0, candle_low=0.0, candle_close=0.0,
                data_quality="DEGRADED"
            )


async def fetch_market_context(symbol: str) -> DTOContext:
    s = symbol.upper()
    if "/" not in s:
        s = f"{s}/USDT"
    price = await get_price(s)
    exchange_id = "binance"
    options = EXCHANGE_OPTIONS.get(exchange_id, {})
    exchange_class = getattr(ccxt, exchange_id)
    async with exchange_class(options) as exchange:
        btc_df = await fetch_ohlcv(exchange, "BTC/USDT", TRADING.timeframe, 300)
        df = await fetch_ohlcv(exchange, s, TRADING.timeframe, 150)
        regime_label, _ = calculate_global_regime(btc_df) if btc_df is not None else ("NEUTRAL", None)
        atr_val = float(calculate_atr(df).iloc[-1]) if df is not None else 0.0
        vwap_val = calculate_vwap_24h(df) if df is not None else 0.0
        funding = await fetch_funding_rate(exchange, s)
    regime_map = {"EXPANSION": "bullish", "COMPRESSION": "bearish", "NEUTRAL": "neutral"}
    btc_regime = regime_map.get(regime_label, "neutral")
    return DTOContext(
        symbol=s,
        price=float(price),
        btc_regime=btc_regime, 
        atr=atr_val,
        vwap=vwap_val if vwap_val != 0 else None,
        funding_rate=funding
    )
