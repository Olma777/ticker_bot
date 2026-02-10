"""
Decision Engine Orchestrator.
Pipelines market data, sentiment, P-Score, and Kevlar to produce a final decision.
Updated for P1-OrderCalc: Using strict deterministic order module.
"""

import logging

from bot.decision_models import (
    DecisionResult, 
    PScoreResult,
    KevlarResult,
    RiskContext,
    LevelGradeResult,
    EntryMode,
    Regime
)
from bot.market_data import load_market_context
from bot.sentiment import load_sentiment
from bot.pscore import calculate_pscore, score_level
from bot.kevlar import apply_kevlar
from bot.config import Config
from bot.order_calc import build_order_plan

logger = logging.getLogger("DecisionEngine-Orchestrator")


async def make_decision(event: dict) -> DecisionResult:
    """
    Execute strict decision pipeline (P1-OrderCalc):
    1. MarketContext
    2. Sentiment
    3. P-Score 
    4. Kevlar
    5. Order Calculation (Strict Module)
    """
    symbol = event.get('symbol')
    if not symbol:
        return _create_error_result("Missing Symbol")

    # 1. Load Data
    market = await load_market_context(symbol)
    sentiment = await load_sentiment(symbol)

    # 2. P-Score Inputs
    regime: Regime = "NEUTRAL"
    if market.regime in ["BULLISH_TREND", "BEARISH_TREND"]:
        regime = "EXPANSION"
    
    event_type = event.get('event')
    is_support = (event_type == "SUPPORT_TEST")
    sc = float(event.get('score', 0))

    # 3. Calculate P-Score
    pscore = calculate_pscore(
        sc=sc,
        regime=regime,
        rsi=market.rsi,
        is_support_event=is_support,
        data_quality_market=market.data_quality,
        data_quality_sentiment=sentiment.data_quality,
        volume_high=None 
    )

    level_grade = score_level(sc)

    # 4. Kevlar
    kevlar = apply_kevlar(event, market, sentiment, pscore)

    # 5. Final Logic & Order Calc
    decision = "WAIT"
    side = None
    reason = "Initial"
    risk_ctx = None
    entry_mode: EntryMode = "TOUCH_LIMIT" 

    try:
        alert_type = event.get('alertType', 'Touch')
        if alert_type == 'Close':
            entry_mode = "CLOSE_CONFIRM"
        else:
            entry_mode = "TOUCH_LIMIT"
    except:
        entry_mode = "TOUCH_LIMIT"

    if is_support:
        potential_side = "LONG"
    elif event_type == "RESISTANCE_TEST":
        potential_side = "SHORT"
    else:
        potential_side = None

    # Logic Pipeline
    if not kevlar.passed:
        decision = "WAIT"
        reason = f"Kevlar Block: {kevlar.blocked_by}"
        
    elif pscore.score < Config.P_SCORE_THRESHOLD:
        decision = "WAIT"
        reason = f"P-SCORE below threshold ({Config.P_SCORE_THRESHOLD})"
        
    elif potential_side:
        # Candidate for Trade -> Calculate Orders via Strict Module
        side = potential_side
        
        # Extract Inputs
        level_price = float(event.get('level', market.price))
        zone_half = float(event.get('zone_half', 0.0))
        atr = market.atr
        capital = getattr(Config, 'DEFAULT_CAPITAL', 1000.0)
        risk_pct = getattr(Config, 'DEFAULT_RISK_PCT', 1.0)
        
        # CALL DETERMINISTIC MODULE
        plan = build_order_plan(
            side=side,
            level=level_price,
            zone_half=zone_half,
            atr=atr,
            capital=capital,
            risk_pct=risk_pct
        )
        
        if plan.reason_blocked:
            decision = "WAIT"
            reason = f"{plan.reason_blocked}"
        else:
            decision = "TRADE"
            reason = f"Systems GO (Score {pscore.score})"
            
            # Populate RiskContext from Plan
            # Calculate leverage manually as it's computed in order_calc implicitly via size but not returned directly
            leverage = (plan.size_units * plan.entry) / capital if capital > 0 else 0
            stop_pct = (plan.stop_dist / plan.entry) * 100 if plan.entry > 0 else 0

            risk_ctx = RiskContext(
                entry_price=plan.entry,
                stop_loss=plan.sl,
                tp1=plan.tp1,
                tp2=plan.tp2,
                tp3=plan.tp3,
                stop_dist=plan.stop_dist,
                stop_dist_pct=stop_pct,
                risk_amount=plan.risk_amount,
                position_size=plan.size_units,
                leverage=leverage,
                rrr_tp2=plan.rrr_tp2,
                fee_included=False
            )
            
    else:
        decision = "WAIT"
        reason = "Unknown Event Type"

    result = DecisionResult(
        decision=decision,
        side=side,
        entry_mode=entry_mode,
        level_grade=level_grade,
        pscore=pscore,
        kevlar=kevlar,
        risk=risk_ctx,
        reason=reason,
        market_context=market,
        sentiment_context=sentiment
    )
    
    logger.info(f"Decision for {symbol}: {decision} ({reason})")
    return result


def _create_error_result(msg: str) -> DecisionResult:
    from bot.pscore import PScoreResult
    return DecisionResult(
        decision="WAIT",
        side=None,
        entry_mode=None,
        level_grade=None,
        pscore=PScoreResult(0, ["Error"]),
        kevlar=KevlarResult(False, "System Error"),
        risk=None,
        reason=msg,
        market_context=None,
        sentiment_context=None
    )
