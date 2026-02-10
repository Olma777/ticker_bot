"""
Data models for Decision Engine.
Pure dataclasses with no logic to ensure type safety across the pipeline.
Updated for P1-Final: Strict compliance + K1 Momentum support.
"""

from dataclasses import dataclass
from typing import Literal, List, Optional

# Constants
DecisionType = Literal["TRADE", "WAIT"]
SideType = Literal["LONG", "SHORT"]
DataQualityType = Literal["OK", "DEGRADED"]
LevelGrade = Literal["STRONG", "MEDIUM", "WEAK"]
Regime = Literal["EXPANSION", "NEUTRAL", "COMPRESSION"]
EntryMode = Literal["TOUCH_LIMIT", "CLOSE_CONFIRM"]

@dataclass(frozen=True)
class LevelGradeResult:
    """Strict level grading result (P1-FIX-01)."""
    grade: LevelGrade
    delta: int
    label: str

@dataclass
class MarketContext:
    """Market data snapshot."""
    price: float
    open: float   # Added for K1 Momentum
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

@dataclass(frozen=True)
class PScoreResult:
    """P-Score calculation result (P1-FIX-02)."""
    score: int
    breakdown: List[str]

@dataclass
class RiskContext:
    """Risk management calculations (P1-FIX-OrderCalc)."""
    entry_price: float
    stop_loss: float
    tp1: float
    tp2: float
    tp3: float
    stop_dist: float
    stop_dist_pct: float
    risk_amount: float     # $ Risk
    position_size: float   # In Asset (e.g. BTC)
    leverage: float        # Implied leverage based on capital
    rrr_tp2: float         # Risk:Reward to TP2
    fee_included: bool

@dataclass
class DecisionResult:
    """Final decision from the engine."""
    decision: DecisionType
    side: Optional[SideType]
    entry_mode: Optional[EntryMode]
    level_grade: Optional[LevelGradeResult]
    pscore: PScoreResult
    kevlar: KevlarResult
    risk: Optional[RiskContext]
    reason: str
    # Context Snapshots for Notifier
    market_context: Optional[MarketContext] = None
    sentiment_context: Optional[SentimentContext] = None
