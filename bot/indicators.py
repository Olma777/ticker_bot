"""
Technical indicators module (Math Only).
Refactored for Phase 2: Removed Business Logic.
"""

import logging
import pandas as pd
import numpy as np
from typing import Optional, tuple

from bot.config import TRADING

logger = logging.getLogger(__name__)


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate Average True Range."""
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()


def calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate Relative Strength Index."""
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def calculate_vwap_24h(df: pd.DataFrame) -> float:
    """Calculate 24h Volume Weighted Average Price."""
    if len(df) < 48:
        return float(df['close'].mean())
    last_24h = df.tail(48)
    vwap = (last_24h['close'] * last_24h['volume']).sum() / last_24h['volume'].sum()
    return float(vwap)


def calculate_global_regime(btc_df: Optional[pd.DataFrame]) -> tuple[str, str]:
    """
    Calculate global market regime based on BTC ROC (Rate of Change).
    Logic from Phase 1 (Approved for Phase 2).
    Returns: (regime, safety_label)
    Regime: "EXPANSION", "COMPRESSION", "NEUTRAL"
    """
    if btc_df is None or btc_df.empty or len(btc_df) < TRADING.z_win:
        return "NEUTRAL", "SAFE"
    
    # ROC 30 periods
    roc = btc_df['close'].pct_change(30)
    if roc.isna().all():
        return "NEUTRAL", "SAFE"
    
    mean = roc.rolling(window=TRADING.z_win).mean()
    std = roc.rolling(window=TRADING.z_win).std()
    
    if std.iloc[-1] == 0 or pd.isna(std.iloc[-1]):
        return "NEUTRAL", "SAFE"
    
    z_score = (roc - mean) / std
    current_z = z_score.iloc[-1]
    
    if pd.isna(current_z):
        return "NEUTRAL", "SAFE"
    
    if current_z > TRADING.z_thr:
        return "COMPRESSION", "RISKY"
    elif current_z < -TRADING.z_thr:
        return "EXPANSION", "SAFE"
    
    return "NEUTRAL", "SAFE"


def calculate_volatility_bands(current_price: float, atr: float) -> tuple[float, float]:
    """Calculate volatility bands based on ATR."""
    return current_price - (atr * 2.0), current_price + (atr * 2.0)
