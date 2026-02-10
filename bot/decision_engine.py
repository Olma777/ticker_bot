"""
Decision Engine Orchestrator.
Pipelines market data, sentiment, P-Score, and Kevlar to produce a final decision.
"""

import logging
import asyncio

from bot.decision_models import (
    DecisionResult, 
    MarketContext, 
    SentimentContext, 
    PScoreResult,
    KevlarResult
)
from bot.market_data import load_market_context
from bot.sentiment import load_sentiment
from bot.pscore import calculate_pscore
from bot.kevlar import apply_kevlar
from bot.config import Config

logger = logging.getLogger("DecisionEngine-Orchestrator")


async def make_decision(event: dict) -> DecisionResult:
    """
    Execute decision pipeline:
    1. Load Market Context
    2. Load Sentiment Context
    3. Calculate P-Score
    4. Apply Kevlar
    5. Final Decision
    """
    symbol = event.get('symbol')
    if not symbol:
        return _create_error_result("Missing Symbol")

    # 1. Load Data (Parallel)
    # market_task = load_market_context(symbol)
    # sentiment_task = load_sentiment(symbol)
    # market, sentiment = await asyncio.gather(market_task, sentiment_task)
    
    # Sequential for debug simplicity first, or parallel for speed?
    # Spec says "Deterministic", speed is good.
    market = await load_market_context(symbol)
    sentiment = await load_sentiment(symbol)

    # 2. Score
    pscore = calculate_pscore(event, market, sentiment)

    # 3. Kevlar
    kevlar = apply_kevlar(event, market, sentiment, pscore)

    # 4. Final Logic
    # Default: WAIT
    decision = "WAIT"
    side = None
    reason = "Initial"

    # Determine potential side
    event_type = event.get('event')
    if event_type == "SUPPORT_TEST":
        potential_side = "LONG"
    elif event_type == "RESISTANCE_TEST":
        potential_side = "SHORT"
    else:
        potential_side = None

    # Evaluation
    if not kevlar.passed:
        decision = "WAIT"
        reason = f"Kevlar Block: {kevlar.blocked_by}"
    elif pscore.score < Config.P_SCORE_THRESHOLD:
        decision = "WAIT"
        reason = f"P-Score ({pscore.score}) < Threshold ({Config.P_SCORE_THRESHOLD})"
    elif potential_side:
        decision = "TRADE"
        side = potential_side
        reason = f"Systems GO (Score {pscore.score})"
    else:
        decision = "WAIT"
        reason = "Unknown Event Type"

    result = DecisionResult(
        decision=decision,
        side=side,
        pscore=pscore,
        kevlar=kevlar,
        reason=reason
    )
    
    logger.info(f"Decision for {symbol}: {decision} ({reason})")
    return result


def _create_error_result(msg: str) -> DecisionResult:
    return DecisionResult(
        decision="WAIT",
        side=None,
        pscore=PScoreResult(0, ["Error"]),
        kevlar=KevlarResult(False, "System Error"),
        reason=msg
    )
