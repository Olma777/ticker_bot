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
        BotCommand(command="/sniper", description="Трейдинг (Маркетмейкер)"),
        BotCommand(command="/audit", description="🛡 Аудит проекта (Риски)"), # Новая команда
    ]
    await bot.set_my_commands(commands)

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    user_name = message.from_user.first_name
    await message.answer(
        f"👋 <b>Привет, {user_name}!</b>\n\n"
        "Я твой профессиональный крипто-терминал.\n\n"
        "👇 <b>Доступные инструменты:</b>\n\n"
        "1️⃣ <b>Котировки (Live):</b>\n"
        "Просто отправь тикер (<code>SOL</code>) — покажу цену и рейтинг.\n\n"
        "2️⃣ <b>Свинг-Трейдинг (Setup):</b>\n"
        "Команда <code>/sniper SOL</code>\n"
        "<i>Поиск манипуляций, уровней ликвидности и точек входа для торговли.</i>\n\n"
        "3️⃣ <b>Аудит Проекта (Security):</b>\n"
        "Команда <code>/audit SOL</code>\n"
        "<i>Проверка на скам, анализ команды, токеномики и долгосрочных рисков.</i>\n\n"
        "🚀 <b>Жду тикер!</b>",
        parse_mode="HTML"
    )

# --- SNIPER (Трейдинг) ---
@dp.message(Command("sniper"))
async def sniper_handler(message: types.Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Укажи тикер. Пример: <code>/sniper ETH</code>", parse_mode="HTML")
        return

    ticker = args[1].upper()
    loading_msg = await message.answer(f"🎯 <b>{ticker}</b>: Сканирую рынок и ищу вход...", parse_mode="HTML")
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    info, error = await get_crypto_price(ticker)
    
    if error:
        await loading_msg.delete()
        await message.answer(f"❌ Не удалось найти данные для {ticker}.")
        return

    analysis_text = await get_sniper_analysis(ticker, info['name'], info['price'])

    await loading_msg.delete()
    await message.answer(analysis_text, parse_mode="Markdown")

# --- AUDIT (Аудит и Риски) ---
@dp.message(Command("audit"))
async def audit_handler(message: types.Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Укажи тикер. Пример: <code>/audit BTC</code>", parse_mode="HTML")
        return

    ticker = args[1].upper()
    loading_msg = await message.answer(f"🛡 <b>{ticker}</b>: Проверяю безопасность и токеномику...", parse_mode="HTML")
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")

    info, error = await get_crypto_price(ticker)
    
    if error:
        await loading_msg.delete()
        await message.answer(f"❌ Не удалось найти данные для {ticker}.")
        return

    analysis_text = await get_crypto_analysis(ticker, info['name'])

    await loading_msg.delete()
    await message.answer(analysis_text, parse_mode="Markdown")

# --- PRICE (Цена) ---
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