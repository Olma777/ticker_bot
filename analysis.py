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
    text = text.replace("**", "") 
    text = text.replace("##", "")
    return text

# --- АУДИТ (PRO VERSION) ---
async def get_crypto_analysis(ticker, full_name, lang="ru"):
    if lang == "ru":
        system_prompt = f"""
        Ты — Старший Аналитик Венчурного Фонда (VC). Твоя специализация: Фундаментальный анализ, Токеномика и Аудит безопасности.
        
        Твоя задача: Провести жесткий Due Diligence (аудит) проекта {full_name} ({ticker}).
        Ты должен найти скрытые риски, которые не видят новички.
        
        ОТВЕЧАЙ НА РУССКОМ. ИСПОЛЬЗУЙ HTML (<b>, <i>, <code>).

        ШАБЛОН АУДИТА:

        🛡 <b>{ticker} — Фундаментальный Аудит</b>

        1️⃣ <b>Безопасность и Доверие (Security)</b>
        • <b>Команда:</b> (Публичная/Анонимная? Есть ли опыт?).
        • <b>Аудиты кода:</b> (Certik, Hacken и др. — были ли взломы?).
        • <b>Red Flags:</b> (Есть ли тревожные сигналы: централизация, доступ к минтингу?).

        2️⃣ <b>Продукт и Конкуренты (Utility)</b>
        • <b>Суть проекта:</b> Какую реальную проблему решает? (USP).
        • <b>Конкуренты:</b> Кто сильнее? (Например: лучше/хуже, чем Optimism/Solana/Render).
        • <b>Активность:</b> Жив ли GitHub? Есть ли реальные пользователи?

        3️⃣ <b>Токеномика и Инфляция</b>
        • <b>Распределение:</b> (Сколько у фондов/команды? Нет ли риска дампа?).
        • <b>Вестинг (Unlock):</b> Ожидаются ли крупные разблокировки токенов в ближайшее время?
        • <b>Полезность токена:</b> Зачем его покупать? (Газ, стейкинг, голосование).

        4️⃣ <b>Ончейн и Рынок</b>
        • <b>TVL и Метрики:</b> Растет или падает ликвидность в протоколе?
        • <b>Листинги:</b> Есть ли на Tier-1 биржах (Binance/Coinbase)?
        • <b>Макро-корреляция:</b> Как ведет себя к BTC?

        ⚖️ <b>ИТОГОВЫЙ ВЕРДИКТ:</b>
        • <b>Уровень риска:</b> [НИЗКИЙ / СРЕДНИЙ / ВЫСОКИЙ / ЭКСТРЕМАЛЬНЫЙ]
        • <b>Мнение аналитика:</b> (Инвестировать в долгосрок, спекулировать или бежать?).
        """
    else:
        system_prompt = f"""
        You are a Senior VC Analyst. Conduct a deep Due Diligence on {full_name} ({ticker}).
        ANSWER IN ENGLISH. USE HTML.

        TEMPLATE:
        🛡 <b>{ticker} — Fundamental Audit</b>

        1️⃣ <b>Security & Trust</b>
        • Team, Audits, Red Flags.

        2️⃣ <b>Product & Utility</b>
        • USP (Unique Selling Point), Competitors, Dev Activity.

        3️⃣ <b>Tokenomics</b>
        • Distribution, Vesting/Unlocks, Token Utility.

        4️⃣ <b>On-Chain & Market</b>
        • TVL, Tier-1 Listings, Correlation.

        ⚖️ <b>FINAL VERDICT:</b>
        • <b>Risk Level:</b> [LOW / MID / HIGH / EXTREME]
        • <b>Analyst Opinion:</b> (Long-term hold / Speculative / Scam).
        """

    try:
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "You are a VC crypto analyst. Be critical and objective. Use HTML."},
                {"role": "user", "content": system_prompt}
            ],
            extra_headers={"HTTP-Referer": "https://telegram.org", "X-Title": "CryptoBot"}
        )
        return clean_html(response.choices[0].message.content)
    except Exception as e:
        return f"⚠️ Error: {str(e)}"

# --- СНАЙПЕР (PRO VERSION - без изменений) ---
async def get_sniper_analysis(ticker, full_name, price, lang="ru"):
    # (Этот код мы уже обновили в прошлом шаге, дублирую для целостности файла)
    if lang == "ru":
        system_prompt = f"""
        Ты — Старший Аналитик Крипто-Хеджфонда. Твоя специализация: Smart Money Concepts (SMC), анализ ликвидности и манипуляций маркетмейкера.
        Твоя задача: Сделать глубокий разбор монеты {full_name} ({ticker}) при цене ${price}.
        
        ИСПОЛЬЗУЙ СТРУКТУРУ И ЛОГИКУ НИЖЕ. ОТВЕЧАЙ НА РУССКОМ. ИСПОЛЬЗУЙ HTML (<b>, <i>, <code>).

        ШАБЛОН АНАЛИЗА:
        📊 <b>{ticker}/USDT — Среднесрочный разбор</b>
        💵 <b>Цена:</b> ≈ ${price}

        1️⃣ <b>Ключевые уровни (D/W)</b>
        • <b>Поддержка (Support):</b> 2-3 уровня. Контекст.
        • <b>Сопротивление (Resistance):</b> 2-3 уровня. Контекст.
        • <i>Вывод по диапазону.</i>

        2️⃣ <b>Фаза рынка и Структура</b>
        • Тренд, Фаза, Структура.

        3️⃣ <b>Smart Money & Sentiment</b>
        • OI и Funding.
        • Действия ММ: Liquidity Hunter 2.0, Accumulation, Spoofing.

        4️⃣ <b>Свинг-Сигнал (СТРОГО ОДНО НАПРАВЛЕНИЕ: ЛОНГ или ШОРТ)</b>
        🔹 <b>Точка входа:</b> Основной / Консервативный.
        🔹 <b>Усреднение:</b> Уровни.
        ✅ <b>Тейк-Профиты:</b> TP1, TP2, TP3.
        ⛔️ <b>Стоп-лосс:</b> Цена и Логика.

        🏁 <b>Резюме:</b> 2 строки.
        """
    else:
        system_prompt = f"""
        You are a Senior Crypto Hedge Fund Analyst (SMC Expert). Analyze {full_name} ({ticker}) at ${price}.
        ANSWER IN ENGLISH. USE HTML.

        TEMPLATE:
        📊 <b>{ticker}/USDT — Mid-term Analysis</b>
        💵 <b>Price:</b> ≈ ${price}

        1️⃣ <b>Key Levels (D/W)</b>
        • Support, Resistance, Range.

        2️⃣ <b>Market Phase & Structure</b>
        • Trend, Phase, Structure.

        3️⃣ <b>Smart Money & Sentiment</b>
        • OI/Funding, MM Strategies.

        4️⃣ <b>Swing Signal (ONE DIRECTION: LONG or SHORT)</b>
        🔹 Entry, Averaging.
        ✅ Take Profits.
        ⛔️ Stop Loss.

        🏁 <b>Summary:</b> 2 lines.
        """

    try:
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "You are a top-tier crypto analyst. Use professional terminology. Use HTML strictly."},
                {"role": "user", "content": system_prompt}
            ],
            extra_headers={"HTTP-Referer": "https://telegram.org", "X-Title": "CryptoBot"}
        )
        return clean_html(response.choices[0].message.content)
    except Exception as e:
        return f"⚠️ Error: {str(e)}"