"""
Decision Engine Orchestrator (Phase 2).
Ties together Market Data, Kevlar, and P-Score to produce a deterministic decision.
"""

import logging
import asyncio

from bot.config import Config
from bot.decision_models import (
    DecisionResult, 
    KevlarResult,
    PScoreResult
)
from bot.market_data import get_market_context
from bot.sentiment import get_sentiment
from bot.kevlar import check_safety
from bot.pscore import calculate_score

logger = logging.getLogger(__name__)


async def process_signal(payload: dict) -> DecisionResult:
    """
    Process Webhook Payload through the Decision Engine pipeline.
    """
    symbol = payload.get('symbol')
    if not symbol:
        return _create_error_result("Missing Symbol")

    # 1. Fetch Context (Parallel)
    market_task = get_market_context(symbol)
    sentiment_task = get_sentiment(symbol)
    
    market, sentiment = await asyncio.gather(market_task, sentiment_task)
    
    # 2. Calculate P-Score
    p_score_res = calculate_score(payload, market, sentiment)
    
    # 3. Check Safety (Kevlar)
    kevlar_res = check_safety(payload, market, sentiment, p_score_res.score)
    
    # 4. Decision Logic
    decision = "WAIT"
    reason = "Initial"
    
    if not kevlar_res.passed:
        decision = "WAIT"
        reason = f"Blocked by Kevlar: {kevlar_res.blocked_by}"
    elif p_score_res.score < Config.P_SCORE_THRESHOLD:
        decision = "WAIT"
        reason = f"Low Score ({p_score_res.score} < {Config.P_SCORE_THRESHOLD})"
    else:
        decision = "TRADE"
        reason = "Valid Setup"

    # 5. Calculate Execution (Even if WAIT, for context)
    # Entry = Level
    level_price = float(payload.get('level', 0.0))
    entry = level_price
    
    # SL = Level +/- 1.5 * ATR (from Spec)
    atr = market.atr
    event_type = payload.get('event', '')
    
    sl_buffer = 1.5 * atr
    if "SUPPORT" in event_type:
        stop = level_price - sl_buffer
        # TP Targets (Standard 1:2 RRR approximation or Levels?)
        # Spec says "TP1/2/3".
        # Let's assume TP1 = Entry + 1R, TP2 = Entry + 2R etc?
        # Or use payload targets? P1 used payload but P2 spec says "Calculate Execution".
        # "Entry = Level, SL = Level +/- 1.5*ATR, TP1/2/3".
        # It doesn't specify TP formulas.
        # I'll stick to a reasonable R-multiple for now: 1R, 2R, 3R.
        risk = abs(entry - stop)
        tp1 = entry + risk
        tp2 = entry + (2 * risk) 
        tp3 = entry + (3 * risk)
    else:
        stop = level_price + sl_buffer
        risk = abs(stop - entry)
        tp1 = entry - risk
        tp2 = entry - (2 * risk)
        tp3 = entry - (3 * risk)

    return DecisionResult(
        decision=decision,
        symbol=symbol,
        level=level_price,
        p_score=p_score_res.score, # Pass Int
        kevlar=kevlar_res,
        entry=entry,
        stop=stop,
        tp_targets=[tp1, tp2, tp3],
        reason=reason,
        market_context=market,
        sentiment_context=sentiment
    )


def _create_error_result(msg: str) -> DecisionResult:
    return DecisionResult(
        decision="WAIT",
        symbol="UNKNOWN",
        level=0.0,
        p_score=0,
        kevlar=KevlarResult(False, "System Error"),
        entry=0.0, stop=0.0, tp_targets=[],
        reason=msg
    )
