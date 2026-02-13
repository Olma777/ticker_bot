
import os
import sys
from datetime import datetime
from pathlib import Path

# Mock Data
mock_signal = {
    'symbol': 'ETH', 'side': 'long', 'entry': 2000.0, 
    'sl': 1900.0, 'tp1': 2050.0, 'tp2': 2100.0, 'tp3': 2200.0, 
    'rrr': 2.0, 'p_score': 85, 'change': 1.2,
    'current_price': 2005.0,
    # Dirty Data
    'ai_analysis': 'Test "quote" & <b>bold from AI</b> <script>alert(1)</script>',
    'strong_supports': '1900 (Dirty <tag>)',
    'strong_resists': '2100 & More',
    'logic_setup': 'Setup with <br>',
    'logic_summary': 'Summary with "quotes"'
}

def test_config():
    print("\n--- Testing Config.DATA_DIR ---")
    try:
        from bot.config import Config
        print(f"Config.DATA_DIR: {Config.DATA_DIR}")
        if not isinstance(Config.DATA_DIR, Path):
            print("❌ DATA_DIR is not a Path object")
            sys.exit(1)
        print("✅ Config.DATA_DIR is valid")
    except ImportError as e:
        print(f"❌ ImportError: {e}")
        sys.exit(1)
    except AttributeError as e:
        print(f"❌ AttributeError: {e}")
        sys.exit(1)

def test_html():
    print("\n--- Testing HTML Escaping ---")
    try:
        from bot.analysis import format_signal_html
        formatted = format_signal_html(mock_signal)
        print("Formatted Output:")
        print(formatted)
        
        # Validation
        if "<script>" in formatted:
            print("❌ FAILED: <script> tag found!")
            sys.exit(1)
        if "<b>ETH</b>" not in formatted:
            print("❌ FAILED: Bot's <b>ETH</b> tag missing/escaped!")
            sys.exit(1)
        if "&lt;script&gt;" not in formatted:
            print("❌ FAILED: <script> was not escaped!")
            sys.exit(1)
        if "Test &quot;quote&quot;" not in formatted:
             print("❌ FAILED: Quotes not escaped!")
             sys.exit(1)
             
        print("✅ HTML Escaping Verified")
    except Exception as e:
        print(f"❌ Exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    test_config()
    test_html()
