"""
Data models for Decision Engine (Phase 2).
Pure dataclasses with no logic to ensure type safety across the pipeline.
Updated to include Candle Data for Kevlar Momentum checks.
"""

from dataclasses import dataclass
from typing import Literal, List, Optional

DecisionType = Literal["TRADE", "WAIT"]
DataQualityType = Literal["OK", "DEGRADED"]

@dataclass
class MarketContext:
    price: float
    atr: float
    rsi: float
    vwap: float
    regime: str  # "EXPANSION", "COMPRESSION", "NEUTRAL"
    # Candle Data for Kevlar
    candle_open: float
    candle_high: float
    candle_low: float
    candle_close: float
    data_quality: DataQualityType

@dataclass
class SentimentContext:
    funding: float
    open_interest: float
    is_hot: bool  # True if OI is significantly high
    data_quality: DataQualityType

@dataclass
class KevlarResult:
    passed: bool
    blocked_by: Optional[str]  # e.g., "Momentum Instability"

@dataclass
class PScoreResult:
    """Detailed score result for debugging/logging."""
    score: int
    breakdown: List[str]

@dataclass
class DecisionResult:
    decision: DecisionType
    symbol: str
    level: float
    p_score: int
    kevlar: KevlarResult
    entry: float
    stop_loss: float            # CHANGED: was 'stop'
    tp_targets: List[float]
    reason: str
    # Context Snapshots for Notifier
    market_context: Optional[MarketContext] = None
    sentiment_context: Optional[SentimentContext] = None
