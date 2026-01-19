import os
import re
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
    Чистит текст от веб-мусора и запрещенных тегов для Telegram.
    """
    if not text: return ""
    
    # 1. Убираем "обертки" кода, если нейросеть решила вернуть код
    text = text.replace("```html", "").replace("```", "")
    
    # 2. Убираем структуру веб-страницы (из-за этого была ошибка !doctype)
    text = re.sub(r"<!DOCTYPE.*?>", "", text, flags=re.IGNORECASE)
    text = text.replace("<html>", "").replace("</html>", "")
    text = text.replace("<head>", "").replace("</head>", "")
    text = text.replace("<body>", "").replace("</body>", "")
    
    # 3. Заменяем веб-теги на телеграм-теги
    text = text.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    text = text.replace("<p>", "").replace("</p>", "\n")
    text = text.replace("<h1>", "<b>").replace("</h1>", "</b>\n")
    text = text.replace("<h2>", "<b>").replace("</h2>", "</b>\n")
    text = text.replace("<h3>", "<b>").replace("</h3>", "</b>\n")
    text = text.replace("<li>", "• ").replace("</li>", "")
    text = text.replace("<ul>", "").replace("</ul>", "")
    
    # 4. Убираем Markdown (**), чтобы не было каши
    text = text.replace("**", "") 
    text = text.replace("##", "")
    
    return text.strip()

# --- АУДИТ (PRO VC VERSION) ---
async def get_crypto_analysis(ticker, full_name, lang="ru"):
    if lang == "ru":
        system_prompt = f"""
        Ты — Старший Аналитик Венчурного Фонда (VC). 
        Твоя задача: Провести жесткий Due Diligence (аудит) проекта {full_name} ({ticker}).
        
        ОТВЕЧАЙ НА РУССКОМ. 
        Используй ТОЛЬКО разрешенные Telegram теги: <b>, <i>, <code>.
        НЕ ПИШИ полноценный HTML код (без <html>, без <body>). Только текст сообщения.

        ШАБЛОН АУДИТА:

        🛡 <b>{ticker} — Фундаментальный Аудит</b>

        1️⃣ <b>Безопасность и Доверие (Security)</b>
        • <b>Команда:</b> ...
        • <b>Аудиты кода:</b> ...
        • <b>Red Flags:</b> ...

        2️⃣ <b>Продукт и Конкуренты (Utility)</b>
        • <b>Суть проекта:</b> ...
        • <b>Конкуренты:</b> ...
        • <b>Активность:</b> ...

        3️⃣ <b>Токеномика и Инфляция</b>
        • <b>Распределение:</b> ...
        • <b>Вестинг (Unlock):</b> ...
        • <b>Полезность токена:</b> ...

        4️⃣ <b>Ончейн и Рынок</b>
        • <b>TVL и Метрики:</b> ...
        • <b>Листинги:</b> ...
        • <b>Макро-корреляция:</b> ...

        ⚖️ <b>ИТОГОВЫЙ ВЕРДИКТ:</b>
        • <b>Уровень риска:</b> [НИЗКИЙ / СРЕДНИЙ / ВЫСОКИЙ / ЭКСТРЕМАЛЬНЫЙ]
        • <b>Мнение аналитика:</b> ...
        """
    else:
        system_prompt = f"""
        You are a Senior VC Analyst. Conduct a deep Due Diligence on {full_name} ({ticker}).
        ANSWER IN ENGLISH. 
        Use ONLY Telegram-supported tags: <b>, <i>, <code>.
        DO NOT write a full HTML document (no <html>, no <!DOCTYPE>).

        TEMPLATE:
        🛡 <b>{ticker} — Fundamental Audit</b>
        ... (structure similar to Russian version) ...
        """

    try:
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "You are a VC crypto analyst. Return formatted message text only. No markdown blocks."},
                {"role": "user", "content": system_prompt}
            ],
            extra_headers={"HTTP-Referer": "https://telegram.org", "X-Title": "CryptoBot"}
        )
        return clean_html(response.choices[0].message.content)
    except Exception as e:
        return f"⚠️ Error: {str(e)}"

# --- СНАЙПЕР (PRO HEDGE FUND VERSION) ---
async def get_sniper_analysis(ticker, full_name, price, lang="ru"):
    if lang == "ru":
        system_prompt = f"""
        Ты — Старший Аналитик Крипто-Хеджфонда (SMC Expert).
        Сделай глубокий разбор {full_name} ({ticker}) при цене ${price}.
        
        ОТВЕЧАЙ НА РУССКОМ. ИСПОЛЬЗУЙ ТОЛЬКО ТЕГИ: <b>, <i>, <code>.
        НЕ ИСПОЛЬЗУЙ Markdown (**). НЕ ПИШИ <!DOCTYPE>.

        ШАБЛОН:
        📊 <b>{ticker}/USDT — Среднесрочный разбор</b>
        💵 <b>Цена:</b> ≈ ${price}

        1️⃣ <b>Ключевые уровни (D/W)</b>
        • <b>Поддержка:</b> ...
        • <b>Сопротивление:</b> ...
        • <i>Вывод по диапазону.</i>

        2️⃣ <b>Фаза рынка и Структура</b>
        • Тренд, Фаза, Структура.

        3️⃣ <b>Smart Money & Sentiment</b>
        • OI и Funding.
        • Действия ММ: Liquidity Hunter 2.0, Accumulation, Spoofing.

        4️⃣ <b>Свинг-Сигнал (СТРОГО ОДНО НАПРАВЛЕНИЕ: ЛОНГ или ШОРТ)</b>
        🔹 <b>Точка входа:</b> ...
        🔹 <b>Усреднение:</b> ...
        ✅ <b>Тейк-Профиты:</b> ...
        ⛔️ <b>Стоп-лосс:</b> ...

        🏁 <b>Резюме:</b> ...
        """
    else:
        system_prompt = f"""
        You are a Senior Crypto Hedge Fund Analyst (SMC Expert). Analyze {full_name} ({ticker}) at ${price}.
        ANSWER IN ENGLISH. Use HTML tags (<b>, <i>). NO Markdown. NO <!DOCTYPE>.

        TEMPLATE:
        📊 <b>{ticker}/USDT — Mid-term Analysis</b>
        ...
        """

    try:
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "You are a top-tier crypto analyst. Output raw text with Telegram HTML tags only."},
                {"role": "user", "content": system_prompt}
            ],
            extra_headers={"HTTP-Referer": "https://telegram.org", "X-Title": "CryptoBot"}
        )
        return clean_html(response.choices[0].message.content)
    except Exception as e:
        return f"⚠️ Error: {str(e)}"