import asyncio
import os
import logging
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, CommandStart
from aiogram.types import BotCommand

# Импортируем наши функции
from data import get_crypto_price
from analysis import get_crypto_analysis
from news import get_crypto_news  # <--- НОВОЕ

load_dotenv()
token = os.getenv("BOT_TOKEN")

logging.basicConfig(level=logging.INFO)

bot = Bot(token=token)
dp = Dispatcher()

async def setup_bot_commands():
    commands = [
        BotCommand(command="/start", description="Перезапуск бота"),
        BotCommand(command="/t", description="Быстрая цена (например: /t SOL)"),
        BotCommand(command="/deep", description="Глубокий AI-анализ"),
        BotCommand(command="/news", description="Последние новости"), # <--- НОВОЕ
    ]
    await bot.set_my_commands(commands)

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 Привет! Я твой крипто-терминал.\n\n"
        "📈 <b>Цена:</b> просто тикер (<code>SOL</code>)\n"
        "🧠 <b>Анализ:</b> <code>/deep SOL</code>\n"
        "📰 <b>Новости:</b> <code>/news SOL</code>",
        parse_mode="HTML"
    )

# Команда /news
@dp.message(Command("news"))
async def news_handler(message: types.Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Укажи тикер. Пример: <code>/news BTC</code>", parse_mode="HTML")
        return

    ticker = args[1].upper()
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    # Получаем новости
    news_text = await get_crypto_news(ticker)
    
    # Отправляем (disable_web_page_preview=True, чтобы не было кучи картинок)
    await message.answer(news_text, parse_mode="HTML", disable_web_page_preview=True)

# Команда /deep
@dp.message(Command("deep"))
async def deep_analysis_handler(message: types.Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Укажи тикер. Пример: <code>/deep BTC</code>", parse_mode="HTML")
        return

    ticker = args[1].upper()
    loading_msg = await message.answer(f"🧠 Анализирую <b>{ticker}</b>... Жди 10-20 сек.", parse_mode="HTML")
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")

    analysis_text = await get_crypto_analysis(ticker)

    await loading_msg.delete()
    await message.answer(analysis_text, parse_mode="Markdown")

# Просто тикер (Цена)
@dp.message()
async def get_price_handler(message: types.Message):
    ticker = message.text.upper().replace("/", "")
    
    # Игнорируем длинные сообщения (не похожие на тикеры)
    if len(ticker) > 6:
        return

    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    price, error = await get_crypto_price(ticker)

    if error:
        await message.answer("Не нашел такой тикер. Попробуй /news или /deep.")
    else:
        await message.answer(
            f"💰 <b>{ticker}</b>: ${price}", 
            parse_mode="HTML"
        )

async def main():
    print("Бот запускается...")
    await setup_bot_commands()
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот выключен.")