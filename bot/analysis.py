import os
import logging
import ccxt.async_support as ccxt
from datetime import datetime, timedelta
from openai import AsyncOpenAI
from aiolimiter import AsyncLimiter
from bot.prices import get_crypto_price, get_market_summary
from bot.indicators import get_technical_indicators

logger = logging.getLogger(__name__)

# --- ОГРАНИЧЕНИЯ И КЭШ ---
rate_limiter = AsyncLimiter(8, 60) # 8 запросов в минуту
daily_cache = {}

# --- АКТУАЛЬНЫЕ ТИКЕРЫ ---
SECTOR_CANDIDATES = {
    "AI": ["FET/USDT", "RENDER/USDT", "WLD/USDT", "ARKM/USDT", "GRT/USDT", "NEAR/USDT"],
    "RWA": ["ONDO/USDT", "PENDLE/USDT", "OM/USDT", "TRU/USDT", "DUSK/USDT"],
    "L2": ["OP/USDT", "ARB/USDT", "POL/USDT", "METIS/USDT", "MANTA/USDT", "STRK/USDT"],
    "DePIN": ["FIL/USDT", "AR/USDT", "IOTX/USDT", "THETA/USDT", "HBAR/USDT"] 
}

# --- ФУНКЦИИ ---

async def fetch_ticker_multisource(exchanges, symbol):
    for name, exchange in exchanges.items():
        try:
            ticker = await exchange.fetch_ticker(symbol)
            if not ticker or ticker['last'] is None: continue
            return {
                "price": ticker['last'],
                "change": ticker['percentage'],
                "vol": ticker['quoteVolume'] if ticker['quoteVolume'] else 0,
                "source": name
            }
        except Exception:
            continue
    return None

async def fetch_real_market_data():
    exchanges = {
        "Binance": ccxt.binance({'options': {'defaultType': 'future'}, 'enableRateLimit': True}),
        "Bybit": ccxt.bybit({'options': {'defaultType': 'future'}, 'enableRateLimit': True}),
        "MEXC": ccxt.mexc({'options': {'defaultType': 'swap'}, 'enableRateLimit': True}),
        "BingX": ccxt.bingx({'options': {'defaultType': 'swap'}, 'enableRateLimit': True})
    }
    market_report = ""
    valid_tickers_list = [] 
    try:
        btc_data = await fetch_ticker_multisource(exchanges, 'BTC/USDT')
        if btc_data:
            market_report += f"🛑 GLOBAL BTC: ${btc_data['price']} ({btc_data['change']}%)\n"
        
        market_report += "📊 VERIFIED MARKET DATA:\n"
        for sector, tickers in SECTOR_CANDIDATES.items():
            market_report += f"--- {sector} ---\n"
            found_any = False
            for ticker in tickers:
                data = await fetch_ticker_multisource(exchanges, ticker)
                if data:
                    vol_str = f"${int(data['vol']):,}"
                    market_report += f"ID: {ticker} | Price: {data['price']} | Change: {data['change']}% | Vol: {vol_str} | Src: {data['source']}\n"
                    valid_tickers_list.append(ticker)
                    found_any = True
            if not found_any:
                market_report += f"(No data for {sector})\n"
            market_report += "\n"
    except Exception as e:
        logger.error(f"Error: {e}")
        market_report += "Error fetching data."
    finally:
        for exchange in exchanges.values():
            await exchange.close()
    return market_report, valid_tickers_list

