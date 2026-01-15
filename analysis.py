import os
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

client = AsyncOpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url="https://openrouter.ai/api/v1"
)

MODEL_NAME = "deepseek/deepseek-chat"

# --- АУДИТ (AUDIT) ---
async def get_crypto_analysis(ticker, full_name, lang="ru"):
    # Выбираем промпт в зависимости от языка
    if lang == "ru":
        system_prompt = f"""
        Ты профессиональный крипто-аудитор. Проведи аудит проекта {full_name} ({ticker}).
        ОТВЕЧАЙ СТРОГО НА РУССКОМ ЯЗЫКЕ.

        ИСПОЛЬЗУЙ HTML ТЕГИ (<b>bold</b>, <i>italic</i>).

        ШАБЛОН ОТВЕТА:
        🛡 <b>АУДИТ БЕЗОПАСНОСТИ: {ticker}</b>

        1. <b>Безопасность и Команда:</b> ...
        2. <b>Фундаментал и Польза:</b> ...
        3. <b>Токеномика:</b> ...
        4. <b>ВЕРДИКТ:</b> ...
        """
    else:
        system_prompt = f"""
        You are a professional crypto auditor. Conduct an audit for {full_name} ({ticker}).
        ANSWER STRICTLY IN ENGLISH.

        USE HTML TAGS (<b>bold</b>, <i>italic</i>).

        RESPONSE TEMPLATE:
        🛡 <b>SECURITY AUDIT: {ticker}</b>

        1. <b>Security & Team:</b> ...
        2. <b>Fundamentals & Utility:</b> ...
        3. <b>Tokenomics:</b> ...
        4. <b>VERDICT:</b> ...
        """

    try:
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "You are a crypto expert. Use HTML formatting."},
                {"role": "user", "content": system_prompt}
            ],
            extra_headers={"HTTP-Referer": "https://telegram.org", "X-Title": "CryptoBot"}
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"⚠️ Error: {str(e)}"

# --- СНАЙПЕР (SNIPER) ---
async def get_sniper_analysis(ticker, full_name, price, lang="ru"):
    if lang == "ru":
        system_prompt = f"""
        Ты профессиональный трейдер (Smart Money). Проведи анализ {full_name} ({ticker}) при цене ${price}.
        ОТВЕЧАЙ СТРОГО НА РУССКОМ ЯЗЫКЕ.
        
        ИСПОЛЬЗУЙ HTML ТЕГИ.

        ШАБЛОН:
        🎯 <b>СНАЙПЕР-СЕТАП: {ticker}</b>
        💵 <b>Цена:</b> ${price}

        📊 <b>Технический анализ:</b> ...
        🐋 <b>Следы Маркетмейкера:</b> ...

        🚦 <b>СИГНАЛ:</b> [ЛОНГ / ШОРТ]
        📍 <b>Вход:</b> ...
        ✅ <b>Тейки:</b> ...
        ⛔️ <b>Стоп:</b> ...
        """
    else:
        system_prompt = f"""
        You are a professional trader (Smart Money). Analyze {full_name} ({ticker}) at price ${price}.
        ANSWER STRICTLY IN ENGLISH.
        
        USE HTML TAGS.

        TEMPLATE:
        🎯 <b>SNIPER SETUP: {ticker}</b>
        💵 <b>Price:</b> ${price}

        📊 <b>Technical Analysis:</b> ...
        🐋 <b>Smart Money Clues:</b> ...

        🚦 <b>SIGNAL:</b> [LONG / SHORT]
        📍 <b>Entry:</b> ...
        ✅ <b>Take Profit:</b> ...
        ⛔️ <b>Stop Loss:</b> ...
        """

    try:
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "You are a pro trader. Use HTML formatting."},
                {"role": "user", "content": system_prompt}
            ],
            extra_headers={"HTTP-Referer": "https://telegram.org", "X-Title": "CryptoBot"}
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"⚠️ Error: {str(e)}"