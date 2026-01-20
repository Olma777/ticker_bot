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

# --- КЭШИРОВАНИЕ (MEMORY) ---
# Чтобы бот не пересчитывал анализ каждую секунду и экономил бюджет
ANALYSIS_CACHE = {}
CACHE_TTL = 300       # 5 минут для Снайпера и Аудита
DAILY_CACHE_TTL = 1800 # 30 минут для Дейли брифинга

def clean_html(text):
    """
    БРОНЕБОЙНАЯ очистка текста для Telegram.
    Защищает от ошибки "Unsupported start tag", сохраняя жирный шрифт и курсив.
    """
    if not text: return ""
    
    # 1. Убираем обертки кода
    text = text.replace("```html", "").replace("```", "")
    
    # 2. Убираем структуру веб-страницы
    text = re.sub(r"<!DOCTYPE.*?>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<head>.*?</head>", "", text, flags=re.IGNORECASE | re.DOTALL)
    text = text.replace("<html>", "").replace("</html>", "")
    text = text.replace("<body>", "").replace("</body>", "")
    
    # 3. Превращаем <br> и <p> в переносы строк
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<p.*?>", "", text, flags=re.IGNORECASE)

    # 4. Превращаем заголовки h1-h3 в жирный текст
    text = re.sub(r"<h[1-3].*?>(.*?)</h[1-3]>", r"<b>\1</b>\n", text, flags=re.IGNORECASE)
    
    # 5. Превращаем списки li в точки
    text = text.replace("<li>", "• ").replace("</li>", "")
    text = re.sub(r"<ul.*?>", "", text, flags=re.IGNORECASE)
    text = text.replace("</ul>", "")

    # === ЗАЩИТА ТЕГОВ ===
    # Прячем разрешенные теги во временные метки
    placeholders = {}
    
    def hide_tag(match):
        tag = match.group(0)
        key = f"||TAG_{len(placeholders)}||"
        placeholders[key] = tag
        return key

    allowed_tags = r"<(/?(b|strong|i|em|code|s|u|pre))>"
    text = re.sub(allowed_tags, hide_tag, text, flags=re.IGNORECASE)

    # === ОБЕЗВРЕЖИВАНИЕ ===
    # Экранируем всё, что похоже на теги (например, "цена < 100")
    text = text.replace("<", "&lt;").replace(">", "&gt;")

    # === ВОССТАНОВЛЕНИЕ ===
    for key, tag in placeholders.items():
        text = text.replace(key, tag)

    # Финальная чистка Markdown
    text = text.replace("**", "").replace("##", "")
    
    return text.strip()

# --- 1. АУДИТ (PRO VC VERSION) ---
async def get_crypto_analysis(ticker, full_name, lang="ru"):
    cache_key = f"{ticker}_audit_{lang}"
    if cache_key in ANALYSIS_CACHE:
        timestamp, cached_text = ANALYSIS_CACHE[cache_key]
        if time.time() - timestamp < CACHE_TTL:
            return cached_text

    if lang == "ru":
        system_prompt = f"""
        Ты — Старший Аналитик Венчурного Фонда (VC). 
        Твоя задача: Провести жесткий Due Diligence (аудит) проекта {full_name} ({ticker}).
        
        ОТВЕЧАЙ НА РУССКОМ. Используй ТОЛЬКО теги: <b>, <i>, <code>.

        ШАБЛОН АУДИТА:
        🛡 <b>{ticker} — Фундаментальный Аудит</b>

        1️⃣ <b>Безопасность и Доверие</b>
        • <b>Команда:</b> (Публичная/Анонимная? Репутация).
        • <b>Аудиты кода:</b> (Certik, Hacken — были ли взломы?).
        • <b>Red Flags:</b> (Централизация, возможности минтинга).

        2️⃣ <b>Продукт и Конкуренты</b>
        • <b>Суть проекта:</b> (USP - уникальное предложение).
        • <b>Конкуренты:</b> (Кто сильнее/слабее?).
        • <b>Активность:</b> (GitHub, реальные юзеры).

        3️⃣ <b>Токеномика и Инфляция</b>
        • <b>Распределение:</b> (Доля фондов vs комьюнити).
        • <b>Вестинг (Unlock):</b> (Есть ли риск сброса токенов фондами?).
        • <b>Полезность:</b> (Зачем держать токен?).

        4️⃣ <b>Ончейн и Рынок</b>
        • <b>TVL и Метрики:</b> (Рост или стагнация?).
        • <b>Листинги:</b> (Tier-1 биржи).
        • <b>Макро-корреляция:</b> (Зависимость от BTC).
        
        5️⃣ <b>Долгосрочный прогноз (Качественный)</b>
        • <b>Потенциал:</b> Сформируй прогноз ценности (без торговых сигналов). Перспектива 1-3 года.
        • <b>Драйверы роста:</b> (Технологии, адопшн, партнерства).

        ⚖️ <b>ИТОГОВЫЙ ВЕРДИКТ:</b>
        • <b>Уровень риска:</b> [НИЗКИЙ / СРЕДНИЙ / ВЫСОКИЙ / ЭКСТРЕМАЛЬНЫЙ]
        • <b>Мнение аналитика:</b> (Инвестировать, спекулировать или скам?).
        """
    else:
        system_prompt = f"""
        You are a Senior VC Analyst. Conduct a deep Due Diligence on {full_name} ({ticker}).
        ANSWER IN ENGLISH. Use ONLY Telegram-supported tags: <b>, <i>, <code>.
        
        TEMPLATE:
        🛡 <b>{ticker} — Fundamental Audit</b>
        ... (English structure identical to Russian) ...
        """

    try:
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "You are a VC crypto analyst. Return text with strictly valid Telegram HTML tags."},
                {"role": "user", "content": system_prompt}
            ],
            temperature=0.2,
            extra_headers={"HTTP-Referer": "https://telegram.org", "X-Title": "CryptoBot"}
        )
        result = clean_html(response.choices[0].message.content)
        ANALYSIS_CACHE[cache_key] = (time.time(), result)
        return result
    except Exception as e:
        return f"⚠️ Error: {str(e)}"

