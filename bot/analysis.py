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
    
    # HTML ПРОМТ
    prompt = f"""
    Ты — алгоритмический аналитик Market Lens. СЕГОДНЯ: {datetime.utcnow().strftime("%Y-%m-%d")}.
    
    РЫНОЧНЫЕ ДАННЫЕ:
    {real_market_data}
    
    ЗАДАЧА:
    Выбери 3-4 наиболее перспективных актива.
    
    ТРЕБОВАНИЯ К ДИЗАЙНУ:
    1. ИСПОЛЬЗУЙ ТОЛЬКО HTML ТЕГИ (`<b>`, `<i>`).
    2. ЗАПРЕЩЕНО использовать Markdown (`**`, `##`, `---`).
    3. Используй эмодзи.
    
    СТРУКТУРА ОТВЕТА (HTML):
    
    🦁 <b>Market Lens | Daily Alpha</b>
    📉 <b>BTC Context:</b> [Цена] ([Изменение]%)
    
    🤖 <b>[ТИКЕР]</b> | [Сектор]
    💰 Цена: [Цена] ([Изменение]%) | 🏦 [Биржа]
    ▪️ <b>Драйвер:</b> [Краткая причина]
    🎯 <b>План:</b> Вход (Market) | TP (+5%) | SL (-3%)
    
    (Повторить для остальных)
    
    ⚖️ <b>Disclaimer:</b> Не финансовый совет. DYOR.
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
        indicators = {
            "rsi": "N/A", "trend": "UNKNOWN", 
            "s1": "N/A", "r1": "N/A", 
            "s1_score": 0.0, "r1_score": 0.0,
            "regime": "N/A", "safety": "N/A"
        }

    # Данные для AI
    curr_price = price_data.get('price', 'N/A')
    source = price_data.get('source', 'Unknown')
    change = price_data.get('change_24h', 'N/A')
    
    # ГИБРИДНЫЙ ПРОМТ (Liquidity Hunter + Trend Level PRO Math)
    prompt = f"""
    Ты — профессиональный аналитик Liquidity Hunter (Smart Money).
    ТАЙМФРЕЙМ: 30 минут (Intraday). Используй ТОЛЬКО предоставленные уровни.

    ВХОДНЫЕ ДАННЫЕ:
    • Актив: {ticker.upper()} | Цена: ${curr_price}
    • RSI (14): {indicators['rsi']} | Тренд: {indicators['trend']}
    • Режим рынка: {indicators['regime']} | Безопасность: {indicators['safety']}
    • Поддержка S1: ${indicators['s1']} (Score: {indicators['s1_score']})
    • Сопротивление R1: ${indicators['r1']} (Score: {indicators['r1_score']})

    ЖЁСТКИЕ ПРАВИЛА LIQUIDITY HUNTER:

    1. РЕЖИМ РЫНКА — ЭТО ВСЁ:
       • COMPRESSION + RISKY = ТОЛЬКО внутри диапазона S1-R1 (отбой).
       • EXPANSION + SAFE = Можно торговать пробои с ретестами.

    2. SCORE УРОВНЯ ОПРЕДЕЛЯЕТ СИЛУ:
       • Score ≥ 3.0 = Strong (высокая вероятность отбоя).
       • Score 1.0-2.9 = Medium (нужна конфирмация).
       • Score < 1.0 = Weak (использовать только как ориентир).

    3. ТОЧКА ВХОДА ДОЛЖНА БЫТЬ РЕАЛИСТИЧНОЙ:
       • Макс. отклонение от текущей цены: 3-5%.
       • Вход: Либо limit на уровне, либо stop-limit на пробое.

    АНАЛИЗИРУЙ ПО ЭТОЙ СТРУКТУРЕ:

    📊 <b>{ticker.upper()} | Liquidity Hunter (M30)</b>
    💰 Цена: <code>${curr_price}</code> ({change}%)

    🎯 <b>КЛЮЧЕВЫЕ УРОВНИ:</b>
    • <b>S1:</b> <code>${indicators['s1']}</code> (Score: {indicators['s1_score']})
    • <b>R1:</b> <code>${indicators['r1']}</code> (Score: {indicators['r1_score']})

    📡 <b>MARKET CONTEXT:</b>
    • Режим: <b>{indicators['regime']}</b> | Риск: <b>{indicators['safety']}</b>
    • Тренд: <b>{indicators['trend']}</b> | RSI: <b>{indicators['rsi']}</b>

    1️⃣ <b>СТРУКТУРА РЫНКА (M30)</b>
    ▪️ <b>Фаза:</b> [Накопление/Распределение/Тренд?]
    ▪️ <b>Анализ:</b> [Где цена относительно уровней? Что говорит RSI?]

    2️⃣ <b>LIQUIDITY HUNTER LOGIC</b>
    ▪️ <b>Ловушка ММ:</b> [Куда MM поведет цену для сбора стопов? Выше R1 или ниже S1?]
    ▪️ <b>Сценарий:</b> [Range-bound в COMPRESSION или пробой в EXPANSION?]

    3️⃣ <b>P-SCORE & РИСКИ</b>
    ▪️ <b>P-Score:</b> <b>[РАССЧИТАЙ]%</b>
       Формула: 50% база
       {'+20%' if indicators['regime'] == 'EXPANSION' and indicators['safety'] == 'SAFE' else '-30%' if indicators['regime'] == 'COMPRESSION' and indicators['safety'] == 'RISKY' else '±0%'} за режим
       {'+15%' if indicators['s1_score'] >= 3.0 or indicators['r1_score'] >= 3.0 else '-20%' if indicators['s1_score'] < 1.0 or indicators['r1_score'] < 1.0 else '±0%'} за силу уровня
    ▪️ <b>Флаги риска:</b> [Fake-out, High RSI, Слабые уровни?]

    🎯 <b>СНАЙПЕРСКИЙ ПЛАН</b>
    {'🔵' if indicators['trend'] == 'BULLISH' else '🔴'} <b>Тип:</b> [LONG/SHORT] (Limit)
    🚪 <b>Вход:</b> <code>[Цена]</code> 
       • Для LONG: limit на S1 или stop-limit при пробое R1
       • Для SHORT: limit на R1 или stop-limit при пробое S1

    🛡 <b>Стоп-лосс:</b>
       🔴 <code>[Цена]</code> (За зоной ликвидности, на 1.5×ATR от входа)

    ✅ <b>Тейк-профиты:</b>
       🟢 TP1: <code>[Цена]</code> (20-30% от диапазона)
       🟢 TP2: <code>[Цена]</code> (50-60% от диапазона)  
       🟢 TP3: <code>[Цена]</code> (Целевой уровень)

    ⚖️ <b>Совет:</b> Риск 1% на сделку. В COMPRESSION уменьшить размер в 2 раза.
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

