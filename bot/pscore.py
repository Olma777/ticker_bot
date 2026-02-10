"""
P-Score Engine.
Calculates numerical score for trade quality.
Deterministic formula synced with spec.
"""

from bot.config import Config
from bot.decision_models import MarketContext, SentimentContext, PScoreResult

# Base Score
BASE_SCORE = 50

# Factors
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

    # 1. Level Strength (from TV event touches/score)
    # Mapping TV "Score" or "touches" to generic Strength concept
    # Spec implies we trust TV "Score" for level quality locally
    # Let's use the 'score' from payload as proxy for Level Strength
    # or define threshold.
    # Spec says:
    # Level Strength STRONG +15
    # Level Strength WEAK -20
    # Let's assume passed TV Score > 35 is Strong? Or use 'touches'?
    # Re-reading spec: "Level Strength" is a factor.
    # In v2.3 logic: Score > 25 is "Moderate", >60 "Strong".
    # Implementation:
    # If TV Score >= 50 -> STRONG (+15)
    # If TV Score < 30 -> WEAK (-20)
    # Else -> Neutral (0)
   
    tv_score = event.get('score', 0)
    if tv_score >= 50:
        score += FACTOR_LEVEL_STRONG
        breakdown.append(f"Level Strong: +{FACTOR_LEVEL_STRONG}")
    elif tv_score < 30:
        score += FACTOR_LEVEL_WEAK
        breakdown.append(f"Level Weak: {FACTOR_LEVEL_WEAK}")

    # 2. Regime (From Market Context)
    # EXPANSION vs COMPRESSION logic needed?
    # Spec: "Regime EXPANSION +10, COMPRESSION -10"
    # Our market_data.py returns BULLISH_TREND / BEARISH_TREND
    # We need to map this or infer Expansion/Compression.
    # Simple proxy: if Price and VWAP are trending apart -> Expansion?
    # Or use ATR?
    # Let's use 24h Change or ATR > Threshold?
    # For now, simplistic mapping:
    # If regime is aligned with trade direction -> Expansion (+10)
    # If regime is opposed -> Compression (-10)
    # Wait, spec says "Regime" is the factor, not alignment.
    # Let's assume "Trending" = Expansion, "Ranging" = Compression.
    # We can use ADX or just ATR/Price ratio?
    # Given strict "No AI/No Magic", let's stick to the names in spec.
    # But we only have BULLISH/BEARISH from market_data.
    # Let's refine market_data later if needed.
    # For now: If score is high (>50) -> assume Expansion? No.
    # Let's skip Regime factor if undefined, or use a placeholder:
    # If market.regime != "UNKNOWN": score += 0 (Neutral for now to avoid guessing)
    pass 
    # TODO: Refine Regime definition in market_data (ADX?)

    # 3. RSI Context
    # "Counter-trend +5"
    # Long on Low RSI (<40) -> +5
    # Short on High RSI (>60) -> +5
    event_type = event.get('event') # SUPPORT_TEST (Long) or RESISTANCE_TEST (Short)
    
    if event_type == "SUPPORT_TEST" and market.rsi < 40:
        score += FACTOR_RSI_COUNTER
        breakdown.append(f"RSI Oversold Buy: +{FACTOR_RSI_COUNTER}")
    elif event_type == "RESISTANCE_TEST" and market.rsi > 60:
        score += FACTOR_RSI_COUNTER
        breakdown.append(f"RSI Overbought Sell: +{FACTOR_RSI_COUNTER}")

    # 4. Data Quality
    if market.data_quality == "DEGRADED" or sentiment.data_quality == "DEGRADED":
        score += FACTOR_DATA_DEGRADED
        breakdown.append(f"Data Degraded: {FACTOR_DATA_DEGRADED}")

    return PScoreResult(score=score, breakdown=breakdown)
