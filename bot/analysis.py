import os
import re
import time
from datetime import datetime
from dotenv import load_dotenv
from openai import AsyncOpenAI
from bot.market_metrics import get_market_regime
from bot.technical_analysis import TechnicalAnalyzer

load_dotenv()

# Настройка клиента (DeepSeek через OpenRouter)
client = AsyncOpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1"
)

MODEL_NAME = "deepseek/deepseek-chat"

# --- КЭШИРОВАНИЕ ---
ANALYSIS_CACHE = {}
CACHE_TTL = 300
DAILY_CACHE_TTL = 1800

# --- СЕКТОРЫ ДЛЯ МОНЕТ (корректный словарь) ---
SECTOR_MAP = {
    # AI
    "FET": "AI",
    "AGIX": "AI",
    "RNDR": "AI",
    "AKT": "AI",
    "TAO": "AI",
    "GRT": "AI",
    "Bittensor": "AI",
    # Layer-2
    "ARB": "Layer-2",
    "OP": "Layer-2",
    "STRK": "Layer-2",
    "MANTA": "Layer-2",
    "ZK": "Layer-2",
    "IMX": "Layer-2",
    "METIS": "Layer-2",
    # RWA
    "ONDO": "RWA",
    "CFG": "RWA",
    "POLYX": "RWA",
    "PROPC": "RWA",
    # DePIN
    "HNT": "DePIN",
    "WLD": "DePIN",
    "LPT": "DePIN",
    "DIMO": "DePIN",
    "TRAC": "DePIN",
    # GameFi
    "SAND": "GameFi",
    "MANA": "GameFi",
    "AXS": "GameFi",
    "GALA": "GameFi",
    "ENJ": "GameFi",
    # Memes
    "PEPE": "Meme",
    "SHIB": "Meme",
    "WIF": "Meme",
    "BONK": "Meme",
    "FLOKI": "Meme",
    # Infrastructure
    "LINK": "Infrastructure",
    "DOT": "Infrastructure",
    "ADA": "Infrastructure",
    "SOL": "Infrastructure",
    "AVAX": "Infrastructure",
    "MATIC": "Infrastructure",
}

def get_sector(ticker):
    """Определяет сектор по тикеру."""
    return SECTOR_MAP.get(ticker, "Other")

def clean_html(text):
    if not text: return ""
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    text = text.replace("```", "").replace("markdown", "").replace("html", "")
    text = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"###\s*(.*)", r"<b>\1</b>", text)
    text = re.sub(r"##\s*(.*)", r"<b>\1</b>", text)
    text = text.replace("* ", "• ").replace("- ", "• ")
    return text.strip()

# --- 1. ФУНДАМЕНТАЛЬНЫЙ АУДИТ ---
async def get_crypto_analysis(ticker, full_name, lang="ru"):
    cache_key = f"{ticker}_audit_{lang}"
    if cache_key in ANALYSIS_CACHE:
        timestamp, cached_text = ANALYSIS_CACHE[cache_key]
        if time.time() - timestamp < CACHE_TTL:
            return cached_text

    system_prompt = f"""
    Ты — Senior VC Analyst (Венчурный аналитик).
    Твоя задача — провести жесткий Due Diligence проекта {full_name} ({ticker}).
    Стиль: Критический, без воды, только факты и риски.

    СТРУКТУRA ОТВЕТА (Telegram HTML):
    🛡 <b>{ticker} — Фундаментальный Аудит</b>

    1️⃣ <b>Токеномика и Инфляция</b>
    • <b>FDV vs Market Cap:</b> (Есть ли навес токенов?).
    • <b>Разлоки (Unlocks):</b> (Давят ли фонды на стакан?).
    • <b>Utility:</b> (Реальная польза токена или фантик?).

    2️⃣ <b>Продукт и Метрики</b>
    • <b>Конкуренты:</b> (Кто сильнее в нише?).
    • <b>Активность:</b> (GitHub, TVL, реальные юзеры).

    3️⃣ <b>Вердикт и Прогноз</b>
    • <b>Потенциал:</b> (Взгляд на 6-12 месяцев).
    • <b>Риск:</b> [НИЗКИЙ / СРЕДНИЙ / ВЫСОКИЙ].
    """

    try:
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "You are a strict VC analyst. Use Telegram HTML tags (<b>, <i>)."},
                {"role": "user", "content": system_prompt}
            ],
            temperature=0.2,
            extra_headers={"HTTP-Referer": "https://telegram.org", "X-Title": "CryptoBot"}
        )
        result = clean_html(response.choices[0].message.content)
        ANALYSIS_CACHE[cache_key] = (time.time(), result)
        return result
    except Exception as e:
        return f"⚠️ Ошибка аудита: {str(e)}"

