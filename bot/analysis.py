import os
import re
import time
from datetime import datetime
from dotenv import load_dotenv
from openai import AsyncOpenAI
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

    # Получаем уровни поддержки/сопротивления и тренд
    ta = TechnicalAnalyzer()
    
    # Default values
    s1, r1 = 0.0, 0.0
    trend = "NEUTRAL"
    phase = "ACCUMULATION"
    
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
            
            # Find closest support and resistance
            supports = [l for l in levels if l['price'] < price]
            resistances = [l for l in levels if l['price'] > price]
            
            if supports:
                s1 = supports[0]['price']
            else:
                s1 = price * 0.95 # Fallback
                
            if resistances:
                r1 = resistances[0]['price']
            else:
                r1 = price * 1.05 # Fallback
            
            # Determine Trend & Phase (Simple logic for prompt context)
            sma_50 = df['close'].rolling(50).mean().iloc[-1]
            sma_200 = df['close'].rolling(200).mean().iloc[-1]
            
            if price > sma_50 and price > sma_200:
                trend = "BULLISH"
                phase = "IMPULSE"
            elif price < sma_50 and price < sma_200:
                trend = "BEARISH"
                phase = "DISTRIBUTION"
            else:
                trend = "SIDEWAYS"
                phase = "CONSOLIDATION"
                
    except Exception as e:
        print(f"Error getting technical levels: {e}")
        s1 = price * 0.95
        r1 = price * 1.05
    finally:
        await ta.close()

    system_prompt = f"""
    Ты — элитный крипто-аналитик, использующий стратегию "Liquidity Hunter 2.0" и "Smart Money Concepts" (SMC). 
    Твоя задача — найти снайперскую точку входа для {ticker}. 
 
    ИСХОДНЫЕ ДАННЫЕ (ФАКТЫ): 
    1. Текущая цена: ${price} 
    2. ТРЕНД (Algorithmic): {trend} 
    3. ФАЗА РЫНКА: {phase} 
    4. ВАЖНЕЙШИЕ УРОВНИ (Trend Level PRO Indicator): 
       - Поддержка (Support): ${s1:.4f} 
       - Сопротивление (Resistance): ${r1:.4f} 
 
    ИНСТРУКЦИЯ: 
    Используй эти уровни как "железобетонные" ориентиры. Не придумывай свои уровни, если есть данные от индикатора. 
    Твоя аналитика должна строиться вокруг того, как цена взаимодействует с этими уровнями (пробой, отскок, ложный вынос). 
 
    СТРУКТУРА ОТВЕТА (Строго Telegram HTML, без Markdown `**`): 
 
    📊 <b>{ticker}/USDT — Smart Money Sniper Setup</b> 
    💵 <b>Цена сейчас:</b> ${price} 
    ⏳ <b>Горизонт:</b> [Intraday / Swing] 
 
    1️⃣ <b>Структура рынка (1H/4H/D)</b> 
    • <b>Тренд:</b> {trend} 
    • <b>Фаза:</b> {phase} 
    • <b>Ключевые уровни (Trend Level PRO):</b> 
      └ S1: <b>${s1:.4f}</b> (Зона интереса покупателя) 
      └ R1: <b>${r1:.4f}</b> (Зона интереса продавца) 
 
    2️⃣ <b>Ликвидность и Действия ММ (Liquidity Hunter 2.0)</b> 
    • <b>Цель ММ:</b> (Сбор стопов шортов / Выбивание лонгов / Заманивание в ловушку) 
    • <b>Зона интереса (POI):</b> (Где стоит "плита" или скрытый ордер?) 
    • <b>Манипуляции:</b> (Есть ли признаки Spoofing, Layering или False Breakout у уровней ${s1:.4f}/${r1:.4f}?) 
 
    3️⃣ <b>Поток капитала и Настроение</b> 
    • <b>OI + Funding:</b> (Растут ли позиции? Кто платит фандинг?) 
    • <b>Sentiment:</b> (Толпа боится или жадничает?) 
 
    4️⃣ <b>Фундаментальный триггер</b> 
    • (Кратко: есть ли новости/катализаторы?) 
 
    5️⃣ <b>P-Score (Вероятность):</b> [0-100%] 
    (Оцени вероятность отработки сценария на основе защиты уровней). 
 
    6️⃣ <b>Liquidity Map</b> 
    • <b>Ликвидации сверху:</b> (Где стопы шортистов?) 
    • <b>Ликвидации снизу:</b> (Где стопы лонгистов?) 
 
    🎯 <b>Снайперский план (Limit Order)</b> 
    <i>Мы не входим по рынку. Мы ждем цену в капкане.</i> 
 
    🔹 <b>Тип:</b> [LONG / SHORT] (Limit) 
    🔹 <b>Вход:</b> $... (Строго от уровня Trend Level PRO или после снятия ликвидности за ним) 
    🔹 <b>Обоснование:</b> (Почему именно здесь? Напр: "Реакция на ${s1:.4f} + сбор стопов") 
 
    ✅ <b>Take Profit:</b> 
    • TP1: $... (Консервативный) 
    • TP2: $... (Основной) 
    • TP3: $... (Moonbag) 
 
    ⛔️ <b>Stop-Loss:</b> $... (За уровнем / за сломом структуры) 
 
    ⚖️ <b>Совет ММ:</b> (Психология сделки) 
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
    try:
        date_str = datetime.now().strftime("%d.%m.%Y")
        cache_key = f"daily_briefing_{date_str}"
        
        if cache_key in ANALYSIS_CACHE:
            timestamp, cached_text = ANALYSIS_CACHE[cache_key]
            if time.time() - timestamp < DAILY_CACHE_TTL:
                return cached_text

        # Если market_data не передан, получаем его
        if not market_data:
            try:
                market_data = await get_market_summary()
            except Exception as e:
                print(f"Error fetching market summary: {e}")
                market_data = {}

        # Формируем строку с данными рынка
        market_data_str = market_data.get('top_coins', 'BTC: $96000, ETH: $2700')

        system_prompt = f""" 
    Ты — главный стратег крипто-фонда. 
    Твоя задача — просканировать рынок и найти кандидатов на ПАМП в горячих секторах: AI, RWA, Layer-2, DePIN. 
 
    ВХОДНЫЕ ДАННЫЕ (Контекст рынка): 
    {market_data_str} 
 
    ИНСТРУКЦИЯ: 
    Используя эти данные как индикатор состояния рынка, выяви в секторах (AI, RWA, L2, DePIN) по одной монете, которая готовится к пампу. 
    Используй свои знания о монетах этих секторов (например, FET, ONDO, ARB, HNT), коррелируя их с общим трендом. 
 
    КРИТЕРИИ АНАЛИЗА (Liquidity Hunter): 
    1. Техника: Фаза аккумуляции, формирование дна, бычьи дивергенции. 
    2. Следы ММ: Сбор стопов ("фитили"), ложные пробои, рост OI при консолидации. 
    3. Фундаментал: Хайп сектора. 
 
    ФОРМАТ ВЫВОДА (Telegram HTML): 
 
    🌅 <b>Market Pulse & Sector Hunt</b> 
    🔥 <b>Активные сектора:</b> AI, RWA, DePIN, L2 
 
    💎 <b>AI Sector Pick: [ТИКЕР]</b> 
    💵 <b>Цена:</b> $... 
    • <b>Техника:</b> (Напр: Выход из клина, тест поддержки) 
    • <b>Следы ММ:</b> (Напр: Скрытый набор позиций, спуфинг) 
    • 🎯 <b>Сигнал:</b> LONG (Вход: $... / TP: $...) 
 
    💎 <b>RWA Sector Pick: [ТИКЕР]</b> 
    ... (аналогично) 
 
    💎 <b>Layer-2 Sector Pick: [ТИКЕР]</b> 
    ... (аналогично) 
 
    💎 <b>DePIN Sector Pick: [ТИКЕР]</b> 
    ... (аналогично) 
 
    ⚠️ <i>Дисклеймер: Соблюдайте риск-менеджмент.</i> 
    """

        try:
            response = await client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": "You are a crypto analyst. Output in Telegram HTML."},
                    {"role": "user", "content": system_prompt}
                ],
                temperature=0.2,
                extra_headers={"HTTP-Referer": "https://telegram.org", "X-Title": "CryptoBot"}
            )
            result = clean_html(response.choices[0].message.content)
            
            if not result:
                 return "⚠️ Не удалось получить ответ от нейросети. Попробуйте еще раз через минуту."

            ANALYSIS_CACHE[cache_key] = (time.time(), result)
            return result
        except Exception as e:
            print(f"LLM Error: {e}")
            return "⚠️ Не удалось получить ответ от нейросети. Попробуйте еще раз через минуту."

    except Exception as e:
        print(f"Critical Error in daily briefing: {e}")
        return f"⚠️ Произошла внутренняя ошибка при формировании брифинга. Попробуйте позже."