"""
Deterministic Order Calculator (P1 - Required).
A single source of truth for all order math: Entry, SL, TP, Size, RRR.
Pure logic, no I/O.
"""

from dataclasses import dataclass
from typing import Literal, Optional, List
import math

from bot.config import Config, TRADING

# Type Definitions
SideType = Literal["LONG", "SHORT"]

@dataclass
class OrderPlan:
    """The result of a deterministic order calculation."""
    entry: float
    sl: float
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
    capital: float,
    risk_pct: float,
    lot_step: Optional[float] = None
) -> OrderPlan:
    """
    Builds a strict order plan based on P1 specs.
    
    Args:
        side: "LONG" or "SHORT"
        level: Central level price from TV payload
        zone_half: Half-width of the zone (from TV or calc)
        atr: Current market ATR(14)
        capital: Account equity to base risk on
        risk_pct: Percentage risk (1.0 = 1%)
        lot_step: Optional step size for rounding (e.g. 0.001 for BTC)
        
    Returns:
        OrderPlan object. If reason_blocked is set, discard trade.
    """
    
    # 1. Entry (TOUCH_LIMIT: entry = level)
    entry_price = level
    
    # 2. Stop Loss (Zone Boundary ± Buffer)
    sl_buffer = TRADING.sl_buffer_atr * atr
    
    if side == "LONG":
        zone_bot = level - zone_half
        sl_price = zone_bot - sl_buffer
        
        # 3. Take Profits (ATR based from Entry)
        tp1 = entry_price + (TRADING.tp1_atr * atr)
        tp2 = entry_price + (TRADING.tp2_atr * atr)
        tp3 = entry_price + (TRADING.tp3_atr * atr)
        
    else: # SHORT
        zone_top = level + zone_half
        sl_price = zone_top + sl_buffer
        
        tp1 = entry_price - (TRADING.tp1_atr * atr)
        tp2 = entry_price - (TRADING.tp2_atr * atr)
        tp3 = entry_price - (TRADING.tp3_atr * atr)

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
    
    # 7. Mandatory Sanity Gate
    if rrr_tp2 < TRADING.min_rrr:
        return _blocked_plan(f"RRR {rrr_tp2:.2f} < Min {TRADING.min_rrr}")

    # Success
    return OrderPlan(
        entry=entry_price,
        sl=sl_price,
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
        entry=0.0, sl=0.0, tp1=0.0, tp2=0.0, tp3=0.0,
        stop_dist=0.0, risk_amount=0.0, size_units=0.0, rrr_tp2=0.0,
        reason_blocked=reason
    )
