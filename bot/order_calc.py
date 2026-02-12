"""
Deterministic Order Calculator (P1 - Required).
A single source of truth for all order math: Entry, SL, TP, Size, RRR.
Pure logic, no I/O.
UPDATED: Uses Config.SL_ATR_MULT (1.5) instead of hardcoded 0.25.
"""

from dataclasses import dataclass
from typing import Literal, Optional, List
import math
from bot.config import Config

# Type Definitions
SideType = Literal["LONG", "SHORT"]

@dataclass
class OrderPlan:
    """The result of a deterministic order calculation."""
    entry: float
    stop_loss: float        # CHANGED: was 'sl'
    tp1: float
    tp2: float
    tp3: float
    
    stop_dist: float
    risk_amount: float
    size_units: float
    rrr_tp2: float
    
    reason_blocked: Optional[str] = None  # If set, trade is INVALID


def build_order_plan(
    side: SideType,
    level: float,
    zone_half: float,
    atr: float,
    capital: float = Config.DEFAULT_CAPITAL,
    risk_pct: float = Config.DEFAULT_RISK_PCT,
    lot_step: Optional[float] = None,
    funding_rate: Optional[float] = None,  # NEW PARAM
    estimated_hold_hours: float = 24.0      # NEW PARAM
) -> OrderPlan:
    """
    Builds a strict order plan based on P1 specs.
    
    Args:
        side: "LONG" or "SHORT"
        level: Central level price from TV payload
        zone_half: Half-width of the zone (from TV or calc)
        atr: Current market ATR(14)
        capital: Account equity to base risk on (default from Config)
        risk_pct: Percentage risk (1.0 = 1%) (default from Config)
        lot_step: Optional step size for rounding (e.g. 0.001 for BTC)
        funding_rate: Current 8h funding rate (e.g. 0.0001 for 0.01%)
        estimated_hold_hours: Expected trade duration for funding calc
        
    Returns:
        OrderPlan object. If reason_blocked is set, discard trade.
    """
    
    # 1. Entry (TOUCH_LIMIT: entry = level)
    entry_price = level
    
    # 2. Stop Loss & Take Profits (ATR Based - User Spec 2026-02-12)
    sl_dist = Config.SL_ATR_MULT * atr
    tp1_dist = Config.TP1_ATR_MULT * atr
    tp2_dist = Config.TP2_ATR_MULT * atr
    tp3_dist = Config.TP3_ATR_MULT * atr
    
    if side == "LONG":
        sl_price = entry_price - sl_dist
        tp1 = entry_price + tp1_dist
        tp2 = entry_price + tp2_dist
        tp3 = entry_price + tp3_dist
        
    else: # SHORT
        sl_price = entry_price + sl_dist
        tp1 = entry_price - tp1_dist
        tp2 = entry_price - tp2_dist
        tp3 = entry_price - tp3_dist

    # 4. Stop Distance & Validation
    stop_dist = abs(entry_price - sl_price)
    
    # Sanity
    if stop_dist == 0:
        return _blocked_plan("Stop Distance is Zero")
        
    # 5. Risk & Size
    risk_amount = capital * (risk_pct / 100.0)
    
    # Size = Risk / Dist
    raw_size = risk_amount / stop_dist
    
    # Lot Step Rounding (Floor)
    if lot_step and lot_step > 0:
        steps = math.floor(raw_size / lot_step)
        size_units = steps * lot_step
    else:
        size_units = raw_size
        
    # Sanity
    if size_units <= 0:
        return _blocked_plan("Calculated Size is Zero")

    # 6. RRR (to TP2)
    # RRR = |TP2 - Entry| / StopDist
    reward_dist = abs(tp2 - entry_price)
    rrr_tp2 = reward_dist / stop_dist
    
    # 7. Funding Rate Adjustment (P0 FIX)
    if funding_rate is not None and funding_rate != 0:
        # Фандинг каждые 8 часов на Binance
        funding_periods = estimated_hold_hours / 8
        funding_cost_pct = abs(funding_rate) * funding_periods
        
        # Если шортуем при положительном фандинге или лонгуем при отрицательном - это плюс
        # Если наоборот - минус
        funding_pnl_impact = 0.0
        if side == "LONG" and funding_rate < 0:
            funding_pnl_impact = -funding_cost_pct  # Получаем фандинг (отрицательная стоимость = доход)
        elif side == "SHORT" and funding_rate > 0:
            funding_pnl_impact = -funding_cost_pct  # Получаем фандинг
        else:
            funding_pnl_impact = funding_cost_pct   # Платим фандинг
        
        # Пока что просто логируем, не меняем логику блокировки, но добавляем предупреждение
        if funding_pnl_impact > 0.005:  # Если платим >0.5% за время удержания
            if rrr_tp2 < 1.3:  # Повышаем требования к RRR при дорогом фандинге
                return _blocked_plan(f"High funding cost ({funding_pnl_impact*100:.2f}%) with low RRR {rrr_tp2:.2f}")

    # 8. Mandatory Sanity Gate
    if rrr_tp2 < 1.10:  # Can be moved to Config later
        return _blocked_plan(f"RRR {rrr_tp2:.2f} is below Min 1.10")

    # Success
    return OrderPlan(
        entry=entry_price,
        stop_loss=sl_price,      # CHANGED: was 'sl'
        tp1=tp1,
        tp2=tp2,
        tp3=tp3,
        stop_dist=stop_dist,
        risk_amount=risk_amount,
        size_units=size_units,
        rrr_tp2=rrr_tp2,
        reason_blocked=None
    )


def _blocked_plan(reason: str) -> OrderPlan:
    """Helper to return a blocked plan safely."""
    return OrderPlan(
        entry=0.0, stop_loss=0.0, tp1=0.0, tp2=0.0, tp3=0.0,
        stop_dist=0.0, risk_amount=0.0, size_units=0.0, rrr_tp2=0.0,
        reason_blocked=reason
    )


def validate_signal(signal: dict) -> bool:
    """Validate that signal contains all required fields for execution."""
    required = ["entry", "sl", "tp1", "tp2", "tp3", "rrr"]
    missing = [f for f in required if f not in signal or not signal[f]]
    if missing:
        raise ValueError(f"Invalid signal: missing {missing}")
    if signal["rrr"] < 1.1:
        raise ValueError(f"RRR too low: {signal['rrr']:.2f} < 1.10")
    return True
