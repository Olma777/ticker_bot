import asyncio
import os
from dotenv import load_dotenv

# 1. САМОЕ ВАЖНОЕ: Загружаем переменные из .env в самом начале
load_dotenv()

# 2. DEBUG: Проверяем, какой ключ загрузился
api_key = os.getenv("OPENROUTER_API_KEY")

print("\n--- DEBUG INFO ---")
if api_key:
    # Показываем первые 10 символов ключа (безопасно), чтобы убедиться, что это не dummy
    print(f"✅ API Key found: {api_key[:10]}...")
    if "dummy" in api_key:
        print("⚠️ WARNING: You are still using a DUMMY key! Check your .env file.")
else:
    print("❌ ERROR: API Key NOT found! Make sure .env file exists and has OPENROUTER_API_KEY.")
    print("Stopping test to prevent 401 Error.")
    exit()
print("------------------\n")

# Импортируем функции бота ТОЛЬКО ПОСЛЕ загрузки ключей
try:
    from bot.analysis import get_sniper_analysis, get_daily_briefing
except ImportError as e:
    print(f"❌ Import Error: {e}")
    print("Check if you are running this from the root folder: ./venv/bin/python test_integration.py")
    exit()

async def test_integration():
    print("🚀 Starting Integration Test...\n")

    # --- ТЕСТ 1: SNIPER ---
    ticker = "BTC"
    print(f"📡 Requesting Sniper Analysis for {ticker}...")
    try:
        # Вызываем функцию. Если твоя функция требует (ticker, name, price), Python скажет об этом.
        # Но по нашей логике мы упростили её до (ticker), так как данные качаются внутри.
        # Попробуем вызвать просто с тикером.
        try:
            result = await get_sniper_analysis(ticker)
        except TypeError:
            # Фолбэк на случай, если сигнатура функции осталась старой
            result = await get_sniper_analysis(ticker, "Bitcoin", 97000)

        print("\n📝 Result received (first 300 chars):")
        print(result[:300] + "...\n")
        
        if "Algorithmic" in result or "Pivot" in result or "Zone" in result:
             print("✅ SUCCESS: Sniper Analysis contains Algorithmic Levels!")
        else:
             print("⚠️ WARNING: AI response might be missing specific level data.")
             
    except Exception as e:
        print(f"❌ Error in Sniper Analysis: {e}")

    print("\n------------------------------------------------\n")

    # --- ТЕСТ 2: DAILY BRIEFING ---
    print("🌅 Requesting Daily Briefing...")
    try:
        # Для дейли брифинга обычно аргументы не нужны или нужен словарь
        # Попробуем без аргументов (если логика берет данные сама) или с заглушкой
        try:
            result = await get_daily_briefing()
        except TypeError:
            market_data = {'top_coins': 'BTC, ETH', 'btc_dominance': '58%'}
            result = await get_daily_briefing(market_data)

        print("\n📝 Result received (first 300 chars):")
        print(result[:300] + "...\n")
        
        if "Market Regime" in result or "COMPRESSION" in result or "EXPANSION" in result:
             print("✅ SUCCESS: Market Regime logic is working!")
        else:
             print("⚠️ WARNING: Market Regime missing in response.")

    except Exception as e:
        print(f"❌ Error in Daily Briefing: {e}")

if __name__ == "__main__":
    asyncio.run(test_integration())