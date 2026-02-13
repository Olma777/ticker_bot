"""
P-Score Engine.
Calculates numerical score for trade quality.
STRICT deterministic formula (P1-FIX-01/02).
"""

from typing import Literal, Optional, List

from bot.config import Config
from bot.decision_models import (
    MarketContext, 
    SentimentContext, 
    PScoreResult,
    LevelGradeResult,
    Regime
)

def score_level(sc: float) -> LevelGradeResult:
    """
    STRICT grading synced with Pine v3.7:
      STRONG: sc >= 3.0  -> +15
      MEDIUM: sc >= 1.0  ->  0
      WEAK:   sc <  1.0  -> -20
    NOTE: negative sc is always WEAK.
    """
    if sc >= 3.0:
        return LevelGradeResult("STRONG", +15, f"Level: STRONG (sc={sc:.1f}) +15")
    if sc >= 1.0:
        return LevelGradeResult("MEDIUM", 0, f"Level: MEDIUM (sc={sc:.1f}) +0")
    return LevelGradeResult("WEAK", -20, f"Level: WEAK (sc={sc:.1f}) -20")


def calculate_pscore(
    sc: float,
    regime: Regime,
    rsi: float,
    is_support_event: bool,
    data_quality_market: Literal["OK", "DEGRADED"],
    data_quality_sentiment: Literal["OK", "DEGRADED"],
    volume_high: Optional[bool] = None,  # P1 optional
) -> PScoreResult:
    """
    P1 STRICT spec:
      Base = 50
      + Level delta (from score_level)
      + Regime delta: EXPANSION +10, COMPRESSION -10, NEUTRAL 0
      + RSI context: +5 ONLY if counter-trend at level:
           Support event and RSI < 35  -> +5
           Resistance event and RSI > 65 -> +5
      + Data quality penalty: -15 if ANY of market/sentiment is DEGRADED
      Volume: optional (keep None in P1 unless implemented deterministically)
    """
    base = 50
    breakdown = [f"Base: +50"]

    lg = score_level(sc)
    score = base + lg.delta
    breakdown.append(lg.label)

    # Regime
    if regime == "EXPANSION":
        score += 10
        breakdown.append("Regime: EXPANSION +10")
    elif regime == "COMPRESSION":
        score -= 10
        breakdown.append("Regime: COMPRESSION -10")
    else:
        breakdown.append("Regime: NEUTRAL +0")

    # RSI Context (counter-trend only)
    rsi_delta = 0
    if is_support_event and rsi < 35:
        rsi_delta = +5
        breakdown.append(f"RSI: Counter-trend (RSI={rsi:.1f} < 35) +5")
    elif (not is_support_event) and rsi > 65:
        rsi_delta = +5
        breakdown.append(f"RSI: Counter-trend (RSI={rsi:.1f} > 65) +5")
    else:
        breakdown.append(f"RSI: Neutral (RSI={rsi:.1f}) +0")
    score += rsi_delta

    # Data quality
    if data_quality_market == "DEGRADED" or data_quality_sentiment == "DEGRADED":
        score -= 15
        breakdown.append("Data Quality: DEGRADED -15")
    else:
        breakdown.append("Data Quality: OK +0")

    # Volume (optional)
    if volume_high is True:
        score += 10
        breakdown.append("Volume: HIGH +10")
    elif volume_high is False:
        score -= 10
        breakdown.append("Volume: LOW -10")

    # Clamp to [0,100]
    score = max(0, min(100, int(round(score))))
    return PScoreResult(score=score, breakdown=breakdown)
