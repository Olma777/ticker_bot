import asyncio
import os
import logging
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, CommandStart
from aiogram.types import BotCommand

from data import get_crypto_price
from analysis import get_crypto_analysis, get_sniper_analysis

load_dotenv()
token = os.getenv("BOT_TOKEN")

logging.basicConfig(level=logging.INFO)

bot = Bot(token=token)
dp = Dispatcher()

async def setup_bot_commands():
    commands = [
        BotCommand(command="/start", description="Перезапуск бота"),
        BotCommand(command="/sniper", description="Поиск точки входа"),
        BotCommand(command="/deep", description="Фундаментальный анализ"),
    ]
    await bot.set_my_commands(commands)

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 <b>Терминал готов.</b>\n\n"
        "📈 <b>Цена:</b> отправь тикер (<code>ICP</code>)\n"
        "🎯 <b>Снайпер:</b> <code>/sniper ICP</code>\n"
        "🧠 <b>Анализ:</b> <code>/deep ICP</code>",
        parse_mode="HTML"
    )

# --- SNIPER ---
@dp.message(Command("sniper"))
async def sniper_handler(message: types.Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Укажи тикер. Пример: <code>/sniper ETH</code>", parse_mode="HTML")
        return

    ticker = args[1].upper()
    loading_msg = await message.answer(f"🎯 Ищу точку входа для <b>{ticker}</b>...", parse_mode="HTML")
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    info, error = await get_crypto_price(ticker)
    
    if error:
        await loading_msg.delete()
        await message.answer(f"❌ Не удалось найти цену для {ticker}.")
        return

    price = info['price'] 
    analysis_text = await get_sniper_analysis(ticker, price)

    await loading_msg.delete()
    await message.answer(analysis_text, parse_mode="Markdown")

# --- DEEP ANALYSIS ---
@dp.message(Command("deep"))
async def deep_analysis_handler(message: types.Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Укажи тикер. Пример: <code>/deep BTC</code>", parse_mode="HTML")
        return

    ticker = args[1].upper()
    loading_msg = await message.answer(f"🧠 Изучаю <b>{ticker}</b>...", parse_mode="HTML")
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")

    analysis_text = await get_crypto_analysis(ticker)

    await loading_msg.delete()
    await message.answer(analysis_text, parse_mode="Markdown")

# --- ПРОСТО ТИКЕР (УЛУЧШЕННЫЙ ВЫВОД) ---
@dp.message()
async def get_price_handler(message: types.Message):
    ticker = message.text.upper().replace("/", "")
    if len(ticker) > 6: return

    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    info, error = await get_crypto_price(ticker)

    if error:
        await message.answer("Тикер не найден. Попробуй /sniper.")
    else:
        # 1. Формируем первую строку
        header = f"🪙 <b>{info['name']}</b> ({info['ticker']})"
        
        # 2. Добавляем ранг, ТОЛЬКО если он известен (не "?")
        if info['rank'] != "?":
            header += f" #{info['rank']}"
            
        # 3. Собираем ответ
        response = (
            f"{header}\n"
            f"💵 <b>Текущая цена:</b> ${info['price']}"
        )
        await message.answer(response, parse_mode="HTML")

async def main():
    print("Бот запускается...")
    await setup_bot_commands()
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот выключен.")