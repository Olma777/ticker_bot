import os
import re
import time
from datetime import datetime
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

client = AsyncOpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url="https://openrouter.ai/api/v1"
)

MODEL_NAME = "deepseek/deepseek-chat"

# --- КЭШИРОВАНИЕ ---
ANALYSIS_CACHE = {}
CACHE_TTL = 300       
DAILY_CACHE_TTL = 1800 

def clean_html(text):
    """
    Очистка текста для Telegram HTML.
    """
    if not text: return ""
    # Удаляем лишнее
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    text = text.replace("```", "").replace("markdown", "")
    
    # Конвертация заголовков Markdown в жирный текст
    text = re.sub(r"###\s*(.*)", r"<b>\1</b>", text)
    text = re.sub(r"##\s*(.*)", r"<b>\1</b>", text)
    text = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", text)
    
    # Списки
    text = text.replace("* ", "• ").replace("- ", "• ")
    
    return text.strip()

# --- 1. АУДИТ (VC MODE) ---
async def get_crypto_analysis(ticker, full_name, lang="ru"):
    cache_key = f"{ticker}_audit_{lang}"
    if cache_key in ANALYSIS_CACHE:
        timestamp, cached_text = ANALYSIS_CACHE[cache_key]
        if time.time() - timestamp < CACHE_TTL:
            return cached_text

    system_prompt = f"""
    Ты — Senior VC Analyst. Твоя задача — фундаментальный разбор {full_name} ({ticker}).
    Стиль: Строгий, критический, без воды.
    
    Структура ответа (Telegram HTML):
    🛡 <b>{ticker} — Фундаментальный Аудит</b>

    1️⃣ <b>Метрики и Токеномика</b>
    • <b>Utility:</b> Реальная польза токена?
    • <b>Unlock:</b> Есть ли риски давления продавцов?
    • <b>Whales:</b> Централизация эмиссии.

    2️⃣ <b>Продукт и Рынок</b>
    • Конкурентные преимущества.
    • Активность разработки (GitHub) и сети (TVL/DAU).

    ⚖️ <b>ВЕРДИКТ:</b>
    • Риск: [НИЗКИЙ/СРЕДНИЙ/ВЫСОКИЙ]
    • Резюме: (Скам, Гем или Утиль).
    """

    try:
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "system", "content": "You are a VC analyst."}, {"role": "user", "content": system_prompt}],
            temperature=0.2,
            extra_headers={"HTTP-Referer": "[https://telegram.org](https://telegram.org)", "X-Title": "CryptoBot"}
        )
        result = clean_html(response.choices[0].message.content)
        ANALYSIS_CACHE[cache_key] = (time.time(), result)
        return result
    except Exception as e:
        return f"⚠️ Ошибка: {str(e)}"

