import asyncio
import logging
from bot.ai_analyst import get_ai_sniper_analysis
from bot.analysis import format_signal_html
from bot.config import Config

# Configure logging
logging.basicConfig(level=logging.INFO)

async def test_sniper():
    ticker = "ETH/USDT"
    print(f"🚀 Running Sniper Test for {ticker}...")
    
    try:
        # 1. Get Analysis
        result = await get_ai_sniper_analysis(ticker)
        
        print(f"✅ Analysis Result:")
        print(f"Status: {result.get('status')}")
        print(f"Reason: {result.get('reason')}")
        print(f"P-Score: {result.get('p_score', 'N/A')}")
        print(f"Side: {result.get('side', 'N/A')}")
        
        if result['status'] != 'OK':
            print(f"⚠️ Result is not OK. Skipping HTML formatting.")
            return

        # 2. Format HTML
        html = format_signal_html(result)
        
        # 3. Check for AI Context
        if "DEEP AI CONTEXT" in html:
            print("✅ AI Context detected in output.")
        else:
            print("❌ AI Context MISSING in output.")
            
        # 4. Save to file for inspection
        with open("test_output.html", "w") as f:
            f.write(html)
        print("✅ Full output saved to test_output.html")

        # 5. Print Preview
        print("\n=== OUTPUT PREVIEW (First 500 chars) ===\n")
        print(html[:500])
        print("...")

    except Exception as e:
        print(f"❌ Critical Test Failure: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_sniper())