from bot.prices import get_market_summary, get_crypto_price

# --- 2. СНАЙПЕР (SMART MONEY / SMC) — УЛУЧШЕННАЯ ВЕРСИЯ ---
async def get_sniper_analysis(ticker, lang="ru"):
    cache_key = f"{ticker}_sniper_{lang}"
    if cache_key in ANALYSIS_CACHE:
        timestamp, cached_text = ANALYSIS_CACHE[cache_key]
        if time.time() - timestamp < CACHE_TTL:
            return cached_text

    # Получаем цену и название
    price_data, _ = await get_crypto_price(ticker)
    if not price_data:
        return f"⚠️ Не удалось найти цену для тикера {ticker}."
    
    full_name = price_data['name']
    price = float(price_data['price'])

    # Получаем уровни поддержки/сопротивления
    ta = TechnicalAnalyzer()
    levels_context = ""
    try:
        # Fetch candles
        df = await ta.fetch_candles(ticker, '1h', limit=500)
        if not df.empty:
            df = ta.calculate_levels(df, timeframe='1h')
            levels = ta.get_active_levels()
            
            # Sort by distance to current price
            for lvl in levels:
                lvl['dist'] = abs(lvl['price'] - price)
            levels.sort(key=lambda x: x['dist'])
            
            top_levels = levels[:3]
            if top_levels:
                levels_context = "HARD DATA CONTEXT (Algorithmic Pivot Zones):\n"
                for i, lvl in enumerate(top_levels):
                    l_type = "RESISTANCE" if lvl['is_res'] else "SUPPORT"
                    levels_context += f"- {l_type} @ ${lvl['price']:.4f} (Touches: {lvl['count']}, ATR: {lvl['atr']:.4f})\n"
                levels_context += "INSTRUCTION: Строго опирайся на предоставленные уровни (Algorithmic Zones). Не выдумывай цены. Формируй торговый план от этих уровней.\n"
                levels_context += "Когда указываешь уровни S1/R1, пиши рядом в скобках: '(Trend Level PRO Indicator)'.\n"
                levels_context += "В разделе 'Снайперский план' пиши: 'Вход согласован с алгоритмической зоной Trend Level PRO'."
    except Exception as e:
        print(f"Error getting technical levels: {e}")
    finally:
        await ta.close()

    system_prompt = f"""
РОЛЬ: Профессиональный SMC-трейдер и аналитик поведения маркетмейкеров (Liquidity Hunter 2.0).
ТИКЕР: {ticker}
ПОЛНОЕ НАЗВАНИЕ: {full_name}
ТЕКУЩАЯ ЦЕНА: ${price} — ЭТО ФАКТ. ИСПОЛЬЗУЙ ТОЛЬКО ЕГО.

{levels_context}

🎯 ЗАДАЧА:
Создать снайперский торговый сетап ТОЛЬКО на основе реальной цены выше.  
НЕ ПРИДУМЫВАЙ ЦЕНЫ. НЕ ПРЕДЛАГАЙ MARKET-ОРДЕРА.  
Вход должен быть ЛИМИТНЫМ и НИЖЕ текущей цены для LONG (или ВЫШЕ — для SHORT, если уместно).

❗️ ОБЯЗАТЕЛЬНЫЕ ПРАВИЛА:
1. Если цена растёт — ищи откат к зоне спроса.
2. Если цена падает — ищи отскок от зоны поддержки или ловушку для шортов.
3. Все уровни (Entry, TP, SL) — числа, основанные на цене ${price}.
4. Не используй markdown. Только Telegram-HTML: <b>, <i>, •, \n.
5. Если есть данные Algorithmic Pivot Zones, ОБЯЗАТЕЛЬНО используй их.
6. Везде упоминай, что анализ основан на "Trend Level PRO".
7. Определи горизонт сделки (Intraday/Swing) на основе расстояния до TP3. Если уровни близко (1-2%) -> Intraday (6-24 часа). Если уровни далеко (5-10%) -> Swing (2-5 дней).

📊 СТРУКТУРА ОТВЕТА (ОБЯЗАТЕЛЬНО!):

📊 <b>{ticker}/USDT — Smart Money Sniper Setup</b>
💵 <b>Цена сейчас:</b> ${price}
⏳ <b>Горизонт:</b> [Intraday / Swing] (~X-Y ч/дн)

1️⃣ <b>Структура рынка (1H/4H/D)</b>
• <b>Тренд:</b> (Восходящий / Нисходящий / Боковик)
• <b>Фаза:</b> (Аккумуляция / Распределение / Импульс)
• <b>Ключевые уровни:</b>
  └ S1: $... (Trend Level PRO Indicator)
  └ R1: $... (Trend Level PRO Indicator)

2️⃣ <b>Ликвидность & MM-активность</b>
• <b>Цель ММ:</b> (Сбор стопов шортов / Выбивание лонгов)
• <b>Зона интереса (POI):</b> $... (где стоит "плита" покупателя/продавца)
• <b>Признаки:</b> (Spoofing / Iceberg orders / False breakout / Divergence)

3️⃣ <b>Поток капитала</b>
• <b>OI + Funding:</b> (Рост OI при консолидации? Нейтральное/отрицательное funding?)
• <b>CVD/Delta:</b> (Наращивание лонгов при падении = накопление?)

4️⃣ <b>Sentiment Snapshot</b>
• <b>Long/Short ratio:</b> (Перешорчено → памп-потенциал?)
• <b>Соцсети:</b> (Хайп или тишина?)

5️⃣ <b>Фундаментал (кратко)</b>
• <b>Сектор:</b> (AI, L2, Gaming и т.д.)
• <b>Катализатор:</b> (Апдейт, листинг, партнерство — если известен)

6️⃣ <b>P-Score</b>: [70–90%] — вероятность исполнения сценария

7️⃣ <b>Liquidity Map</b>
• <b>Ликвидации вверх:</b> $... (стопы шортов)
• <b>Ликвидации вниз:</b> $... (стопы лонгов)

🎯 <b>Снайперский план (Limit Order)</b>
<i>Мы не догоняем зелёные свечи. Мы ждем цену в нашей зоне.</i>

🔹 <b>Тип:</b> LONG (Limit) — ИЛИ SHORT, если дамп очевиден
🔹 <b>Вход:</b> $... (ТОЛЬКО ниже ${price} для LONG!)
🔹 <b>Обоснование:</b> (Напр.: "Тест ордер-блока + бычья дивергенция на 4H" или "Реакция на Algorithmic Pivot Zone")

✅ <b>Take Profit:</b>
• <b>TP1:</b> $... (+3–5%)
• <b>TP2:</b> $... (+8–12%)
• <b>TP3:</b> $... (выход на ликвидность выше)

⛔️ <b>Stop-Loss:</b> $... (за структурой / за POI)

⚖️ <b>Совет:</b> (Психология: "Не входи на FOMO", "Жди подтверждение закрытия свечи" и т.д.)

👇 <i>Для глубокого фундаментального разбора: /audit {ticker}</i>
"""

    try:
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a precision-focused Smart Money trader. "
                        "Use ONLY the provided current price. NEVER hallucinate numbers. "
                        "Output in Telegram-compatible HTML (<b>, <i>). NO markdown. "
                        "Suggest LIMIT orders ONLY. For LONG, entry MUST be BELOW current price. "
                        "If Algorithmic Pivot Zones are provided, prioritize them."
                    )
                },
                {"role": "user", "content": system_prompt}
            ],
            temperature=0.15,
            extra_headers={
                "HTTP-Referer": "https://telegram.org",
                "X-Title": "CryptoBot"
            }
        )
        result = clean_html(response.choices[0].message.content)
        ANALYSIS_CACHE[cache_key] = (time.time(), result)
        return result
    except Exception as e:
        return f"⚠️ Ошибка снайпера: {str(e)}"