# --- 1. DAILY BRIEFING ---
async def get_daily_briefing(user_input=None):
    cache_key = datetime.utcnow().strftime("%Y-%m-%d-%H")
    if cache_key in daily_cache:
        return daily_cache[cache_key]

    real_market_data, valid_tickers = await fetch_real_market_data()
    if not valid_tickers:
        return "⚠️ Ошибка: Не удалось получить рыночные данные. Попробуйте позже."

    client = AsyncOpenAI(api_key=os.getenv("OPENROUTER_API_KEY"), base_url="https://openrouter.ai/api/v1")
    
    prompt = f"""
    Ты — алгоритмический трейдер. СЕГОДНЯ: {datetime.utcnow().strftime("%Y-%m-%d")}.
    ДАННЫЕ РЫНКА: {real_market_data}
    СПИСОК ТИКЕРОВ: {valid_tickers}
    
    ЗАДАЧА: Выбери 4 лучших актива для ЛОНГА. Используй только предоставленные цифры.
    СТРУКТУРА (MARKDOWN):
    # 🦁 Market Lens | Daily Alpha
    (Контекст BTC)
    ---
    ## 🤖 [ТИКЕР] (Сектор)
    **Цена:** [ЦЕНА] ([ИЗМЕНЕНИЕ]%)
    *Биржа: [Src]*
    1. **Драйвер:** (Кратко)
    2. **Сигнал:** Вход (текущая), Тейк (+5%), Стоп (-3%).
    """
    
    try:
        async with rate_limiter:
            completion = await client.chat.completions.create(
                model=os.getenv("MODEL_NAME", "deepseek/deepseek-chat"),
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0
            )
        report = completion.choices[0].message.content
        daily_cache.clear()
        daily_cache[cache_key] = report
        return report
    except Exception as e:
        return f"⚠️ Ошибка Daily: {e}"

