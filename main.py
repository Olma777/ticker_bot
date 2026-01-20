import asyncio
import logging
import sys
import os
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ParseMode

# Импорт наших модулей
# prices.py должен содержать get_crypto_price и get_market_summary
from prices import get_crypto_price, get_market_summary
# analysis.py должен содержать все функции, которые мы написали выше
from analysis import get_crypto_analysis, get_sniper_analysis, get_daily_briefing

# Загрузка переменных
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

# Логирование
logging.basicConfig(level=logging.INFO)

# Инициализация бота
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- START / HELP ---
@dp.message(Command("start"))
async def start_handler(message: Message):
    await message.answer(
        "👋 <b>Привет! Я AI Crypto Analyst.</b>\n\n"
        "Я умею находить гемы, анализировать графики и проверять проекты.\n\n"
        "<b>Мои команды:</b>\n"
        "🦅 <code>/sniper [тикер]</code> — Найти точку входа (SMC Setup)\n"
        "🛡 <code>/audit [тикер]</code> — Фундаментальный разбор (VC Audit)\n"
        "🌅 <code>/daily</code> — Утренний брифинг рынка\n\n"
        "<i>Пример: /sniper BTC</i>",
        parse_mode=ParseMode.HTML
    )

@dp.message(Command("help"))
async def help_handler(message: Message):
    await message.answer(
        "<b>Как пользоваться ботом:</b>\n\n"
        "1. <b>Торговля:</b> Напиши <code>/sniper ETH</code>, чтобы получить сетап для сделки (Вход, Стоп, Тейк).\n"
        "2. <b>Инвестиции:</b> Напиши <code>/audit TON</code>, чтобы проверить токеномику и риски проекта.\n"
        "3. <b>Рынок:</b> Напиши <code>/daily</code>, чтобы получить сводку трендов на сегодня.\n\n"
        "⚠️ <i>Бот использует ИИ (DeepSeek). Это не финансовый совет. DYOR.</i>",
        parse_mode=ParseMode.HTML
    )

# --- AUDIT HANDLER ---
@dp.message(Command("audit"))
async def audit_handler(message: Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Введите тикер монеты.\nПример: <code>/audit SOL</code>", parse_mode=ParseMode.HTML)
        return

    ticker = args[1].upper()
    loading_msg = await message.answer(f"🛡 <b>Провожу аудит {ticker}...</b>\n<i>Анализирую безопасность, токеномику и конкурентов...</i>", parse_mode=ParseMode.HTML)

    try:
        # 1. Получаем цену и полное имя
        price_data, error = await get_crypto_price(ticker)
        if not price_data:
            await loading_msg.edit_text(f"❌ Тикер <b>{ticker}</b> не найден.", parse_mode=ParseMode.HTML)
            return

        full_name = price_data['name']
        
        # 2. Запрашиваем анализ у ИИ
        analysis_text = await get_crypto_analysis(ticker, full_name, lang="ru")

        # 3. Отправляем результат
        await loading_msg.delete()
        await message.answer(analysis_text, parse_mode=ParseMode.HTML)

    except Exception as e:
        await loading_msg.edit_text(f"⚠️ Ошибка: {str(e)}")

# --- SNIPER HANDLER ---
@dp.message(Command("sniper"))
async def sniper_handler(message: Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Введите тикер.\nПример: <code>/sniper BTC</code>", parse_mode=ParseMode.HTML)
        return

    ticker = args[1].upper()
    loading_msg = await message.answer(f"🦅 <b>Ищу сделку по {ticker}...</b>\n<i>Анализирую ликвидность, структуру и уровни...</i>", parse_mode=ParseMode.HTML)

    try:
        # 1. Получаем цену
        price_data, error = await get_crypto_price(ticker)
        if not price_data:
            await loading_msg.edit_text(f"❌ Тикер <b>{ticker}</b> не найден.", parse_mode=ParseMode.HTML)
            return

        full_name = price_data['name']
        price = price_data['price']

        # 2. Запрашиваем анализ у ИИ
        analysis_text = await get_sniper_analysis(ticker, full_name, price, lang="ru")

        # 3. Отправляем результат
        await loading_msg.delete()
        await message.answer(analysis_text, parse_mode=ParseMode.HTML)

    except Exception as e:
        await loading_msg.edit_text(f"⚠️ Ошибка: {str(e)}")

# --- DAILY BRIEFING HANDLER ---
@dp.message(Command("daily"))
async def daily_handler(message: Message):
    loading_msg = await message.answer("☕️ <b>Готовлю утренний брифинг...</b>\n<i>Собираю макро-данные и ищу нарративы...</i>", parse_mode=ParseMode.HTML)
    
    try:
        # 1. Собираем сырые данные (Цены, Топы)
        market_data = await get_market_summary()
        
        # 2. Генерируем аналитику через ИИ
        briefing_text = await get_daily_briefing(market_data)
        
        # 3. Отправляем результат
        await loading_msg.delete()
        await message.answer(briefing_text, parse_mode=ParseMode.HTML)
        
    except Exception as e:
        await loading_msg.edit_text(f"⚠️ Не удалось собрать брифинг. Ошибка: {str(e)}")

# --- MAIN ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Bot stopped!")