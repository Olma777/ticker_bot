import os
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

client = AsyncOpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url="https://openrouter.ai/api/v1"
)

MODEL_NAME = "deepseek/deepseek-chat"

def clean_html(text):
    """
    Чистит текст от тегов, которые не понимает Telegram HTML.
    """
    if not text: return ""
    text = text.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    text = text.replace("<h1>", "<b>").replace("</h1>", "</b>")
    text = text.replace("<h2>", "<b>").replace("</h2>", "</b>")
    text = text.replace("<h3>", "<b>").replace("</h3>", "</b>")
    text = text.replace("**", "") # Убираем маркдаун, если проскочил
    text = text.replace("##", "")
    return text

# --- АУДИТ (AUDIT) ---
async def get_crypto_analysis(ticker, full_name, lang="ru"):
    # (Оставляем аудит без изменений, он у нас уже хороший)
    if lang == "ru":
        system_prompt = f"""
        Ты профессиональный крипто-аудитор. Проведи аудит проекта {full_name} ({ticker}).
        ОТВЕЧАЙ СТРОГО НА РУССКОМ ЯЗЫКЕ. ИСПОЛЬЗУЙ HTML ТЕГИ (<b>bold</b>, <i>italic</i>).
        Не используй Markdown (**).

        ШАБЛОН ОТВЕТА:
        🛡 <b>АУДИТ БЕЗОПАСНОСТИ: {ticker}</b>

        1. <b>Безопасность и Команда:</b> ...
        2. <b>Фундаментал и Польза:</b> ...
        3. <b>Токеномика:</b> ...
        4. <b>ВЕРДИКТ:</b> ...
        """
    else:
        system_prompt = f"""
        You are a professional crypto auditor. Audit {full_name} ({ticker}).
        ANSWER STRICTLY IN ENGLISH. USE HTML TAGS.

        RESPONSE TEMPLATE:
        🛡 <b>SECURITY AUDIT: {ticker}</b>
        ...
        """

    try:
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "You are a crypto auditor. Use HTML formatting."},
                {"role": "user", "content": system_prompt}
            ],
            extra_headers={"HTTP-Referer": "https://telegram.org", "X-Title": "CryptoBot"}
        )
        return clean_html(response.choices[0].message.content)
    except Exception as e:
        return f"⚠️ Error: {str(e)}"

# --- СНАЙПЕР (PRO VERSION) ---
async def get_sniper_analysis(ticker, full_name, price, lang="ru"):
    # ПРОМПТ НА ОСНОВЕ ТВОИХ ШАБЛОНОВ И ПРИМЕРА LTC
    if lang == "ru":
        system_prompt = f"""
        Ты — Старший Аналитик Крипто-Хеджфонда. Твоя специализация: Smart Money Concepts (SMC), анализ ликвидности и манипуляций маркетмейкера.
        
        Твоя задача: Сделать глубокий разбор монеты {full_name} ({ticker}) при цене ${price}.
        
        ИСПОЛЬЗУЙ СТРУКТУРУ И ЛОГИКУ НИЖЕ. ОТВЕЧАЙ НА РУССКОМ. ИСПОЛЬЗУЙ HTML (<b>, <i>, <code>).

        ШАБЛОН АНАЛИЗА:

        📊 <b>{ticker}/USDT — Среднесрочный разбор</b>
        💵 <b>Цена:</b> ≈ ${price}

        1️⃣ <b>Ключевые уровни (D/W)</b>
        • <b>Поддержка (Support):</b> Укажи 2-3 уровня (сильный daily, глубокий weekly). Опиши, почему они важны (скопление объемов, историческая база).
        • <b>Сопротивление (Resistance):</b> Укажи 2-3 уровня (ближайший, range-high, психологический). 
        • <i>Вывод по диапазону:</i> Укажи текущий рабочий диапазон (например: 65–70$ снизу и 75–82$ сверху).

        2️⃣ <b>Фаза рынка и Структура</b>
        • <b>Тренд:</b> (Восходящий / Нисходящий / Боковик).
        • <b>Фаза:</b> (Накопление, Распределение, Markup, Markdown).
        • <b>Структура:</b> Опиши поведение цены (импульс, коррекция, слом структуры).

        3️⃣ <b>Smart Money & Sentiment</b>
        • <b>OI и Funding:</b> Оцени, что происходит с открытым интересом (растет/падает) и фандингом. Есть ли дисбаланс Long/Short?
        • <b>Действия Маркетмейкера (Стратегии):</b>
          - <i>Liquidity Hunter 2.0:</i> Где стопы? Кого сейчас "бреют"?
          - <i>Accumulation/Distribution:</i> Есть ли признаки скрытого набора или раздачи?
          - <i>Spoofing/Layering:</i> Есть ли признаки манипуляций в стакане?

        4️⃣ <b>Свинг-Сигнал (СТРОГО ОДНО НАПРАВЛЕНИЕ: ЛОНГ или ШОРТ)</b>
        <i>Обоснование выбора направления в 1 предложении.</i>

        🔹 <b>Точка входа (Entry):</b>
        - Основной вход: (Цена).
        - Консервативный вход: (Цена).
        
        🔹 <b>Усреднение (DCA):</b>
        - Уровень 1: (Безопасный добор).
        - Уровень 2: (Агрессивный добор, перед стопом).

        ✅ <b>Тейк-Профиты (TP):</b>
        - TP1 (Частичная фиксация): ...
        - TP2 (Основная цель): ...
        - TP3 (Moonbag/Остаток): ...

        ⛔️ <b>Стоп-лосс (Invalidation):</b>
        - Цена: ...
        - Логика: Почему здесь? (Слом структуры, уход под базу).

        🏁 <b>Резюме:</b> Короткий вывод в 2 строки.
        """
    else:
        # English version (Shortened for brevity but same logic)
        system_prompt = f"""
        You are a Senior Crypto Hedge Fund Analyst (SMC Expert). Analyze {full_name} ({ticker}) at ${price}.
        ANSWER IN ENGLISH. USE HTML.

        TEMPLATE:
        📊 <b>{ticker}/USDT — Mid-term Analysis</b>
        💵 <b>Price:</b> ≈ ${price}

        1️⃣ <b>Key Levels (D/W)</b>
        • <b>Support:</b> 2-3 levels with context.
        • <b>Resistance:</b> 2-3 levels with context.
        • <b>Range:</b> Current working range.

        2️⃣ <b>Market Phase & Structure</b>
        • Trend, Phase (Accumulation/Distribution), Structure.

        3️⃣ <b>Smart Money & Sentiment</b>
        • OI/Funding analysis.
        • Market Maker Strategies (Liquidity Hunter, Spoofing).

        4️⃣ <b>Swing Signal (ONE DIRECTION: LONG or SHORT)</b>
        🔹 <b>Entry:</b> Split entry (Main / Conservative).
        🔹 <b>Averaging (DCA):</b> Safe levels to add.
        ✅ <b>Take Profits:</b> TP1, TP2, TP3.
        ⛔️ <b>Stop Loss:</b> Price & Logic.

        🏁 <b>Summary:</b> 2 lines conclusion.
        """

    try:
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "You are a top-tier crypto analyst. Use professional terminology (SMC, OI, Funding). Use HTML formatting strictly."},
                {"role": "user", "content": system_prompt}
            ],
            extra_headers={"HTTP-Referer": "https://telegram.org", "X-Title": "CryptoBot"}
        )
        return clean_html(response.choices[0].message.content)
    except Exception as e:
        return f"⚠️ Error: {str(e)}"