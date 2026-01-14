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

load_dotenv()
token = os.getenv("BOT_TOKEN")

logging.basicConfig(level=logging.INFO)

bot = Bot(token=token)
dp = Dispatcher()

# Настройка меню команд (кнопка Menu слева внизу)
async def setup_bot_commands():
    commands = [
        BotCommand(command="/start", description="Перезапуск бота"),
        BotCommand(command="/t", description="Быстрая цена (например: /t SOL)"),
        BotCommand(command="/deep", description="Глубокий AI-анализ (например: /deep ETH)"),
    ]
    await bot.set_my_commands(commands)

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 Привет! Я готов.\n\n"
        "📈 <b>Узнать цену:</b> напиши тикер (напр. <code>SOL</code>)\n"
        "🧠 <b>Глубокий анализ:</b> нажми /deep и тикер (напр. <code>/deep TON</code>)",
        parse_mode="HTML"
    )

# Команда /deep (Глубокий анализ)
@dp.message(Command("deep"))
async def deep_analysis_handler(message: types.Message):
    # Получаем аргументы (всё, что после /deep)
    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Укажи тикер. Пример: <code>/deep BTC</code>", parse_mode="HTML")
        return

    ticker = args[1].upper()
    
    # Сообщение "Думаю...", так как анализ занимает 5-10 секунд
    loading_msg = await message.answer(f"🧠 Анализирую <b>{ticker}</b>... Это займет около 10-20 секунд.", parse_mode="HTML")
    
    # Запускаем "крутилку" в статусе бота
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")

    # Идем в OpenAI
    analysis_text = await get_crypto_analysis(ticker)

    # Удаляем сообщение "Анализирую..." и отправляем результат
    await loading_msg.delete()
    await message.answer(analysis_text, parse_mode="Markdown")

# Просто тикер (Быстрая цена)
@dp.message()
async def get_price_handler(message: types.Message):
    ticker = message.text.upper().replace("/", "") # Убираем слэш, если юзер написал /SOL
    
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    price, error = await get_crypto_price(ticker)

    if error:
        # Если не нашли цену, может юзер просто болтает?
        await message.answer("Я понимаю только тикеры (SOL, BTC) или команду /deep для анализа.")
    else:
        await message.answer(
            f"💰 <b>{ticker}</b>: ${price}\n"
            f"ℹ️ <i>Данные CoinGecko</i>", 
            parse_mode="HTML"
        )

async def main():
    print("Бот запускается...")
    await setup_bot_commands() # Добавляем меню
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот выключен.")