# --- 4. MARKET SCAN (HIDDEN ACCUMULATION) ---
async def get_market_scan():
    # 1. Получаем полные данные рынка (все сектора)
    real_market_data, valid_tickers = await fetch_real_market_data()
    if not valid_tickers:
        return "⚠️ Ошибка: Не удалось получить данные с бирж."

    client = AsyncOpenAI(api_key=os.getenv("OPENROUTER_API_KEY"), base_url="https://openrouter.ai/api/v1")
    
    # 2. ПРОМТ "HIDDEN ACCUMULATION"
    prompt = f"""
    Ты — алгоритмический скринер Market Lens (Liquidity Hunter).
    ДАТА: {datetime.utcnow().strftime("%Y-%m-%d")}.
    
    ПОЛНЫЙ СПИСОК РЫНКА (ДАННЫЕ):
    {real_market_data}
    
    ЗАДАЧА:
    Проанализируй данные (Цену, Изменение, Объем) и найди ТОП-5 монет, где происходит "Скрытая Аккумуляция" или подготовка к движению.
    Критерии: Аномальный объем при малом изменении цены, удержание важных уровней, расхождение с BTC.
    
    ФОРМАТ ОТВЕТА (СТРОГО HTML, Clean UI):
    1. ИСПОЛЬЗУЙ ТОЛЬКО HTML ТЕГИ (`<b>`, `<i>`).
    2. ЗАПРЕЩЕНО Markdown.
    3. Стиль: Профессиональный скринер.

    СТРУКТУРА ОТВЕТА:

    🔭 <b>Market Lens | Hidden Accumulation Scan</b>
    📅 Дата: {datetime.utcnow().strftime("%d.%m.%Y")} | 🏦 Market: Global

    📊 <b>Топ-5 Лидеров (Heatmap):</b>
    1. <b>[TICKER]</b> — [Причина одним словом, например: "Рост объема"] (P-Score: [XX]%)
    2. <b>[TICKER]</b> — ...
    (до 5)
    
    ---
    
    (ДЕТАЛЬНЫЙ РАЗБОР ДЛЯ КАЖДОЙ ИЗ 5 МОНЕТ):
    
    🤖 <b>1. [TICKER] | [Сектор]</b>
    💰 Цена: [Цена] ([Изменение]%) | Vol: [Объем]
    ▪️ <b>Сигнал:</b> [Почему это скрытая аккумуляция? Опиши паттерн]
    📉 <b>Техника:</b> [Тренд / Уровни]
    ⚠️ <b>Риски:</b> [Чего опасаться]
    
    (Повторить для остальных)
    
    ---
    
    💡 <b>Действия трейдера:</b>
    
    1️⃣ <b>Хотите точный вход?</b>
    Используйте снайпер-модуль для расчета лимиток:
    👉 Скопируйте: <code>/sniper [TICKER]</code>
    
    2️⃣ <b>Сомневаетесь в проекте?</b>
    Закажите глубокий VC-аудит (разлоки, риски):
    👉 Скопируйте: <code>/audit [TICKER]</code>
    
    ⚖️ <b>Disclaimer:</b> Сгенерировано AI. DYOR.
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
        logger.error(f"Scan Error: {e}")
        return f"⚠️ Ошибка сканера: {e}"

# --- COMPATIBILITY LAYER ---
# Старые функции для совместимости с main.py
async def get_crypto_analysis(ticker, name, language="ru"):
    """Legacy function - redirects to analyze_token_fundamentals"""
    return await analyze_token_fundamentals(ticker)