# --- 3. DAILY BRIEFING — ГЛУБОКИЙ АНАЛИЗ ПО СЕКТОРАМ ---
async def get_daily_briefing(market_data=None):
    date_str = datetime.now().strftime("%d.%m.%Y")
    cache_key = f"daily_briefing_{date_str}"
    
    if cache_key in ANALYSIS_CACHE:
        timestamp, cached_text = ANALYSIS_CACHE[cache_key]
        if time.time() - timestamp < DAILY_CACHE_TTL:
            return cached_text

    # Если market_data не передан, получаем его
    if not market_data:
        market_data = await get_market_summary()

    # Получаем Market Regime
    regime_data = await get_market_regime()
    regime_status = regime_data.get('status', 'NEUTRAL') if regime_data else "NEUTRAL"
    regime_z = regime_data.get('z_score', 0.0) if regime_data else 0.0
    
    regime_warning = ""
    if regime_status == "COMPRESSION":
        regime_warning = f"⚠️ <b>ВНИМАНИЕ: Рынок в фазе СЖАТИЯ (Z-Score: {regime_z:.2f}). Высокий риск взрывной волатильности!</b>\n\n"
    elif regime_status == "EXPANSION":
        regime_warning = f"ℹ️ <b>Рынок в фазе РАСШИРЕНИЯ (Z-Score: {regime_z:.2f}). Тренд уже развился.</b>\n\n"

    top_coins_raw = market_data.get('top_coins', '1. BTC: $96000\n2. ETH: $2800\n3. SOL: $140')
    btc_dom = market_data.get('btc_dominance', '56.5')

    # Парсим монеты: [("BTC", "96000"), ("ETH", "2800"), ("SOL", "140")]
    coins = []
    for line in top_coins_raw.split('\n'):
        if ':' in line:
            parts = line.split(':')
            if len(parts) >= 2:
                ticker_part = parts[0].strip()
                # Извлекаем тикер (последнее слово перед ":")
                ticker = ticker_part.split()[-1] if ticker_part else ""
                price_part = parts[1].strip().replace('$', '').replace(',', '')
                try:
                    price = float(price_part)
                    fmt_price = f"{price:.8f}" if price < 0.01 else (f"{price:.4f}" if price < 1 else f"{price:.2f}")
                    coins.append((ticker, fmt_price))
                except ValueError:
                    continue

    if not coins:
        return "⚠️ Не удалось распознать монеты для анализа."

    # Формируем входной промпт для LLM
    coins_context = "\n".join([f"- {ticker}: ${price}" for ticker, price in coins])
    sectors_mentioned = set(get_sector(ticker) for ticker, _ in coins)
    sectors_list = ", ".join(sorted(sectors_mentioned))

    system_prompt = f"""
    Ты — главный аналитик крипто-фонда. Сегодня {date_str}. BTC Dom: {btc_dom}%.
    
    Рынок сейчас в состоянии {regime_status}.
    {regime_warning}
    
    ВХОДНЫЕ ДАННЫЕ (ТОЛЬКО ЭТИ МОНЕТЫ — НЕ ПРИДУМЫВАЙ ДРУГИЕ):
    {coins_context}
    
    ЗАДАЧА:
    Проведи глубокий анализ этих 3 монет по шаблону "Поиск монет по секторам".  
    Для каждой монеты:
    1. Определи её сектор (AI, Layer-2, RWA, DePIN, GameFi и т.д.).
    2. Проведи анализ готовности к пампу, используя логику маркетмейкеров.
    3. Дай фьючерсный сигнал ТОЛЬКО в направлении LONG (если уместно).
    
    ❗️ ЖЁСТКОЕ ПРАВИЛО:  
    Все цены — из списка выше. НЕ ПРИДУМЫВАЙ ЦЕНЫ.  
    Если монета не подходит под памп — честно так и напиши.
    Если статус COMPRESSION — начни ответ с предупреждения о рисках волатильности.
    ОБЯЗАТЕЛЬНО используй формат "Макро-режим (Trend Level Logic): [STATUS]" в заголовке.
    
    ФОРМАТ ВЫВОДА (Telegram HTML):
    
    🌅 <b>Market Pulse: {date_str}</b>
    📊 <b>Макро-режим (Trend Level Logic):</b> {regime_status} (BTC Dom {btc_dom}%)
    🔥 <b>Активные сектора:</b> {sectors_list}
    
    💎 <b>Watchlist по секторам:</b>
    
    1. <b>{coins[0][0]}</b> — [Сектор]
       💵 <b>Цена:</b> ${coins[0][1]}
       • Ключевые уровни: ...
       • Готовность к пампу: ...
       • Фундаментал: ...
       • 🎯 <b>Сигнал:</b> LONG
         └ Вход: $...
         └ TP1/TP2/TP3: $... / $... / $...
         └ SL: $...
    
    2. <b>{coins[1][0]}</b> — [Сектор]
       ...
    
    3. <b>{coins[2][0]}</b> — [Сектор]
       ...
    
    👇 <i>Детальный расчет сделки: /sniper [тикер]</i>
    """

    try:
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "You are a strict crypto analyst. Use ONLY provided prices. Do NOT hallucinate. Output in Telegram HTML."},
                {"role": "user", "content": system_prompt}
            ],
            temperature=0.2,
            extra_headers={"HTTP-Referer": "https://telegram.org", "X-Title": "CryptoBot"}
        )
        result = clean_html(response.choices[0].message.content)
        ANALYSIS_CACHE[cache_key] = (time.time(), result)
        return result
    except Exception as e:
        return f"⚠️ Ошибка брифинга: {str(e)}"