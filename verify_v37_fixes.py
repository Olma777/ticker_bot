
import asyncio
import logging
import sys
from unittest.mock import patch, MagicMock

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import modules to test
from bot.analysis import _format_price, _clean_telegram_html
from bot.ai_analyst import _detect_liquidity_hunts, get_ai_sniper_analysis
from bot.order_calc import build_order_plan
from bot.kevlar import check_safety_v2
from bot.models.market_context import MarketContext as DTOContext, Candle

async def test_hbar_precision():
    print("\n--- TEST 1: HBAR LOW VALUE PRECISION ---")
    price = 0.090123
    formatted = _format_price(price)
    print(f"Input: {price}, Output: {formatted}")
    assert formatted == "$0.0901", f"Failed: {formatted}"
    
    # Test liquidity formatter indirectly via _detect_liquidity_hunts
    supports = [{'price': 0.09, 'score': 2.0}]
    resistances = []
    verdict = _detect_liquidity_hunts(0.091, 0.001, supports, resistances)
    print(f"Liquidity Verdict: {verdict}")
    # Expected: $0.0855-$0.0873 (approx)
    assert "$0.0873" in str(verdict) or "$0.0855" in str(verdict), "Liquidity formatting failed"
    print("✅ HBAR Precision Passed")

async def test_order_calc_funding():
    print("\n--- TEST 2: ORDER CALC WITH FUNDING ---")
    # Case: Shorting with positive funding (receiving payouts) -> Good
    plan_good = build_order_plan(
        side="SHORT", level=100, zone_half=1, atr=2, 
        funding_rate=0.0005, estimated_hold_hours=24
    )
    print(f"Short + Pos Funding RRR: {plan_good.rrr_tp2:.2f}")
    
    # Case: Longing with positive funding (paying fee) -> Bad impact
    plan_bad_fund = build_order_plan(
        side="LONG", level=100, zone_half=1, atr=2,
        funding_rate=0.001, estimated_hold_hours=48 # High cost
    )
    print(f"Long + High Pos Funding Blocked Reason: {plan_bad_fund.reason_blocked}")
    # Note: Logic only warning in logs currently unless RRR low.
    
    print("✅ Funding Calc Executed")

async def test_html_cleaner():
    print("\n--- TEST 3: HTML CLEANER ---")
    dirty = "Phase: Accumulation\n<ul><li>Item 1</li><li>Item 2</li></ul>"
    clean = _clean_telegram_html(dirty)
    print(f"Original: {dirty!r}")
    print(f"Cleaned:  {clean!r}")
    assert "<ul>" not in clean, "<ul> found"
    assert "• Item 1" in clean, "Bullet point missing"
    print("✅ HTML Cleaner Passed")

async def test_kevlar_short_squeeze():
    print("\n--- TEST 4: KEVLAR SHORT SQUEEZE ---")
    
    # Mock Context with rising prices (squeeze)
    class MockCandle:
        def __init__(self, c): self.close = c
        
    ctx = DTOContext(
        symbol="APE", price=105, btc_regime="neutral", atr=1, vwap=100, funding_rate=0.01,
        timestamp=None, candle_open=0, candle_high=0, candle_low=0, candle_close=105,
        rsi=60, candles=[MockCandle(100), MockCandle(101), MockCandle(102), MockCandle(103), MockCandle(105)]
    )
    # Move from 100 to 105 (+5%) in 5 bars
    
    event = {"event": "RESISTANCE", "level": 105}
    res = check_safety_v2(event, ctx, p_score=40)
    print(f"Squeeze Check Result: {res.passed}, Reason: {res.blocked_by}")
    
    assert not res.passed, "Should be blocked by K2_SHORT_SQUEEZE"
    assert "K2_SHORT_SQUEEZE" in res.blocked_by, "Wrong block reason"
    print("✅ Kevlar Short Squeeze Passed")

async def test_ape_direction_logic():
    print("\n--- TEST 5: APE DIRECTION LOGIC (P0) ---")
    
    # Mock indicators response
    mock_indicators = {
        'price': 1.00,
        'atr_val': 0.02, # Fixed type: float not string based on usage
        'rsi': 55,
        'p_score': 60, # High Score
        'support': [{'price': 0.98, 'score': 2.5}], # Fixed structure: list of dicts
        'resistance': [{'price': 1.05, 'score': 0.5}], # Weak Resistance
        'change': '+1%',
        'vwap': 1.00,
        'funding': '0.01%',
        'open_interest': '$100M',
        'btc_regime': 'NEUTRAL',
        'strategy': {'side': 'LONG'},
        'candles': [
            Candle(timestamp=0, open=100, high=100, low=100, close=100, volume=1000),
            Candle(timestamp=0, open=100, high=100, low=100, close=100, volume=1000),
            Candle(timestamp=0, open=100, high=100, low=100, close=100, volume=1000),
            Candle(timestamp=0, open=100, high=100, low=100, close=100, volume=1000),
            Candle(timestamp=0, open=100, high=100, low=100, close=100, volume=1000)
        ] 
    }
    
    # Use AsyncMock which handles awaitables correctly
    # Check if AsyncMock is available (Python 3.8+)
    try:
        from unittest.mock import AsyncMock
    except ImportError:
        # Fallback for strict environments (shouldn't happen on Mac python 3)
        print("AsyncMock not found, using MagicMock")
        from unittest.mock import MagicMock
        # But MagicMock isn't async primitive. 
        # We assume standard 3.8+ env.
    
    # Patch bot.indicators.get_technical_indicators
    # Note: We need to patch where it is IMPORTED in ai_analyst if it was from ... import ...
    # But ai_analyst does 'from bot.indicators import get_technical_indicators' inside the function.
    # So patching sys.modules or the source module should work.
    
    with patch('bot.indicators.get_technical_indicators', new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = mock_indicators
        
        with patch('bot.analysis._generate_ai_contextual_analysis', new_callable=AsyncMock) as mock_ai:
             mock_ai.return_value = "<div>AI Analysis</div>"
             
             try:
                 result = await get_ai_sniper_analysis("APE")
                 print(f"APE Result: {result}")
                 
                 assert result['status'] == 'OK', f"Status not OK: {result.get('status')} {result.get('reason')}"
                 # Note: get_ai_sniper_analysis returns key 'type' or 'side'?
                 # Original code: "type": direction (LONG/SHORT/WAIT)
                 assert result['type'] == 'LONG', f"Direction wrong: {result.get('type')}"
                 assert result['entry'] == 0.98, f"Entry wrong: {result.get('entry')}"
                 
                 print("✅ Direction Logic - Strong Support Priority Passed")
             except Exception as e:
                 print(f"Inside Test Error: {e}")
                 import traceback
                 traceback.print_exc()
                 raise e

async def main():
    try:
        await test_hbar_precision()
        await test_order_calc_funding()
        await test_html_cleaner()
        await test_kevlar_short_squeeze()
        await test_ape_direction_logic()
        print("\n🎉 ALL TESTS PASSED")
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
