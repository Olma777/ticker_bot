"""
Decision Engine Orchestrator.
Pipelines market data, sentiment, P-Score, and Kevlar to produce a final decision.
Updated for P1-FIX-OrderCalc: Strict Order Math & RRR Validation.
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
from bot.config import Config, TRADING

logger = logging.getLogger("DecisionEngine-Orchestrator")


async def make_decision(event: dict) -> DecisionResult:
    """
    Execute strict decision pipeline (P1-FIX-OrderCalc):
    1. MarketContext
    2. Sentiment
    3. P-Score 
    4. Kevlar
    5. Order Calculation (Strict Rules)
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
        # Candidate for Trade -> Calculate Orders first to validate RRR
        side = potential_side
        
        # --- P1-FIX-OrderCalc STRICT MATH ---
        current_price = market.price
        atr = market.atr
        level_price = event.get('level', current_price)
        zone_half = event.get('zone_half', 0.0)
        
        # 1. Entry (Touch P1 = Level)
        entry_price = level_price
        
        # 2. SL (Zone Boundary ± Buffer)
        sl_buffer = TRADING.sl_buffer_atr * atr
        
        if side == "LONG":
            zone_bot = level_price - zone_half
            stop_loss = zone_bot - sl_buffer
            
            # 3. TP Targets
            tp1 = entry_price + (TRADING.tp1_atr * atr)
            tp2 = entry_price + (TRADING.tp2_atr * atr)
            tp3 = entry_price + (TRADING.tp3_atr * atr)
        else:
            zone_top = level_price + zone_half
            stop_loss = zone_top + sl_buffer
            
            # 3. TP Targets
            tp1 = entry_price - (TRADING.tp1_atr * atr)
            tp2 = entry_price - (TRADING.tp2_atr * atr)
            tp3 = entry_price - (TRADING.tp3_atr * atr)

        # 4. Size & Risk
        capital = getattr(Config, 'DEFAULT_CAPITAL', 1000.0)
        risk_pct = getattr(Config, 'DEFAULT_RISK_PCT', 1.0) / 100.0
        risk_amount = capital * risk_pct
        
        stop_dist = abs(entry_price - stop_loss)
        if stop_dist == 0: stop_dist = atr # Prevent div/0

        position_size = risk_amount / stop_dist
        
        # 5. RRR to TP2
        reward_dist = abs(tp2 - entry_price)
        rrr_tp2 = reward_dist / stop_dist
        
        # Leverage
        notional = position_size * entry_price
        leverage = notional / capital

        # Validation Check (P1-FIX-04)
        if rrr_tp2 < TRADING.min_rrr:
            decision = "WAIT"
            reason = f"RRR {rrr_tp2:.2f} < Min {TRADING.min_rrr}"
        else:
            decision = "TRADE"
            reason = f"Systems GO (Score {pscore.score})"
            
            risk_ctx = RiskContext(
                entry_price=entry_price,
                stop_loss=stop_loss,
                tp1=tp1,
                tp2=tp2,
                tp3=tp3,
                stop_dist=stop_dist,
                stop_dist_pct=(stop_dist / entry_price) * 100,
                risk_amount=risk_amount,
                position_size=position_size,
                leverage=leverage,
                rrr_tp2=rrr_tp2,
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
