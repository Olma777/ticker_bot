"""
Kevlar Core.
Strict filters to block bad trades regardless of score.
Implemented in purely deterministic logic.
Updated for P1-Final: K1 Momentum Implemented.
"""

from typing import Optional

from bot.config import Config
from bot.decision_models import (
    MarketContext, 
    SentimentContext, 
    KevlarResult, 
    PScoreResult
)

def apply_kevlar(
    event: dict,
    market: MarketContext,
    sentiment: SentimentContext,
    pscore: PScoreResult
) -> KevlarResult:
    """
    Apply Kevlar filters K1-K4 (BLOCKING).
    Returns Passed=True only if ALL filters pass.
    """
    
    # Extract event data
    event_type = event.get('event') 
    level_price = event.get('level', 0)
    current_price = market.price
    atr = market.atr
    
    # Safety Check: If ATR is 0 -> BLOCK
    if atr == 0:
        return KevlarResult(passed=False, blocked_by="K0_NO_ATR")

    # --- K1: Momentum Instability ---
    # BLOCK if abs(close - open) > X * ATR
    # Requires candle Open. 
    candle_body = abs(market.price - market.open)
    max_body = Config.KEVLAR_MOMENTUM_ATR_MULT * atr
    
    if candle_body > max_body:
         return KevlarResult(
             passed=False,
             blocked_by=f"K1_MOMENTUM_INSTABILITY (Body {candle_body:.2f} > {max_body:.2f})"
         )

    # --- K2: Missed Entry ---
    # BLOCK if abs(price - level) > Y * ATR
    dist = abs(current_price - level_price)
    max_dist = Config.KEVLAR_MISSED_ENTRY_ATR_MULT * atr
    
    if dist > max_dist:
        return KevlarResult(
            passed=False, 
            blocked_by=f"K2_MISSED_ENTRY (Dist {dist:.2f} > {max_dist:.2f})"
        )

    # --- K3: RSI Panic Guard ---
    # RSI < 20 or > 80: Block unless P-Score >= STRONG
    if market.rsi < Config.KEVLAR_RSI_LOW:
        if pscore.score < Config.KEVLAR_STRONG_PSCORE:
             return KevlarResult(
                 passed=False,
                 blocked_by=f"K3_RSI_PANIC (RSI {market.rsi:.1f} < {Config.KEVLAR_RSI_LOW})"
             )
             
    if market.rsi > Config.KEVLAR_RSI_HIGH:
        if pscore.score < Config.KEVLAR_STRONG_PSCORE:
             return KevlarResult(
                 passed=False,
                 blocked_by=f"K3_RSI_PANIC (RSI {market.rsi:.1f} > {Config.KEVLAR_RSI_HIGH})"
             )

    # --- K4: Sentiment Trap ---
    # Long Trap: Funding > Thr AND Price < VWAP (Crowd Long, Price Bearish) -> BLOCK Longs
    funding = sentiment.funding if sentiment.funding is not None else 0.0
    
    # Check Longs (SUPPORT_TEST)
    if event_type == "SUPPORT_TEST":
        if funding > Config.FUNDING_THRESHOLD and current_price < market.vwap:
             return KevlarResult(
                 passed=False,
                 blocked_by=f"K4_SENTIMENT_LONG_TRAP (F={funding:.4f}, P<VWAP)"
             )

    # Check Shorts (RESISTANCE_TEST)
    if event_type == "RESISTANCE_TEST":
        if funding < -Config.FUNDING_THRESHOLD and current_price > market.vwap:
             return KevlarResult(
                 passed=False,
                 blocked_by=f"K4_SENTIMENT_SHORT_TRAP (F={funding:.4f}, P>VWAP)"
             )

    # All Passed
    return KevlarResult(passed=True, blocked_by=None)
