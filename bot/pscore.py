"""
P-Score Engine.
Calculates numerical score for trade quality.
Deterministic formula synced with LOCKED Specification.
"""

from bot.config import Config
from bot.decision_models import MarketContext, SentimentContext, PScoreResult, LevelGradeResult

# Base Score
BASE_SCORE = 50

# --- LOCKED SPEC (P1 Final) ---
# Factor        Condition       Delta
# Level         STRONG          +15
# Level         WEAK (-ve sc)   -20
# Regime        EXPANSION       +10
# Regime        COMPRESSION     -10
# RSI           Contra(Supp<35/Res>65) +5
# Data Quality  DEGRADED        -15

def score_level(sc: float) -> LevelGradeResult:
    """
    Classify level strength based on Score (sc).
    LOCKED SPEC:
      sc >= 3.0        -> STRONG (Green)
      1.0 <= sc < 3.0  -> MEDIUM (Yellow)
      sc < 1.0         -> WEAK (Red)
    """
    if sc >= 3.0:
        return LevelGradeResult("STRONG", +15, "🟢")
    elif sc >= 1.0:
        return LevelGradeResult("MEDIUM", +0, "🟡")
    else:
        # Includes all negative scores
        return LevelGradeResult("WEAK", -20, "🔴")


def calculate_pscore(
    sc: float,
    regime: str,  # EXPANSION / NEUTRAL / COMPRESSION
    rsi: float,
    is_support_event: bool,
    data_quality_market: str,
    data_quality_sentiment: str,
    volume_high: bool = None
) -> PScoreResult:
    """
    Calculate deterministic P-Score.
    """
    score = BASE_SCORE
    breakdown = []
    
    # 1. Level Factor (LOCKED)
    lvl_res = score_level(sc)
    score += lvl_res.delta
    breakdown.append(f"Base: {BASE_SCORE}")
    breakdown.append(f"Level ({lvl_res.grade}): {lvl_res.delta:+}")

    # 2. Regime Factor (LOCKED)
    if regime == "EXPANSION":
        score += 10
        breakdown.append("Regime (EXP): +10")
    elif regime == "COMPRESSION":
        score -= 10
        breakdown.append("Regime (CMP): -10")
    else:
        breakdown.append("Regime (NEU): +0")

    # 3. RSI Context (LOCKED)
    # Support & RSI < 35 -> +5
    # Resistance & RSI > 65 -> +5
    rsi_bonus = 0
    if is_support_event and rsi < 35:
        rsi_bonus = 5
        breakdown.append("RSI (Oversold): +5")
    elif not is_support_event and rsi > 65:
        rsi_bonus = 5
        breakdown.append("RSI (Overbought): +5")
    
    score += rsi_bonus

    # 4. Data Quality (LOCKED)
    if data_quality_market == "DEGRADED" or data_quality_sentiment == "DEGRADED":
        score -= 15
        breakdown.append("Data (Degraded): -15")

    # Final logic
    if score < 0: score = 0
    if score > 100: score = 100
    
    return PScoreResult(score, breakdown)
