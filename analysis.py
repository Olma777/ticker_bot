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
    БРОНЕБОЙНАЯ очистка текста для Telegram.
    1. Прячет разрешенные теги.
    2. Экранирует все остальные символы < и > (чтобы Telegram не ругался).
    3. Возвращает разрешенные теги.
    """
    if not text: return ""
    
    # 1. Убираем обертки кода
    text = text.replace("```html", "").replace("```", "")
    
    # 2. Убираем структуру веб-страницы (доктайпы, хедеры)
    text = re.sub(r"<!DOCTYPE.*?>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<head>.*?</head>", "", text, flags=re.IGNORECASE | re.DOTALL)
    text = text.replace("<html>", "").replace("</html>", "")
    text = text.replace("<body>", "").replace("</body>", "")
    
    # 3. Превращаем <br> и <p> в переносы строк ПЕРЕД защитой
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
    # Заменяем разрешенные теги на временные метки, которые точно не сломают HTML
    # Telegram поддерживает: b, strong, i, em, u, ins, s, strike, del, code, pre
    
    placeholders = {}
    
    def hide_tag(match):
        tag = match.group(0)
        # Создаем уникальный ключ
        key = f"||TAG_{len(placeholders)}||"
        placeholders[key] = tag
        return key

    # Ищем разрешенные теги и прячем их
    allowed_tags = r"<(/?(b|strong|i|em|code|s|u))>"
    text = re.sub(allowed_tags, hide_tag, text, flags=re.IGNORECASE)

    # === ОБЕЗВРЕЖИВАНИЕ ===
    # Всё, что осталось с уголками < или > — это мусор или математика. Экранируем их.
    text = text.replace("<", "&lt;").replace(">", "&gt;")

    # === ВОССТАНОВЛЕНИЕ ===
    # Возвращаем спрятанные теги обратно
    for key, tag in placeholders.items():
        text = text.replace(key, tag)

    # Финальная чистка Markdown символов
    text = text.replace("**", "").replace("##", "")
    
    return text.strip()

# --- АУДИТ (PRO VC VERSION + LONG TERM) ---
async def get_crypto_analysis(ticker, full_name, lang="ru"):
    if lang == "ru":
        system_prompt = f"""
        Ты — Старший Аналитик Венчурного Фонда (VC). 
        Твоя задача: Провести жесткий Due Diligence (аудит) проекта {full_name} ({ticker}).
        
        ОТВЕЧАЙ НА РУССКОМ. 
        Используй ТОЛЬКО разрешенные Telegram теги: <b>, <i>, <code>.
        Остальной текст пиши без тегов.

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
        
        5️⃣ <b>Долгосрочный прогноз (Качественный)</b>
        • <b>Потенциал:</b> Сформируй качественный прогноз стоимости/диапазона (без сигналов). Перспектива 1-3 года.
        • <b>Драйверы роста:</b> Что может запампить цену? (Технологии, адопшн).

        ⚖️ <b>ИТОГОВЫЙ ВЕРДИКТ:</b>
        • <b>Уровень риска:</b> [НИЗКИЙ / СРЕДНИЙ / ВЫСОКИЙ / ЭКСТРЕМАЛЬНЫЙ]
        • <b>Мнение аналитика:</b> (Инвестировать, спекулировать или скам?).
        """
    else:
        system_prompt = f"""
        You are a Senior VC Analyst. Conduct a deep Due Diligence on {full_name} ({ticker}).
        ANSWER IN ENGLISH. 
        Use ONLY Telegram-supported tags: <b>, <i>, <code>.

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
            extra_headers={"HTTP-Referer": "https://telegram.org", "X-Title": "CryptoBot"}
        )
        return clean_html(response.choices[0].message.content)
    except Exception as e:
        return f"⚠️ Error: {str(e)}"

# --- СНАЙПЕР (PRO HEDGE FUND VERSION - без изменений) ---
async def get_sniper_analysis(ticker, full_name, price, lang="ru"):
    if lang == "ru":
        system_prompt = f"""
        Ты — Старший Аналитик Крипто-Хеджфонда (SMC Expert).
        Сделай глубокий разбор {full_name} ({ticker}) при цене ${price}.
        
        ОТВЕЧАЙ НА РУССКОМ. ИСПОЛЬЗУЙ ТОЛЬКО ТЕГИ: <b>, <i>, <code>.
        НЕ ИСПОЛЬЗУЙ Markdown (**).

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
        ANSWER IN ENGLISH. Use HTML tags (<b>, <i>).

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