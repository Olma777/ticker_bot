"""
Data models for Decision Engine.
Pure dataclasses with no logic to ensure type safety across the pipeline.
"""

from dataclasses import dataclass
from typing import Literal, List, Optional

# Constants
DecisionType = Literal["TRADE", "WAIT"]
SideType = Literal["LONG", "SHORT"]
DataQualityType = Literal["OK", "DEGRADED"]

@dataclass
class MarketContext:
    """Market data snapshot."""
    price: float
    atr: float
    rsi: float
    vwap: float
    regime: str
    data_quality: DataQualityType


@dataclass
class SentimentContext:
    """Crowd positioning data."""
    funding: Optional[float]
    open_interest: Optional[float]
    data_quality: DataQualityType


@dataclass
class KevlarResult:
    """Result of Kevlar filters application."""
    passed: bool
    blocked_by: Optional[str]


@dataclass
class PScoreResult:
    """P-Score calculation result."""
    score: int
    breakdown: List[str]


@dataclass
class RiskContext:
    """Risk management calculations (P1-FIX-04)."""
    entry_price: float
    stop_loss: float
    stop_dist: float
    stop_dist_pct: float
    risk_amount: float     # $ Risk
    position_size: float   # In Asset (e.g. BTC)
    leverage: float        # Implied leverage based on capital
    fee_included: bool


@dataclass
class DecisionResult:
    """Final decision from the engine."""
    decision: DecisionType
    side: Optional[SideType]
    pscore: PScoreResult
    kevlar: KevlarResult
    risk: Optional[RiskContext]  # Added for FIX-04
    reason: str
