"""
P-Score Engine (Phase 2).
Calculates deterministic probability score.
Formula v2.7 (Spec v2.0).
"""

from bot.decision_models import MarketContext, SentimentContext, PScoreResult

def calculate_score(
    event: dict,
    market: MarketContext,
    sentiment: SentimentContext
) -> PScoreResult:
    """
    Calculate P-Score (0-100).
    """
    score = 50
    breakdown = ["Base: 50"]
    
    # 1. Level Strength
    # Strong (Sc >= 1): +15
    # Weak (Sc < 0): -20
    # Ghost (Sc < -10): Automatic Wait (Handled via low score)
    sc = float(event.get('score', 0))
    
    if sc < -10:
        score = 0
        breakdown.append(f"Ghost Level (Sc {sc}): FORCE WAIT")
        return PScoreResult(0, breakdown) # Kill immediately
        
    if sc >= 1.0:
        score += 15
        breakdown.append(f"Level Strong ({sc}): +15")
    elif sc < 0.0:
        score -= 20
        breakdown.append(f"Level Weak ({sc}): -20")
    else:
        breakdown.append(f"Level Moderate ({sc}): +0")

    # 2. Regime (BTC)
    # Expansion: +10
    # Neutral/Compression: -10
    if market.regime == "EXPANSION":
        score += 10
        breakdown.append("Regime (EXP): +10")
    else:
        score -= 10
        breakdown.append(f"Regime ({market.regime}): -10")

    # 3. Volume/Sentiment
    # High (Hot): +10
    # Low (Cold): -10
    if sentiment.is_hot:
        score += 10
        breakdown.append("Sentiment (HOT): +10")
    else:
        score -= 10
        breakdown.append("Sentiment (COLD): -10")

    # 4. RSI Context
    # Counter-trend extreme: +5
    # Support & RSI < 35 -> +5
    # Resistance & RSI > 65 -> +5
    event_type = event.get('event', '')
    is_support = "SUPPORT" in event_type
    
    rsi_bonus = 0
    if is_support and market.rsi < 35:
        rsi_bonus = 5
        breakdown.append("RSI (Oversold): +5")
    elif not is_support and market.rsi > 65:
        rsi_bonus = 5
        breakdown.append("RSI (Overbought): +5")
    
    score += rsi_bonus

    # Clamp 0-100
    if score < 0: score = 0
    if score > 100: score = 100
    
    return PScoreResult(score, breakdown)
