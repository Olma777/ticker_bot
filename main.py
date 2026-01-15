import asyncio
import os
import logging
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, CommandStart
from aiogram.types import BotCommand

# Импортируем функции
from data import get_crypto_price
from analysis import get_crypto_analysis, get_sniper_analysis # <--- Добавили снайпера

load_dotenv()
token = os.getenv("BOT_TOKEN")

logging.basicConfig(level=logging.INFO)

bot = Bot(token=token)
dp = Dispatcher()

async def setup_bot_commands():
    commands = [
        BotCommand(command="/start", description="Перезапуск бота"),
        BotCommand(command="/t", description="Быстрая цена"),
        BotCommand(command="/deep", description="Фундаментальный анализ"),
        BotCommand(command="/sniper", description="Поиск точки входа (Setup)"), # <--- Новая команда
    ]
    await bot.set_my_commands(commands)

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 <b>Крипто-терминал готов к работе.</b>\n\n"
        "📈 <b>Цена:</b> просто тикер (<code>SOL</code>)\n"
        "🧠 <b>Фундаментал:</b> <code>/deep SOL</code>\n"
        "🎯 <b>Снайпер-сетап:</b> <code>/sniper SOL</code>\n\n"
        "<i>Выбери инструмент для работы.</i>",
        parse_mode="HTML"
    )

# --- КОМАНДА SNIPER (Заменила новости) ---
@dp.message(Command("sniper"))
async def sniper_handler(message: types.Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Укажи тикер. Пример: <code>/sniper ETH</code>", parse_mode="HTML")
        return

    ticker = args[1].upper()
    
    # 1. Сначала узнаем актуальную цену
    loading_msg = await message.answer(f"🎯 Ищу точку входа для <b>{ticker}</b>... Анализирую стакан и графики...", parse_mode="HTML")
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    price, error = await get_crypto_price(ticker)
    
    if error:
        await loading_msg.delete()
        await message.answer(f"❌ Не удалось найти цену для {ticker}. Проверь тикер.")
        return

    # 2. Делаем анализ с учетом цены
    analysis_text = await get_sniper_analysis(ticker, price)

    await loading_msg.delete()
    await message.answer(analysis_text, parse_mode="Markdown")

# --- КОМАНДА DEEP (Старый анализ) ---
@dp.message(Command("deep"))
async def deep_analysis_handler(message: types.Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Укажи тикер. Пример: <code>/deep BTC</code>", parse_mode="HTML")
        return

    ticker = args[1].upper()
    loading_msg = await message.answer(f"🧠 Изучаю токеномику <b>{ticker}</b>...", parse_mode="HTML")
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")

    analysis_text = await get_crypto_analysis(ticker)

    await loading_msg.delete()
    await message.answer(analysis_text, parse_mode="Markdown")

# --- ПРОСТО ЦЕНА ---
@dp.message()
async def get_price_handler(message: types.Message):
    ticker = message.text.upper().replace("/", "")
    if len(ticker) > 6: return

    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    price, error = await get_crypto_price(ticker)

    if error:
        await message.answer("Тикер не найден. Попробуй /sniper или /deep.")
    else:
        await message.answer(f"💰 <b>{ticker}</b>: ${price}", parse_mode="HTML")

async def main():
    print("Бот запускается...")
    await setup_bot_commands()
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот выключен.")