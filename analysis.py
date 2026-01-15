import os
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

# Настройка клиента OpenRouter (DeepSeek V3)
client = AsyncOpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url="https://openrouter.ai/api/v1"
)

MODEL_NAME = "deepseek/deepseek-chat"

# --- 1. ФУНДАМЕНТАЛЬНЫЙ ИНВЕСТ-АНАЛИЗ (/deep) ---
async def get_crypto_analysis(ticker, full_name):
    system_prompt = f"""
    Ты профессиональный венчурный крипто-инвестор и фундаментальный аналитик.
    Твоя задача — провести глубокий анализ проекта {full_name} ({ticker}) для долгосрочного инвестирования.
    
    ИСПОЛЬЗУЙ ЭТОТ ШАБЛОН:

    1. Фундаментальная ценность и экосистема:
       - Суть проекта: Utility, USP, Технологическое преимущество.
       - Конкуренты: Кто они и чем этот проект лучше?
       - Roadmap и команда: Компетенции и планы.

    2. Метрики и Токеномика:
       - Рост: TVL, активные адреса, транзакции.
       - Токеномика: Инфляция/дефляция, вестинги (разблокировки), ютилити токена.
       - Драйверы роста: Катализаторы будущего успеха.

    3. Макро и Рынок:
       - Глобальные факторы: Влияние ставок, ликвидности.
       - Корреляция с BTC.
       - Рыночная позиция: Капитализация и ликвидность.

    4. Риски и Возможности:
       - Риски: Регуляция, технологии, безопасность.
       - Возможности: Партнерства, тренды.

    5. Долгосрочный прогноз (Качественный):
       - Потенциал цены (без конкретных сигналов входа, только инвестиционный взгляд).

    6. Формат вывода: Markdown для Telegram.
    """

    try:
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "Ты эксперт по фундаментальному анализу криптовалют."},
                {"role": "user", "content": system_prompt}
            ],
            extra_headers={
                "HTTP-Referer": "https://telegram.org",
                "X-Title": "CryptoBot"
            }
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"⚠️ Ошибка фундаментального анализа: {str(e)}"


# --- 2. СВИНГ-ТРЕЙДИНГ И MM АНАЛИЗ (/sniper) ---
async def get_sniper_analysis(ticker, full_name, price):
    system_prompt = f"""
    Пожалуйста, проведи глубокий среднесрочный анализ монеты {full_name} ({ticker}) на основе цены ${price}.
    Ты — профессиональный трейдер, специализирующийся на действиях Маркетмейкера (Smart Money).

    ИСПОЛЬЗУЙ ЭТОТ ШАБЛОН:

    1. Ключевые уровни (Daily/Weekly):
       - Сильные уровни поддержки и сопротивления (границы диапазонов).

    2. Фаза рынка и Тренд:
       - Фаза: Накопление, Тренд, Распределение.
       - Структура: Канал, боковик, разворот.

    3. Настроение и Крупный игрок:
       - Индикаторы: Open Interest, Funding Rates, Long/Short. Есть ли дисбаланс?
       - Действия Маркетмейкера:
         * Аккумуляция/Распределение.
         * "Liquidity Hunter": Где стопы толпы?
         * "Spoofing": Есть ли манипуляции в стакане?

    4. Фьючерсный сигнал (Свинг):
       - НАПРАВЛЕНИЕ: [ЛОНГ или ШОРТ] (Только одно).
       - Точка входа: Оптимальный уровень.
       - 3 Тейк-профита.
       - Усреднение: Безопасные уровни.
       - Стоп-лосс: Уровень отмены сценария.

    5. Выведи всё в формате Telegram markdown.
    """

    try:
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "Ты профессиональный свинг-трейдер."},
                {"role": "user", "content": system_prompt}
            ],
            extra_headers={
                "HTTP-Referer": "https://telegram.org",
                "X-Title": "CryptoBot"
            }
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"⚠️ Ошибка снайпер-анализа: {str(e)}"