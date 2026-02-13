
import sys
import unittest
import os
import logging

# Add project root to path
sys.path.append(os.getcwd())

# Mock logger
logging.basicConfig(level=logging.INFO)

from bot.analysis import format_signal_html

class TestAuditorFinalV4(unittest.TestCase):
    def test_full_signal_sanitization(self):
        """Test that format_signal_html sanitizes all injected HTML in fields"""
        
        dirty_signal = {
            "symbol": "BTCUSDT",
            "side": "long",
            "entry": 50000.0,
            "sl": 49000.0,
            "tp1": 51000.0,
            "tp2": 52000.0,
            "tp3": 55000.0,
            "rrr": 2.5,
            "p_score": 85,
            "current_price": 50005.0,
            "change": 1.5,
            
            # Dirty fields
            "mm_phase": "<b>Accumulation</b>", # Allowed but should be clean
            "mm_verdict": ["• <b>Phase:</b> Bullish", "• <script>alert(1)</script> Attack"],
            "liquidity_hunts": ["• Hunt at <div onclick=x>100</div>"],
            "spoofing_signals": ["• Spoof <> empty tags"],
            "strong_supports": "<b>$49000</b> (Strong <script>)",
            "strong_resists": "<i>$55000</i>",
            "logic_setup": "Breakout of <123>",
            "logic_summary": "Summary with </p> broken tags"
        }
        
        result = format_signal_html(dirty_signal)
        
        print(f"\n[Final HTML]:\n{result}")
        
        # Assertions
        self.assertNotIn("<script>", result)
        self.assertNotIn("onclick", result)
        self.assertNotIn("<div", result)
        self.assertNotIn("<>", result) # Empty tags should be gone
        
        # Check that allowed tags are preserved IN THE STRUCTURE, but content is sanitized
        # Note: logic_setup sanitized via _clean_telegram_html might keep <b> if logic had it, 
        # but here logic_setup="Breakout of <123>" -> <123> is likely stripped or escaped.
        # "Breakout of <123>" -> "Breakout of" or "Breakout of &lt;123&gt;"
        
        # Check crucial info is present
        self.assertIn("BTCUSDT", result)
        self.assertIn("50,000", result)

if __name__ == '__main__':
    unittest.main()
