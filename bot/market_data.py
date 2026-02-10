"""
Market Data Component.
Fetches OHLCV and calculates indicators (ATR, RSI, VWAP) via CCXT.
Strictly deterministic, no AI guessing.
Updated for P1-Final: Includes Open price for K1 check.
"""

import logging
import asyncio
from typing import Optional, List
from datetime import datetime, timezone

import ccxt.async_support as ccxt
import pandas as pd
import numpy as n

from bot.config import Config, EXCHANGE_OPTIONS
from bot.decision_models import MarketContext

logger = logging.getLogger("DecisionEngine-MarketData")


async def fetch_ohlcv(symbol: str, timeframe: str = "30m", limit: int = 100) -> pd.DataFrame:
    """
    Fetch OHLCV data from Binance (or fallback).
    Returns DataFrame with columns: timestamp, open, high, low, close, volume.
    """
    exchange_id = "binance"
    options = EXCHANGE_OPTIONS.get(exchange_id, {})
    
    try:
        exchange_class = getattr(ccxt, exchange_id)
        async with exchange_class(options) as exchange:
            ohlcv = await exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            
            df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            return df
            
    except Exception as e:
        logger.error(f"Failed to fetch OHLCV for {symbol}: {e}")
        return pd.DataFrame()


def calculate_atr(df: pd.DataFrame, period: int = 14) -> float:
    """Calculate Relative ATR (Last value only)."""
    if len(df) < period + 1:
        return 0.0
        
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close = (df["low"] - df["close"].shift()).abs()
    
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    
    return float(atr.iloc[-1])


def calculate_rsi(df: pd.DataFrame, period: int = 14) -> float:
    """Calculate RSI (Last value only)."""
    if len(df) < period + 1:
        return 50.0
        
    delta = df["close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    return float(rsi.iloc[-1])


def calculate_vwap(df: pd.DataFrame) -> float:
    """
    Calculate Rolling VWAP (Session).
    Simulated as rolling 24h VWAP for simplicity if session data unavailable.
    """
    if df.empty:
        return 0.0
        
    v = df["volume"]
    tp = (df["high"] + df["low"] + df["close"]) / 3
    
    vwap = (tp * v).cumsum() / v.cumsum()
    return float(vwap.iloc[-1])


def determine_regime(close: float, vwap: float) -> str:
    """
    Simple regime detection.
    CLOSE > VWAP -> BULLISH_TREND
    CLOSE < VWAP -> BEARISH_TREND
    """
    if close > vwap:
        return "BULLISH_TREND"
    return "BEARISH_TREND"


async def load_market_context(symbol: str) -> MarketContext:
    """
    Loads market context.
    If fails -> Returns DEGRADED context.
    """
    df = await fetch_ohlcv(symbol, limit=100)
    
    if df.empty or len(df) < 50:
        logger.warning(f"Insufficient data for {symbol}")
        return MarketContext(
            price=0.0,
            open=0.0,
            atr=0.0,
            rsi=50.0,
            vwap=0.0,
            regime="UNKNOWN",
            data_quality="DEGRADED"
        )

    try:
        price = float(df["close"].iloc[-1])
        open_p = float(df["open"].iloc[-1]) # Need Open for K1
        atr = calculate_atr(df, period=Config.ATR_LEN)
        rsi = calculate_rsi(df, period=14)
        vwap = calculate_vwap(df)
        regime = determine_regime(price, vwap)
        
        if atr == 0 or vwap == 0:
             raise ValueError("Indicator calculation failed")

        return MarketContext(
            price=price,
            open=open_p,
            atr=atr,
            rsi=rsi,
            vwap=vwap,
            regime=regime,
            data_quality="OK"
        )
        
    except Exception as e:
        logger.error(f"Error processing context for {symbol}: {e}")
        return MarketContext(
            price=0.0,
            open=0.0,
            atr=0.0,
            rsi=50.0,
            vwap=0.0,
            regime="UNKNOWN",
            data_quality="DEGRADED"
        )
