import asyncio
import os
import logging
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, CommandStart
from aiogram.types import BotCommand

# ВАЖНО: Теперь мы импортируем из prices, а не data
from prices import get_crypto_price
from analysis import get_crypto_analysis, get_sniper_analysis

load_dotenv()
token = os.getenv("BOT_TOKEN")

logging.basicConfig(level=logging.INFO)

bot = Bot(token=token)
dp = Dispatcher()

async def setup_bot_commands():
    commands = [
        BotCommand(command="/start", description="Перезапуск бота"),
        BotCommand(command="/sniper", description="Трейдинг (Маркетмейкер)"),
        BotCommand(command="/audit", description="Аудит (Риски и Потенциал)"),
    ]
    await bot.set_my_commands(commands)

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    user_name = message.from_user.first_name
    await message.answer(
        f"👋 <b>Привет, {user_name}!</b>\n\n"
        "Я твой <b>AI-терминал V2.0</b>.\n\n"
        "👇 <b>Меню:</b>\n\n"
        "1️⃣ <b>Котировки:</b>\n"
        "Просто отправь тикер (<code>SOL</code>) — покажу цену и рейтинг.\n\n"
        "2️⃣ <b>Свинг-Трейдинг:</b>\n"
        "Команда <code>/sniper SOL</code>\n"
        "<i>Ищет манипуляции, ликвидность и дает сетап на вход.</i>\n\n"
        "3️⃣ <b>Аудит Проекта:</b>\n"
        "Команда <code>/audit SOL</code>\n"
        "<i>Проверка на скам, анализ команды и рисков.</i>",
        parse_mode="HTML"
    )

# --- SNIPER ---
@dp.message(Command("sniper"))
async def sniper_handler(message: types.Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Пример: <code>/sniper BTC</code>", parse_mode="HTML")
        return

    ticker = args[1].upper()
    loading_msg = await message.answer(f"🎯 <b>{ticker}</b>: Анализирую рынок...", parse_mode="HTML")
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    info, error = await get_crypto_price(ticker)
    
    if error:
        await loading_msg.delete()
        await message.answer(f"❌ Тикер {ticker} не найден.")
        return

    # Передаем: Тикер, Имя, Цену
    analysis_text = await get_sniper_analysis(ticker, info['name'], info['price'])

    await loading_msg.delete()
    await message.answer(analysis_text, parse_mode="HTML")

# --- AUDIT ---
@dp.message(Command("audit"))
async def audit_handler(message: types.Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Пример: <code>/audit BTC</code>", parse_mode="HTML")
        return

    ticker = args[1].upper()
    loading_msg = await message.answer(f"🛡 <b>{ticker}</b>: Проверяю безопасность...", parse_mode="HTML")
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")

    info, error = await get_crypto_price(ticker)
    
    if error:
        await loading_msg.delete()
        await message.answer(f"❌ Тикер {ticker} не найден.")
        return

    # Передаем: Тикер, Имя
    analysis_text = await get_crypto_analysis(ticker, info['name'])

    await loading_msg.delete()
    await message.answer(analysis_text, parse_mode="HTML")

# --- PRICE ---
@dp.message()
async def get_price_handler(message: types.Message):
    ticker = message.text.upper().replace("/", "")
    if len(ticker) > 6: return

    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    info, error = await get_crypto_price(ticker)

    if error:
        await message.answer("Тикер не найден. Попробуй /sniper или /audit.")
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