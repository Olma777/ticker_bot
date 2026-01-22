import os
import re
import time
from datetime import datetime
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

# Настройка клиента (DeepSeek через OpenRouter)
client = AsyncOpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url="https://openrouter.ai/api/v1"
)

MODEL_NAME = "deepseek/deepseek-chat"

# --- КЭШИРОВАНИЕ (Чтобы экономить деньги и время) ---
ANALYSIS_CACHE = {}
CACHE_TTL = 300       # 5 минут для Снайпера и Аудита
DAILY_CACHE_TTL = 1800 # 30 минут для Дейли брифинга

def clean_html(text):
    """
    Очищает ответ нейросети, оставляя только валидные HTML-теги для Telegram.
    Убирает маркдаун, лишние символы и '```html'.
    """
    if not text: return ""
    
    # Убираем обертки кода
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    text = text.replace("```", "").replace("markdown", "").replace("html", "")
    
    # Конвертируем Markdown жирный в HTML
    text = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"###\s*(.*)", r"<b>\1</b>", text)
    text = re.sub(r"##\s*(.*)", r"<b>\1</b>", text)
    
    # Конвертируем списки
    text = text.replace("* ", "• ").replace("- ", "• ")
    
    return text.strip()

# --- 1. ФУНДАМЕНТАЛЬНЫЙ АУДИТ (VC MODE) ---
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

    СТРУКТУРА ОТВЕТА (Telegram HTML):
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

# --- 2. СНАЙПЕР (SMART MONEY / SMC) ---
async def get_sniper_analysis(ticker, full_name, price, lang="ru"):
    cache_key = f"{ticker}_sniper_{lang}"
    if cache_key in ANALYSIS_CACHE:
        timestamp, cached_text = ANALYSIS_CACHE[cache_key]
        if time.time() - timestamp < CACHE_TTL:
            return cached_text

    system_prompt = f"""
    РОЛЬ: Профессиональный SMC Трейдер (Liquidity Hunter).
    ЗАДАЧА: Найти точку входа для {ticker}.
    ТЕКУЩАЯ ЦЕНА: ${price}.

    ПРАВИЛА ТОРГОВЛИ (СТРОГО):
    1. Ищи вход ОТ ЛИКВИДНОСТИ (Support/Demand). 
    2. ЗАПРЕЩЕНО предлагать вход на пробой (Breakout) выше текущей цены.
    3. Если цена выросла — жди откат.
    4. Точка входа должна быть ЛИМИТНОЙ (Ниже текущей для Лонга).

    ФОРМАТ ОТВЕТА (HTML):
    📊 <b>{ticker}/USDT — Smart Money Setup</b>
    💵 <b>Цена сейчас:</b> ${price}

    1️⃣ <b>Структура рынка</b>
    • <b>Тренд:</b> (Восходящий/Нисходящий/Боковик).
    • <b>Зона интереса (POI):</b> (Где стоит "плита" покупателя?).
    • <b>Ликвидность:</b> (Где скопились стопы?).

    🎯 <b>Торговый План (Limit Order)</b>
    <i>Мы не догоняем зелёные свечи. Мы ждем цену в нашей зоне.</i>

    🔹 <b>Тип:</b> LONG (Limit)
    🔹 <b>Вход:</b> (Цена НИЖЕ текущей).
    🔹 <b>Обоснование:</b> (Например: "Тест ордер-блока" или "Снятие ликвидности").

    ✅ <b>Цели (Take Profit):</b>
    • <b>TP1:</b> ...
    • <b>TP2:</b> ...

    ⛔️ <b>Стоп-лосс:</b>
    • <b>Цена:</b> ... (За лоем/структурой).

    ⚖️ <b>Совет:</b> (Психология сделки).
    """

    try:
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "You are a Smart Money trader. Suggest Limit entries only. Use HTML bold tags."},
                {"role": "user", "content": system_prompt}
            ],
            temperature=0.2,
            extra_headers={"HTTP-Referer": "https://telegram.org", "X-Title": "CryptoBot"}
        )
        result = clean_html(response.choices[0].message.content)
        ANALYSIS_CACHE[cache_key] = (time.time(), result)
        return result
    except Exception as e:
        return f"⚠️ Ошибка снайпера: {str(e)}"

# --- 3. DAILY BRIEFING (FIXED PRICES - БЕЗ ГАЛЛЮЦИНАЦИЙ) ---
async def get_daily_briefing(market_data):
    date_str = datetime.now().strftime("%d.%m.%Y")
    cache_key = f"daily_briefing_{date_str}"
    
    if cache_key in ANALYSIS_CACHE:
        timestamp, cached_text = ANALYSIS_CACHE[cache_key]
        if time.time() - timestamp < DAILY_CACHE_TTL:
            return cached_text

    # Получаем строку с реальными ценами из prices.py
    # Пример: "ROSE (Price: $0.062), AXS (Price: $7.45)"
    top_coins_data = market_data.get('top_coins', 'Нет данных')

    system_prompt = f"""
    РОЛЬ: Ведущий аналитик крипто-фонда.
    ДАТА: {date_str}
    МАКРО: BTC Dom: {market_data.get('btc_dominance')}%
    
    ВХОДНЫЕ ДАННЫЕ (ТОП МОНЕТЫ И ИХ РЕАЛЬНЫЕ ЦЕНЫ):
    {top_coins_data}

    ЗАДАЧА:
    Составь утренний брифинг по этим 3 монетам.
    
    ❗️ ВАЖНЕЙШЕЕ ПРАВИЛО:
    Ты ОБЯЗАН использовать цены из списка выше как ТЕКУЩИЕ. 
    Рассчитывай цели (Take Profit) и уровни входа (Entry) ТОЛЬКО от этих цен.
    НЕ ПРИДУМЫВАЙ ЦЕНЫ ИЗ ГОЛОВЫ.

    ФОРМАТ ВЫВОДА (HTML):
    🌅 <b>Market Pulse: {date_str}</b>

    📊 <b>Макро:</b> {{BULLISH / NEUTRAL}} (BTC Dom {market_data.get('btc_dominance')}%)
    {{Краткий вывод по рынку в целом}}.

    🔥 <b>Сектор дня:</b> (Определи общий сектор этих монет, например AI, Gaming или L1).

    💎 <b>Watchlist (Охота за ликвидностью):</b>

    1. <b>#TICKER</b> 📈 LONG (или SHORT)
       💵 <b>Цена:</b> (Вставь цену из входных данных!)
       └ <i>Сетап:</i> (Например: Сбор ликвидности / Тест поддержки).
       └ <i>План:</i> Ждем (Цена входа рядом с текущей). Цель (Реалистичная, +5-15%).

    2. <b>#TICKER</b> ...
       ...

    3. <b>#TICKER</b> ...
       ...
    
    👇 <i>Детальный расчет сделки: /sniper [тикер]</i>
    """

    try:
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "You are a strict crypto analyst. Do not hallucinate prices. Use ONLY provided input data."},
                {"role": "user", "content": system_prompt}
            ],
            temperature=0.2, # Низкая температура для строгости фактов
            extra_headers={"HTTP-Referer": "https://telegram.org", "X-Title": "CryptoBot"}
        )
        result = clean_html(response.choices[0].message.content)
        ANALYSIS_CACHE[cache_key] = (time.time(), result)
        return result

    except Exception as e:
        return f"⚠️ Ошибка брифинга: {str(e)}"