# --- 2. AUDIT (VC STYLE) ---
async def analyze_token_fundamentals(ticker):
    # 1. Получаем базовые данные для шапки (Цена, Объем)
    price_data, _ = await get_crypto_price(ticker)
    curr_price = price_data.get('price', 'N/A') if price_data else 'N/A'
    vol = price_data.get('volume_24h', 'N/A') if price_data else 'N/A'
    
    client = AsyncOpenAI(api_key=os.getenv("OPENROUTER_API_KEY"), base_url="https://openrouter.ai/api/v1")
    
    # 2. VC SUPER PROMPT (HTML Only)
    prompt = f"""
    Ты — старший аналитик венчурного фонда (VC Researcher).
    Актив: {ticker.upper()} | Цена: ${curr_price} | Объем: {vol}
    
    ЗАДАЧА:
    Проведи фундаментальный аудит проекта.
    Ищи "Красные флаги" (риски) и "Зеленые флаги" (потенциал).
    
    ТРЕБОВАНИЯ К ФОРМАТУ:
    1. ИСПОЛЬЗУЙ ТОЛЬКО HTML (`<b>`, `<i>`). ЗАПРЕЩЕНО Markdown (`**`, `##`).
    2. Используй эмодзи для списков.
    3. Стиль: Лаконичный, жесткий, без воды.
    
    СТРУКТУРА ОТВЕТА (HTML):
    
    🛡 <b>{ticker.upper()} | Fundamental Audit</b>
    💰 Цена: ${curr_price}
    
    1️⃣ <b>Продукт и Утилити</b>
    ▪️ Суть: [Что они делают? 1 предложение]
    ▪️ Проблема: [Какую боль решают?]
    ▪️ Конкуренты: [Кто дышит в спину?]
    
    2️⃣ <b>Токеномика (On-Chain)</b>
    ▪️ Эмиссия: [Ограничена или бесконечна?]
    ▪️ Разлоки/Давление: [Есть ли риск дампа от фондов?]
    ▪️ Утилити токена: [Зачем он нужен? Газ/Говернанс?]
    
    3️⃣ <b>Риски и Угрозы (Red Flags)</b>
    🚩 [Риск 1]
    🚩 [Риск 2]
    
    4️⃣ <b>Вердикт VC</b>
    🏆 <b>Оценка: [1-10]/10</b>
    ▪️ Вывод: [Инвестировать / Наблюдать / Скам]
    
    ⚖️ <b>Market Lens Disclaimer:</b> Не финансовый совет.
    """

    try:
        async with rate_limiter:
            completion = await client.chat.completions.create(
                model=os.getenv("MODEL_NAME", "deepseek/deepseek-chat"),
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
        return completion.choices[0].message.content
    except Exception as e:
        return f"⚠️ Ошибка аудита: {e}"

# --- 3. SNIPER (FINAL VERSION) ---
async def get_sniper_analysis(ticker, language="ru"):
    # 1. Получаем данные цены
    price_data, error = await get_crypto_price(ticker)
    if not price_data:
        return f"⚠️ Не удалось найти {ticker}."

    # 2. Получаем индикаторы (MATH)
    indicators = await get_technical_indicators(ticker)
    if not indicators:
        indicators = {"rsi": "N/A", "trend": "UNKNOWN", "support": "N/A", "resistance": "N/A"}

    # Данные для AI
    curr_price = price_data.get('price', 'N/A')
    source = price_data.get('source', 'Unknown')
    change = price_data.get('change_24h', 'N/A')
    
    # 3. HTML ПРОМТ (Clean UI + Vertical Layout)
    prompt = f"""
    Ты — алгоритмическая система Market Lens.
    Язык: {language.upper()} (Russian).
    
    ВХОДНЫЕ ДАННЫЕ (ALGO DATA):
    • Актив: {ticker.upper()}
    • Цена: ${curr_price}
    • RSI (14): {indicators['rsi']}
    • Тренд: {indicators['trend']}
    • Поддержка (Low 50h): ${indicators['support']}
    • Сопротивление (High 50h): ${indicators['resistance']}
    
    ЗАДАЧА:
    Напиши снайперский отчет.
    1. ИСПОЛЬЗУЙ ТОЛЬКО HTML ТЕГИ (`<b>Текст</b>`). ЗАПРЕЩЕНО использовать `**` или `###`.
    2. Раздел "Индикаторы" должен показывать реальные цифры из входных данных.
    3. Тейк-профиты и Стоп-лосс пиши КАЖДЫЙ С НОВОЙ СТРОКИ.
    
    СТРУКТУРА ОТВЕТА (HTML):
    
    📊 <b>{ticker.upper()} | Smart Money Setup</b>
    💰 Цена: ${curr_price} ({change}%)
    
    📡 <b>Индикаторы Market Lens:</b>
       ▪️ RSI (14): <b>{indicators['rsi']}</b>
       ▪️ Тренд: <b>{indicators['trend']}</b>
       ▪️ Поддержка (S1): <b>${indicators['support']}</b>
       ▪️ Сопротивление (R1): <b>${indicators['resistance']}</b>
    
    1️⃣ <b>Структура рынка</b>
    ▪️ Фаза: [Фаза рынка]
    ▪️ Анализ: [Краткий вывод на основе Тренда и RSI]

    2️⃣ <b>Ликвидность & Манипуляции</b>
    ▪️ Зона интереса: [Где искать вход]
    ▪️ Сценарий: [Описание действий ММ]
    
    🎯 <b>Снайперский план</b>
    🔵 Тип: <b>[LONG / SHORT]</b> (Limit)
    🚪 Вход: <b>[Цена около S1/R1]</b>
    
    🛡 <b>Стоп-лосс:</b>
       🔴 <b>[Цена]</b>
    
    ✅ <b>Тейк-профиты:</b>
       🟢 TP1: <b>[Цена]</b>
       🟢 TP2: <b>[Цена]</b>
       🟢 TP3: <b>[Цена]</b>
    
    ⚖️ <b>Совет:</b> Риск 1% на сделку.
    """

    client = AsyncOpenAI(api_key=os.getenv("OPENROUTER_API_KEY"), base_url="https://openrouter.ai/api/v1")

    try:
        async with rate_limiter:
            completion = await client.chat.completions.create(
                model=os.getenv("MODEL_NAME", "deepseek/deepseek-chat"),
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0
            )
        return completion.choices[0].message.content
    except Exception as e:
        logger.error(f"Sniper AI Error: {e}")
        return f"⚠️ Ошибка анализа: {e}"

# --- COMPATIBILITY LAYER ---
# Старые функции для совместимости с main.py
async def get_crypto_analysis(ticker, name, language="ru"):
    """Legacy function - redirects to analyze_token_fundamentals"""
    return await analyze_token_fundamentals(ticker)