# --- 2. СНАЙПЕР (PRO HEDGE FUND + ALT SCENARIO) ---
async def get_sniper_analysis(ticker, full_name, price, lang="ru"):
    cache_key = f"{ticker}_sniper_{lang}"
    if cache_key in ANALYSIS_CACHE:
        timestamp, cached_text = ANALYSIS_CACHE[cache_key]
        if time.time() - timestamp < CACHE_TTL:
            return cached_text

    if lang == "ru":
        system_prompt = f"""
        Ты — Старший Аналитик Крипто-Хеджфонда (SMC Expert).
        Сделай глубокий разбор {full_name} ({ticker}) при цене ${price}.
        
        Твоя задача: Найти ЛУЧШУЮ сделку. Если цена в середине диапазона, предложи сценарий хеджирования.
        
        ОТВЕЧАЙ НА РУССКОМ. ИСПОЛЬЗУЙ ТОЛЬКО ТЕГИ: <b>, <i>, <code>.

        ШАБЛОН:
        📊 <b>{ticker}/USDT — Среднесрочный разбор</b>
        💵 <b>Цена:</b> ≈ ${price}

        1️⃣ <b>Ключевые уровни (D/W)</b>
        • <b>Поддержка:</b> ...
        • <b>Сопротивление:</b> ...
        • <i>Вывод по диапазону.</i>

        2️⃣ <b>Фаза рынка и Структура</b>
        • Тренд, Фаза (Аккумуляция/Распределение), Структура.

        3️⃣ <b>Smart Money & Sentiment</b>
        • OI и Funding.
        • Действия ММ: Liquidity Hunter 2.0 (где стопы?), Accumulation, Spoofing.

        4️⃣ <b>ОСНОВНОЙ Свинг-Сигнал (По Тренду)</b>
        <i>(Обычно: Лонг на бычьем, Шорт на медвежьем)</i>
        🔹 <b>Направление:</b> [ЛОНГ / ШОРТ]
        🔹 <b>Точка входа:</b> ...
        🔹 <b>Усреднение:</b> ...
        ✅ <b>Тейк-Профиты:</b> TP1, TP2, TP3.
        ⛔️ <b>Стоп-лосс:</b> Цена и Логика.

        5️⃣ <b>Альтернативный сценарий (Контртренд/Хедж)</b>
        <i>(Заполнять, если цена далеко от точки входа. Например, шорт к поддержке)</i>
        • <b>Возможность:</b> Можно ли открыть сделку прямо сейчас в противоположную сторону?
        • <b>Риск:</b> (Например: торговля против тренда).
        • <b>Сетап:</b> Если риск оправдан, укажи цели. Если нет — напиши "Ждать точку входа".

        🏁 <b>Резюме:</b> Короткий вывод.
        """
    else:
        system_prompt = f"""
        You are a Senior Crypto Hedge Fund Analyst. Analyze {full_name} ({ticker}) at ${price}.
        ANSWER IN ENGLISH. Use HTML tags (<b>, <i>).
        
        TEMPLATE:
        📊 <b>{ticker}/USDT — Mid-term Analysis</b>
        ...
        5️⃣ <b>Alternative Scenario (Counter-trend/Hedge)</b>
        ...
        """

    try:
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "You are a top-tier crypto analyst. Output raw text with Telegram HTML tags only."},
                {"role": "user", "content": system_prompt}
            ],
            temperature=0.1, # Низкая температура для точности сигналов
            extra_headers={"HTTP-Referer": "https://telegram.org", "X-Title": "CryptoBot"}
        )
        result = clean_html(response.choices[0].message.content)
        ANALYSIS_CACHE[cache_key] = (time.time(), result)
        return result
    except Exception as e:
        return f"⚠️ Error: {str(e)}"

