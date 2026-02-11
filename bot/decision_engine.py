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
from bot.order_calc import build_order_plan

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

    # 5. Calculate Execution (Single Source of Truth)
    order_plan = None
    level_price = float(payload.get('level', 0.0))
    event_type = payload.get('event', '')

    if decision == "TRADE":
        # Determine side from event type
        side = "LONG" if "SUPPORT" in event_type else "SHORT"
        
        # Get zone_half from payload (critical for SL placement)
        zone_half = float(payload.get('zone_half', 0.0))
        # Fallback: if zone_half is 0, estimate from ATR and default multiplier
        if zone_half == 0:
            zone_half = market.atr * Config.ZONE_WIDTH_MULT
        
        # Call SINGLE SOURCE OF TRUTH
        order_plan = build_order_plan(
            side=side,
            level=level_price,
            zone_half=zone_half,
            atr=market.atr,
            capital=1000.0,  # Default, should come from config
            risk_pct=1.0,    # Default
            lot_step=None    # Optional
        )
        
        # Check if order plan is valid (not blocked by RRR etc.)
        if order_plan.reason_blocked:
            decision = "WAIT"
            reason = f"Order Calc Blocked: {order_plan.reason_blocked}"
    
    # Build result - use order_plan if exists, else zero values
    if order_plan and decision == "TRADE":
        entry = order_plan.entry
        stop = order_plan.stop_loss
        tp_targets = [order_plan.tp1, order_plan.tp2, order_plan.tp3]
    else:
        entry = 0.0
        stop = 0.0
        tp_targets = []

    return DecisionResult(
        decision=decision,
        symbol=symbol,
        level=level_price,
        p_score=p_score_res.score,
        kevlar=kevlar_res,
        entry=entry,
        stop_loss=stop,
        tp_targets=tp_targets,
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
