"""
P-Score Engine.
Calculates numerical score for trade quality.
Deterministic formula synced with spec and P1-FIX-01/02.
"""

from bot.config import Config
from bot.decision_models import MarketContext, SentimentContext, PScoreResult

# Base Score
BASE_SCORE = 50

# Factors (Synced with P1-FIX-02)
FACTOR_LEVEL_STRONG = 15
FACTOR_LEVEL_WEAK = -20
FACTOR_REGIME_EXPANSION = 10
FACTOR_REGIME_COMPRESSION = -10
FACTOR_RSI_COUNTER = 5
FACTOR_DATA_DEGRADED = -15


def calculate_pscore(
    event: dict,
    market: MarketContext,
    sentiment: SentimentContext
) -> PScoreResult:
    """
    Calculate P-Score based on factors.
    Returns Score and Breakdown list.
    """
    score = BASE_SCORE
    breakdown = [f"Base: {BASE_SCORE}"]

    # --- 1. Level Strength (P1-FIX-01: Grade Sync) ---
    # Strong >= 3 -> +15
    # Medium >= 1 -> 0
    # Weak < 1 -> -20 (includes negative)
    
    # We expect 'score' in payload to represent the Pine 'sc' value
    # (or mapped equivalent if payload differs).
    # Assuming event['score'] IS the 'sc' value from Pine.
    
    level_sc = event.get('score', 0)
    
    if level_sc >= 3:
        score += FACTOR_LEVEL_STRONG
        breakdown.append(f"Level Strong (sc={level_sc}): +{FACTOR_LEVEL_STRONG}")
    elif level_sc < 1:
        score += FACTOR_LEVEL_WEAK
        breakdown.append(f"Level Weak (sc={level_sc}): {FACTOR_LEVEL_WEAK}")
    else:
        # Medium (1 <= sc < 3) -> Neutral
        breakdown.append(f"Level Medium (sc={level_sc}): +0")

    # --- 2. Regime (From Market Context) ---
    # TODO: Implement Regime Mapping (Expansion/Compression)
    # Current placeholder: Neutral
    pass

    # --- 3. RSI Context ---
    # "Counter-trend +5"
    event_type = event.get('event') 
    
    if event_type == "SUPPORT_TEST" and market.rsi < 40:
        score += FACTOR_RSI_COUNTER
        breakdown.append(f"RSI Oversold Buy: +{FACTOR_RSI_COUNTER}")
    elif event_type == "RESISTANCE_TEST" and market.rsi > 60:
        score += FACTOR_RSI_COUNTER
        breakdown.append(f"RSI Overbought Sell: +{FACTOR_RSI_COUNTER}")

    # --- 4. Data Quality (P1-FIX-02) ---
    if market.data_quality == "DEGRADED" or sentiment.data_quality == "DEGRADED":
        score += FACTOR_DATA_DEGRADED
        breakdown.append(f"Data Degraded: {FACTOR_DATA_DEGRADED}")

    return PScoreResult(score=score, breakdown=breakdown)
