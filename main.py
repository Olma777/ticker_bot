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
        BotCommand(command="/sniper", description="Свинг-трейдинг (MM Analysis)"),
        BotCommand(command="/deep", description="Фундаментальный Инвест-анализ"),
    ]
    await bot.set_my_commands(commands)

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 <b>Крипто-терминал V2.0</b>\n\n"
        "📈 <b>Котировки:</b> отправь тикер (<code>SOL</code>)\n"
        "🎯 <b>Свинг-сетап:</b> <code>/sniper SOL</code>\n"
        "🧠 <b>Инвестиции:</b> <code>/deep SOL</code>",
        parse_mode="HTML"
    )

# --- КОМАНДА SNIPER (Свинг / Маркетмейкер) ---
@dp.message(Command("sniper"))
async def sniper_handler(message: types.Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Укажи тикер. Пример: <code>/sniper ETH</code>", parse_mode="HTML")
        return

    ticker = args[1].upper()
    loading_msg = await message.answer(f"🎯 <b>{ticker}</b>: Анализирую действия маркетмейкера...", parse_mode="HTML")
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    # 1. Получаем данные (Цену + Имя)
    info, error = await get_crypto_price(ticker)
    
    if error:
        await loading_msg.delete()
        await message.answer(f"❌ Не удалось найти данные для {ticker}.")
        return

    # 2. Передаем в анализ (Тикер, Имя, Цену)
    analysis_text = await get_sniper_analysis(ticker, info['name'], info['price'])

    await loading_msg.delete()
    await message.answer(analysis_text, parse_mode="Markdown")

# --- КОМАНДА DEEP (Фундаментал / Инвестиции) ---
@dp.message(Command("deep"))
async def deep_analysis_handler(message: types.Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Укажи тикер. Пример: <code>/deep BTC</code>", parse_mode="HTML")
        return

    ticker = args[1].upper()
    loading_msg = await message.answer(f"🧠 <b>{ticker}</b>: Читаю Whitepaper и токеномику...", parse_mode="HTML")
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")

    # 1. Получаем имя монеты (цена тут менее важна, но нужна для проверки существования)
    info, error = await get_crypto_price(ticker)
    
    if error:
        await loading_msg.delete()
        await message.answer(f"❌ Не удалось найти данные для {ticker}.")
        return

    # 2. Передаем в анализ (Тикер, Имя)
    analysis_text = await get_crypto_analysis(ticker, info['name'])

    await loading_msg.delete()
    await message.answer(analysis_text, parse_mode="Markdown")

# --- ПРОСТО ТИКЕР (Цена) ---
@dp.message()
async def get_price_handler(message: types.Message):
    ticker = message.text.upper().replace("/", "")
    if len(ticker) > 6: return

    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    info, error = await get_crypto_price(ticker)

    if error:
        await message.answer("Тикер не найден. Попробуй /sniper.")
    else:
        header = f"🪙 <b>{info['name']}</b> ({info['ticker']})"
        if info['rank'] != "?":
            header += f" #{info['rank']}"
            
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