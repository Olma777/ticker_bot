"""
Decision Engine Orchestrator.
Pipelines market data, sentiment, P-Score, and Kevlar to produce a final decision.
Updated for P1-FIX: Strict P-Score signature, Entry Mode, Risk Calc.
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

logger = logging.getLogger("DecisionEngine-Orchestrator")


async def make_decision(event: dict) -> DecisionResult:
    """
    Execute strict decision pipeline (P1-FIX-05):
    1. MarketContext
    2. Sentiment
    3. P-Score (Strict)
    4. Kevlar
    5. Decision + Risk
    """
    symbol = event.get('symbol')
    if not symbol:
        return _create_error_result("Missing Symbol")

    # 1. Load Data
    market = await load_market_context(symbol)
    sentiment = await load_sentiment(symbol)

    # 2. Prepare P-Score Inputs
    regime: Regime = "NEUTRAL"
    if market.regime in ["BULLISH_TREND", "BEARISH_TREND"]:
        regime = "EXPANSION"
    
    event_type = event.get('event')
    is_support = (event_type == "SUPPORT_TEST")
    sc = float(event.get('score', 0))

    # 3. Calculate P-Score (Strict)
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

    # 5. Final Logic
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

    if not kevlar.passed:
        decision = "WAIT"
        reason = f"Kevlar Block: {kevlar.blocked_by}"
        
    elif pscore.score < Config.P_SCORE_THRESHOLD:
        decision = "WAIT"
        reason = f"P-SCORE below threshold ({Config.P_SCORE_THRESHOLD})"
        
    elif potential_side:
        decision = "TRADE"
        side = potential_side
        reason = f"Refined Logic Pass (Score {pscore.score})"
        
        current_price = market.price
        atr = market.atr
        level_price = event.get('level', current_price)
        
        stop_mult = 1.5
        stop_dist = atr * stop_mult
        
        if side == "LONG":
            stop_loss = level_price - stop_dist
            if stop_loss >= current_price: 
                 stop_loss = current_price - stop_dist
        else:
            stop_loss = level_price + stop_dist
            if stop_loss <= current_price:
                 stop_loss = current_price + stop_dist
                
        capital = getattr(Config, 'DEFAULT_CAPITAL', 1000.0)
        risk_pct = getattr(Config, 'DEFAULT_RISK_PCT', 1.0) / 100.0
        risk_amount = capital * risk_pct
        
        dist_price = abs(current_price - stop_loss)
        if dist_price == 0: dist_price = atr 

        position_size = risk_amount / dist_price
        
        notional = position_size * current_price
        leverage = notional / capital
        
        risk_ctx = RiskContext(
            entry_price=current_price,
            stop_loss=stop_loss,
            stop_dist=dist_price,
            stop_dist_pct=(dist_price / current_price) * 100,
            risk_amount=risk_amount,
            position_size=position_size,
            leverage=leverage,
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
        market_context=market,      # Added
        sentiment_context=sentiment # Added
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