# --- 3. DAILY BRIEFING (УТРЕННЯЯ ГАЗЕТА) ---
async def get_daily_briefing(market_data):
    date_str = datetime.now().strftime("%d.%m.%Y")
    cache_key = f"daily_briefing_{date_str}"
    
    if cache_key in ANALYSIS_CACHE:
        timestamp, cached_text = ANALYSIS_CACHE[cache_key]
        if time.time() - timestamp < DAILY_CACHE_TTL:
            return cached_text

    system_prompt = f"""
    # РОЛЬ
    Ты — ведущий аналитик "Market Maker Lens". Твоя задача — сгенерировать "Утренний Брифинг" для трейдеров.
    Стиль: Профессиональный, без "воды", фокус на логику Маркетмейкера. 
    ОТВЕЧАЙ НА РУССКОМ. ИСПОЛЬЗУЙ ТОЛЬКО ТЕГИ: <b>, <i>, <code>.

    # ВХОДНЫЕ ДАННЫЕ
    1. Дата: {date_str}
    2. BTC Dominance: {market_data.get('btc_dominance')}% (Если растет - ликвидность в BTC, если падает - альтсезон).
    3. BTC Price: ${market_data.get('btc_price')}
    4. Рынок (Топ монет и изменения): {market_data.get('top_coins')}
    5. Сентимент: Определи сам на основе динамики рынка (Страх/Жадность).

    # ЗАДАЧА АНАЛИЗА
    ШАГ 1: МАКРО-КЛИМАТ
    - Если BTC Dom падает + BTC флэт/рост -> Risk-On (Альтсезон).
    - Если BTC Dom растет + BTC падает -> Risk-Off (Кэш).
    
    ШАГ 2: ПОИСК НАРРАТИВА
    - Посмотри на список монет. Кто растет? (SOL, ETH, BNB?). Выдели лидера как "Сектор дня".
    
    ШАГ 3: ОТБОР ТОП-3 МОНЕТ (Watchlist)
    - Из списка лидеров выбери 3 актива, придумай логичную причину "Скрытой аккумуляции" на основе SMC.

    # ФОРМАТ ВЫВОДА

    🌅 <b>Market Pulse: {date_str}</b>

    📊 <b>Макро-Настроение:</b> {{BULLISH / BEARISH / NEUTRAL}}
    • <b>Макро:</b> BTC Dom {market_data.get('btc_dominance')}%. {{Вывод для альтов}}.
    • <b>Риски:</b> {{Кратко про волатильность}}.

    🔥 <b>Сектор дня:</b> #{{SECTOR_NAME}}
    Ликвидность перетекает сюда. Лидеры: {{TICKER1}}, {{TICKER2}}.

    💎 <b>Watchlist (Скрытая Аккумуляция):</b>
    Наблюдаем признаки работы ММ (Liquidity Hunter):

    1. <b>#{{TICKER}}</b>
       └ <i>Причина:</i> {{SMC паттерн, например "Сбор стопов завершен"}}.
       └ <i>Цель ММ:</i> {{Уровень}}.

    2. <b>#{{TICKER}}</b>
       └ <i>Причина:</i> {{Аномальный объем}}.

    3. <b>#{{TICKER}}</b>
       └ <i>Причина:</i> {{Тест зоны спроса}}.

    🛠 <b>Торговые инструменты:</b>
    Хочешь детальный разбор? Жми:
    👇
    /audit {{TICKER1}} — Проверить монету
    /sniper {{TICKER1}} — Найти точку входа
    """

    try:
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "You are a pro crypto analyst. Use Telegram HTML tags."},
                {"role": "user", "content": system_prompt}
            ],
            temperature=0.3,
            extra_headers={"HTTP-Referer": "https://telegram.org", "X-Title": "CryptoBot"}
        )
        result = clean_html(response.choices[0].message.content)
        ANALYSIS_CACHE[cache_key] = (time.time(), result)
        return result

    except Exception as e:
        return f"⚠️ Error generating briefing: {str(e)}"