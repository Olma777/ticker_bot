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
from bot.models.market_context import MarketContext as DTOContext
from bot.kevlar import check_safety_v2

from bot.logger import logger


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
        reason = f"Low Score ({p_score_res.score} is below {Config.P_SCORE_THRESHOLD})"
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

    result = DecisionResult(
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
    # LEGACY: logging.info(f"Decision made: {decision} for {symbol}")
    logger.info("decision_made", symbol=symbol, price=market.price if hasattr(market, "price") else None, latency_ms=None, tokens_used=None)
    return result


async def process_signal_v2(payload: dict, ctx: DTOContext) -> DecisionResult:
    symbol = payload.get('symbol') or ctx.symbol
    level_price = float(payload.get('level', 0.0))
    event_type = payload.get('event', '')
    base_score = 50
    regime_bonus = 10 if ctx.btc_regime == "bullish" else -10 if ctx.btc_regime == "bearish" else 0
    p_score = max(0, min(100, base_score + regime_bonus))
    kevlar_res = check_safety_v2(payload, ctx, p_score)
    decision = "TRADE" if kevlar_res.passed and p_score >= Config.P_SCORE_THRESHOLD else "WAIT"
    reason = "Valid Setup" if decision == "TRADE" else f"Blocked: {kevlar_res.blocked_by or 'Low Score'}"
    order_plan = None
    if decision == "TRADE":
        side = "LONG" if "SUPPORT" in event_type else "SHORT"
        zone_half = float(payload.get('zone_half', 0.0)) or (ctx.atr * Config.ZONE_WIDTH_MULT)
        order_plan = build_order_plan(
            side=side,
            level=level_price,
            zone_half=zone_half,
            atr=ctx.atr,
            capital=Config.DEFAULT_CAPITAL,
            risk_pct=Config.DEFAULT_RISK_PCT,
            lot_step=None
        )
        if order_plan.reason_blocked:
            decision = "WAIT"
            reason = f"Order Calc Blocked: {order_plan.reason_blocked}"
    if order_plan and decision == "TRADE":
        entry = order_plan.entry
        stop = order_plan.stop_loss
        tp_targets = [order_plan.tp1, order_plan.tp2, order_plan.tp3]
    else:
        entry = 0.0
        stop = 0.0
        tp_targets = []
    result = DecisionResult(
        decision=decision,
        symbol=symbol,
        level=level_price,
        p_score=p_score,
        kevlar=kevlar_res,
        entry=entry,
        stop_loss=stop,
        tp_targets=tp_targets,
        reason=reason,
        market_context=None,
        sentiment_context=None
    )
    logger.info("decision_made", symbol=symbol, price=None, latency_ms=None, tokens_used=None)
    return result

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
