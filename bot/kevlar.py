""" 
Kevlar Core - HOTFIX 2026.02.11 
Строгие фильтры, синхронизированные с Pine Script v3.7 
""" 
 
from bot.config import Config 
from bot.decision_models import MarketContext, SentimentContext, KevlarResult 
from bot.models.market_context import MarketContext as DTOContext
 
def check_safety( 
    event: dict, 
    market: MarketContext, 
    sentiment: SentimentContext, 
    p_score: int 
) -> KevlarResult: 
    """ 
    Применяет Kevlar фильтры. 
    Возвращает Passed=True ТОЛЬКО если ВСЕ фильтры пройдены. 
    """ 
    
    # Извлечение данных 
    event_type = event.get('event', '') 
    level_price = float(event.get('level', 0.0)) 
    current_price = market.price 
    atr = market.atr 
 
    # ============ ФИЛЬТР 0: ЦЕЛОСТНОСТЬ ДАННЫХ ============ 
    if atr == 0 or current_price == 0: 
        return KevlarResult( 
            passed=False, 
            blocked_by="K0_INVALID_MARKET_DATA" 
        ) 
 
    # ============ ФИЛЬТР 1: ДИСТАНЦИЯ ДО УРОВНЯ ============ 
    # Источник: Pine Script v3.7, параметр 'maxDistPct' = 30.0 
    dist_pct = abs(current_price - level_price) / current_price * 100 
    
    if dist_pct > Config.MAX_DIST_PCT: 
        return KevlarResult( 
            passed=False, 
            blocked_by=f"K1_LEVEL_TOO_FAR (Дист: {dist_pct:.1f}% > {Config.MAX_DIST_PCT}%)" 
        ) 
 
    # ============ ФИЛЬТР 2: MOMENTUM - NO BRAKES ============ 
    # ТОЛЬКО для LONG (покупка на падающем ноже) 
    if "SUPPORT" in event_type: 
        candle_range = market.candle_high - market.candle_low 
        if candle_range > 0: 
            close_pos = (market.candle_close - market.candle_low) / candle_range 
            if close_pos < 0.05: 
                return KevlarResult( 
                    passed=False, 
                    blocked_by=f"K2_NO_BRAKES (Close @ {close_pos*100:.1f}% от минимума)" 
                ) 
 
    # ============ ФИЛЬТР 3: RSI PANIC GUARD ============ 
    if market.rsi < Config.KEVLAR_RSI_LOW: 
        if p_score < Config.KEVLAR_STRONG_PSCORE: 
            return KevlarResult( 
                passed=False, 
                blocked_by=f"K3_RSI_PANIC (RSI {market.rsi:.1f} < 20 & Score {p_score} < 50)" 
            ) 
 
    # ============ ФИЛЬТР 4: SENTIMENT TRAP ============ 
    funding = sentiment.funding 
    
    if "SUPPORT" in event_type: 
        if funding > Config.FUNDING_THRESHOLD and current_price < market.vwap: 
            return KevlarResult( 
                passed=False, 
                blocked_by=f"K4_SENTIMENT_LONG_TRAP (F: {funding*100:.3f}%, P < VWAP)" 
            ) 
 
    if "RESISTANCE" in event_type: 
        if funding < -Config.FUNDING_THRESHOLD and current_price > market.vwap: 
            return KevlarResult( 
                passed=False, 
                blocked_by=f"K4_SENTIMENT_SHORT_TRAP (F: {funding*100:.3f}%, P > VWAP)" 
            ) 
 
    # Все фильтры пройдены 
    return KevlarResult(passed=True, blocked_by=None)


def check_safety_v2(
    event: dict,
    ctx: DTOContext,
    p_score: int
) -> KevlarResult:
    """
    Kevlar v2 safety check with ALL filters enabled by default.
    Returns Passed=True ONLY if ALL filters are passed.
    """
    event_type = event.get("event", "")
    level_price = float(event.get("level", 0.0))
    current_price = ctx.price
    atr = ctx.atr
    
    # ============ ФИЛЬТР 0: ЦЕЛОСТНОСТЬ ДАННЫХ ============
    if atr == 0 or current_price == 0:
        return KevlarResult(passed=False, blocked_by="K0_INVALID_MARKET_DATA")

    # VALIDATION: Check for sufficient data
    if not ctx.candles or len(ctx.candles) < 5:
        return KevlarResult(passed=False, blocked_by="K0_INSUFFICIENT_CANDLES_DATA")
    if ctx.rsi is None:
        return KevlarResult(passed=False, blocked_by="K0_NO_RSI_DATA")
    
    # ============ ФИЛЬТР 1: ДИСТАНЦИЯ ДО УРОВНЯ ============
    dist_pct = abs(current_price - level_price) / current_price * 100
    if dist_pct > Config.MAX_DIST_PCT:
        return KevlarResult(passed=False, blocked_by=f"K1_LEVEL_TOO_FAR ({dist_pct:.1f}% > {Config.MAX_DIST_PCT}%)")
    
    # ============ ФИЛЬТР 2: MOMENTUM - NO BRAKES ============
    # Momentum Protection — защита от "падающего ножа"
    # Logic: Close[0] / Close[5] - 1 < -5% (RELAXED from -3%)
    if "SUPPORT" in event_type:
        # Check if we have enough candles (already checked above)
        if not ctx.candles or len(ctx.candles) < 5:
             # Safety fallback: if no data, do we block? 
             # No, let's assume safe if data missing, but log warning elsewhere.
             pass
        else:
            current_close = ctx.candles[-1].close
            prev_close_5 = ctx.candles[-5].close
            
            momentum = (current_close / prev_close_5) - 1
            if momentum < -0.05:  # P0 FIX: RELAXED to -5%
                 return KevlarResult(
                    passed=False,
                    blocked_by=f"K2_NO_BRAKES (Falling Knife: {momentum*100:.1f}%)"
                )
    
    # ============ ФИЛЬТР 3: RSI PANIC GUARD ============
    # RSI Panic Guard — защита от входа на панике
    if ctx.rsi < 30 or ctx.rsi > 70:
        return KevlarResult(
            passed=False,
            blocked_by=f"K3_RSI_PANIC (RSI {ctx.rsi:.1f} is extreme)"
        )
    
    # ============ ФИЛЬТР 4: SENTIMENT TRAP ============
    # Funding rate based sentiment filtering
    if ctx.funding_rate is not None:
        if "SUPPORT" in event_type:
            if ctx.funding_rate > Config.FUNDING_THRESHOLD and current_price < (ctx.vwap or current_price): # Fallback to price if VWAP 0
                return KevlarResult(
                    passed=False,
                    blocked_by=f"K4_SENTIMENT_LONG_TRAP (F: {ctx.funding_rate*100:.3f}%, P < VWAP)"
                )
        if "RESISTANCE" in event_type:
            if ctx.funding_rate < -Config.FUNDING_THRESHOLD and current_price > (ctx.vwap or current_price):
                return KevlarResult(
                    passed=False,
                    blocked_by=f"K4_SENTIMENT_SHORT_TRAP (F: {ctx.funding_rate*100:.3f}%, P > VWAP)"
                )

    # Все фильтры пройдены
    return KevlarResult(passed=True, blocked_by=None)
