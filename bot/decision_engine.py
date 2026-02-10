"""
Decision Engine Orchestrator.
Pipelines market data, sentiment, P-Score, and Kevlar to produce a final decision.
Updated for P1-FIX: Risk Calculation and Entry Mode logic.
"""

import logging

from bot.decision_models import (
    DecisionResult, 
    PScoreResult,
    KevlarResult,
    RiskContext
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
    5. Final Decision (Trade/Wait) with Risk Calculations
    """
    symbol = event.get('symbol')
    if not symbol:
        return _create_error_result("Missing Symbol")

    # 1. Load Data
    market = await load_market_context(symbol)
    sentiment = await load_sentiment(symbol)

    # 2. Score (P1-FIX-01/02)
    pscore = calculate_pscore(event, market, sentiment)

    # 3. Kevlar
    kevlar = apply_kevlar(event, market, sentiment, pscore)

    # 4. Final Logic
    decision = "WAIT"
    side = None
    reason = "Initial"
    risk_ctx = None

    # Determine potential side from Event Type
    # P1-FIX-05: Entry Mode Logic
    # alertType could be 'Touch' or 'Close'
    # 'Touch' -> Immediate
    # 'Close' -> Candle Close
    # For now, we process both.
    event_type = event.get('event')
    if event_type == "SUPPORT_TEST":
        potential_side = "LONG"
    elif event_type == "RESISTANCE_TEST":
        potential_side = "SHORT"
    else:
        potential_side = None

    # Evaluation
    # P1-FIX-03: Strict Kevlar Enforcement
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
        
        # P1-FIX-04: Risk Calculation
        current_price = market.price
        atr = market.atr
        level_price = event.get('level', current_price)
        
        # Determine Stop Price
        # Logic: Stop = Level ± (mult * ATR)
        # Using Config.ZONE_WIDTH_MULT for zone width proxy? 
        # Or standard stop distance?
        # Pine typically uses `stopDist = atr * mult`. 
        # Let's assume Stop Distance is roughly 1.5-2 ATR if not specified.
        # Let's use 2.0 ATR for robust stops. Or configure in Config.
        # But wait, config has `ZONE_WIDTH_MULT`.
        # Let's define `STOP_ATR_MULT = 1.0` if not in config, or use existing if any.
        # Using 1.0 * ATR for tight stop relative to level?
        # Spec P1-FIX-04: "Transparency... Print StopDist".
        # Let's implement generic 2 ATR stop for safety.
        # Or better: Stop at invalidation of level width?
        # Use 1.0 ATR from level.
        stop_mult = 1.5
        stop_dist = atr * stop_mult
        
        if side == "LONG":
            stop_loss = level_price - stop_dist
            if stop_loss >= current_price: # Safety if price dipped below
                stop_loss = current_price - stop_dist
        else:
            stop_loss = level_price + stop_dist
            if stop_loss <= current_price:
                stop_loss = current_price + stop_dist
                
        # Calculate Risk $
        # Risk = Capital * RiskPct
        # Size = Risk$ / DistPerUnit
        capital = getattr(Config, 'DEFAULT_CAPITAL', 1000.0)
        risk_pct = getattr(Config, 'DEFAULT_RISK_PCT', 1.0) / 100.0
        risk_amount = capital * risk_pct
        
        dist_price = abs(current_price - stop_loss)
        if dist_price == 0: dist_price = atr # Prevent div/0

        position_size = risk_amount / dist_price
        
        # Leverage = (PositionSize * Price) / Capital
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
            fee_included=False # Explicit P1-FIX-04
        )

    else:
        decision = "WAIT"
        reason = "Unknown Event Type"

    result = DecisionResult(
        decision=decision,
        side=side,
        pscore=pscore,
        kevlar=kevlar,
        risk=risk_ctx,
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
        risk=None,
        reason=msg
    )