# --- 2. СНАЙПЕР (SMART MONEY / SMC MODE) ---
async def get_sniper_analysis(ticker, full_name, price, lang="ru"):
    cache_key = f"{ticker}_sniper_{lang}"
    if cache_key in ANALYSIS_CACHE:
        timestamp, cached_text = ANALYSIS_CACHE[cache_key]
        if time.time() - timestamp < CACHE_TTL:
            return cached_text

    # ПРОМПТ, ОСНОВАННЫЙ НА ТВОЕМ ПРИМЕРЕ
    system_prompt = f"""
    РОЛЬ: Ты — Профессиональный SMC Трейдер (Smart Money Concepts).
    ЗАДАЧА: Дать торговый сетап по {ticker} (Текущая цена: ${price}).
    
    ЛОГИКА АНАЛИЗА (СТРОГО):
    1. Мы торгуем ЛИКВИДНОСТЬ. Не предлагай покупать на хаях.
    2. Если цена в середине диапазона — ищи вход НИЖЕ (от поддержки/ордерблока).
    3. Используй термины: OBV, Accumulation, Liquidity Sweep, Range, Break of Structure.
    4. Твой анализ должен выглядеть как инсайд из закрытого канала.

    ФОРМАТ ВЫВОДА (HTML):

    📊 <b>{ticker}/USDT — Анализ Smart Money</b>
    💵 <b>Цена:</b> ${price}

    1️⃣ <b>Ключевые уровни (S/R)</b>
    • <b>Resistance (Продавец):</b> (Уровень на 3-5% выше текущей цены). Зона интереса медведей.
    • <b>Support (Покупатель):</b> (Уровень на 2-5% ниже текущей цены). Здесь лежат лимиты на откуп.
    • <b>Диапазон:</b> (Определи текущий торговый канал).

    2️⃣ <b>Фаза рынка и Действия ММ</b>
    • <b>Фаза:</b> (Например: Аккумуляция в боковике / Сбор ликвидности).
    • <b>OBV и Объемы:</b> (Сымитируй анализ: "Скрытый набор позиций" или "Распределение").
    • <b>Ловушка ММ:</b> Где маркетмейкер запер толпу? (Например: "Засадили лонгистов на верхах").

    🎯 <b>Торговый Сетап (Свинг-Лонг)</b>
    <i>Мы не входим по рынку. Мы ждем цену в нашей зоне интереса.</i>

    🔹 <b>Вход (Limit):</b> (Цена НИЖЕ текущей! Зона Support/Order Block).
    🔹 <b>Стоп-лосс:</b> (За уровнем поддержки/ликвидности).
    🔹 <b>Тейк-профит 1:</b> (Середина канала).
    🔹 <b>Тейк-профит 2:</b> (Верхняя граница / Ликвидность сверху).

    ⚖️ <b>Резюме:</b>
    (Короткий вывод: Ждем спуска к уровню входа. Не фомо).
    """

    try:
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "You are a Smart Money Crypto Trader. Use HTML bold tags for formatting. Never suggest entering at the top of a range."},
                {"role": "user", "content": system_prompt}
            ],
            temperature=0.2, # Низкая температура для четкости
            extra_headers={"HTTP-Referer": "[https://telegram.org](https://telegram.org)", "X-Title": "CryptoBot"}
        )
        result = clean_html(response.choices[0].message.content)
        ANALYSIS_CACHE[cache_key] = (time.time(), result)
        return result
    except Exception as e:
        return f"⚠️ Ошибка: {str(e)}"

# --- 3. DAILY BRIEFING (ACTIONABLE) ---
async def get_daily_briefing(market_data):
    date_str = datetime.now().strftime("%d.%m.%Y")
    cache_key = f"daily_briefing_{date_str}"
    
    if cache_key in ANALYSIS_CACHE:
        timestamp, cached_text = ANALYSIS_CACHE[cache_key]
        if time.time() - timestamp < DAILY_CACHE_TTL:
            return cached_text

    system_prompt = f"""
    РОЛЬ: Ведущий аналитик хедж-фонда.
    ДАТА: {date_str}
    ДАННЫЕ: BTC Dom: {market_data.get('btc_dominance')}%, Top Coins: {market_data.get('top_coins')}

    ЗАДАЧА: Написать утренний брифинг. Выбери 3 монеты из топа.
    Для каждой дай SMC-сетап (Вход от отката/ликвидности).

    ФОРМАТ ВЫВОДА (HTML):
    🌅 <b>Market Pulse: {date_str}</b>

    📊 <b>Макро:</b> BTC Dom {market_data.get('btc_dominance')}%. (Краткий вывод).

    🔥 <b>Сектор дня:</b> (Назови сектор).

    💎 <b>Watchlist (Охота за ликвидностью):</b>

    1. <b>#TICKER</b> 📈 LONG
       └ <i>Сетап:</i> (Например: Сняли стопы снизу, возврат в рендж).
       └ <i>План:</i> Ждем ретест зоны (цена). Цель (цена).

    2. <b>#TICKER</b> 📈 LONG
       └ <i>Сетап:</i> ...
       └ <i>План:</i> ...

    3. <b>#TICKER</b> ...
    
    👇 <i>Детальный расчет сделки: /sniper [тикер]</i>
    """

    try:
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "You are a pro trader. Output Telegram HTML."},
                {"role": "user", "content": system_prompt}
            ],
            temperature=0.3,
            extra_headers={"HTTP-Referer": "[https://telegram.org](https://telegram.org)", "X-Title": "CryptoBot"}
        )
        result = clean_html(response.choices[0].message.content)
        ANALYSIS_CACHE[cache_key] = (time.time(), result)
        return result

    except Exception as e:
        return f"⚠️ Ошибка: {str(e)}"