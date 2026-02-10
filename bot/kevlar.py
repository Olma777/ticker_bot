"""
Kevlar Core (Phase 2).
Strict filters to block dangerous trades.
"""

from typing import Optional
from bot.decision_models import (
    MarketContext, 
    SentimentContext, 
    KevlarResult
)

def check_safety(
    event: dict,
    market: MarketContext,
    sentiment: SentimentContext,
    p_score: int
) -> KevlarResult:
    """
    Apply Kevlar filters (BLOCKING).
    Returns Passed=True only if ALL filters pass.
    """
    
    # Extract event data
    event_type = event.get('event', '')
    level_price = float(event.get('level', 0.0))
    current_price = market.price
    atr = market.atr
    
    # Safety Check: If ATR is 0 -> BLOCK
    if atr == 0:
        return KevlarResult(passed=False, blocked_by="K0_NO_ATR")

    # --- K1: Momentum Instability ---
    # 1. Body > 2.0 * ATR
    candle_body = abs(market.candle_close - market.candle_open)
    max_body = 2.0 * atr 
    
    if candle_body > max_body:
         return KevlarResult(
             passed=False,
             blocked_by=f"K1_CRASH_SCENARIO (Body {candle_body:.2f} > {max_body:.2f})"
         )

    # 2. "No Brakes" (Long Only): Close in bottom 5% of candle
    if "SUPPORT" in event_type:
        candle_range = market.candle_high - market.candle_low
        if candle_range > 0:
            # Position of close relative to low (0.0 = Low, 1.0 = High)
            close_pos = (market.candle_close - market.candle_low) / candle_range
            if close_pos < 0.05:
                return KevlarResult(
                    passed=False,
                    blocked_by=f"K1_NO_BRAKES (Close @ {close_pos*100:.1f}% of Range)"
                )

    # --- K2: Missed Entry ---
    # Abs(Price - Level) > 1.5 * ATR
    dist = abs(current_price - level_price)
    max_dist = 1.5 * atr
    
    if dist > max_dist:
        return KevlarResult(
            passed=False, 
            blocked_by=f"K2_MISSED_ENTRY (Dist {dist:.2f} > {max_dist:.2f})"
        )

    # --- K3: RSI Panic Guard ---
    # If RSI < 20, Require Score >= 60. Else Block.
    if market.rsi < 20:
        if p_score < 60:
             return KevlarResult(
                 passed=False,
                 blocked_by=f"K3_RSI_PANIC (RSI {market.rsi:.1f} < 20 & Score {p_score} < 60)"
             )

    # --- K4: Sentiment Trap ---
    # Long Trap: Funding > 0.03% AND Price < VWAP (Crowd Long, Price Bearish) -> BLOCK Longs
    funding = sentiment.funding
    
    if "SUPPORT" in event_type: # Long Attempt
        if funding > 0.0003 and current_price < market.vwap:
             return KevlarResult(
                 passed=False,
                 blocked_by=f"K4_SENTIMENT_LONG_TRAP (F={funding*100:.3f}%, P<VWAP)"
             )

    # Short Trap (Resistance)
    if "RESISTANCE" in event_type: # Short Attempt
        if funding < -0.0003 and current_price > market.vwap:
             return KevlarResult(
                 passed=False,
                 blocked_by=f"K4_SENTIMENT_SHORT_TRAP (F={funding*100:.3f}%, P>VWAP)"
             )

    # All Passed
    return KevlarResult(passed=True, blocked_by=None)
