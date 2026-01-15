import asyncio
import os
import logging
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.types import BotCommand, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from prices import get_crypto_price
from analysis import get_crypto_analysis, get_sniper_analysis

load_dotenv()
token = os.getenv("BOT_TOKEN")

logging.basicConfig(level=logging.INFO)

bot = Bot(token=token)
dp = Dispatcher()

# База данных языков в памяти
user_languages = {}

async def setup_bot_commands():
    commands = [
        BotCommand(command="/start", description="Restart / Перезапуск"),
        BotCommand(command="/sniper", description="Trading / Трейдинг"),
        BotCommand(command="/audit", description="Audit / Аудит"),
    ]
    await bot.set_my_commands(commands)

# --- 1. ВЫБОР ЯЗЫКА (БЕЗ ФЛАГОВ) ---
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    # Строгие кнопки без эмодзи
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Русский", callback_data="lang_ru"),
            InlineKeyboardButton(text="English", callback_data="lang_en")
        ]
    ])
    
    await message.answer(
        "👋 <b>Welcome! / Добро пожаловать!</b>\n\n"
        "Please choose your language:\n"
        "Пожалуйста, выберите язык:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

# --- 2. ОБРАБОТКА ВЫБОРА ---
@dp.callback_query(F.data.startswith("lang_"))
async def language_selection(callback: CallbackQuery):
    lang_code = callback.data.split("_")[1]
    user_id = callback.from_user.id
    
    user_languages[user_id] = lang_code
    
    if lang_code == "ru":
        text = (
            "✅ <b>Язык установлен: Русский</b>\n\n"
            "👇 <b>Меню:</b>\n"
            "1️⃣ <b>Котировки:</b> Отправь тикер (<code>TON</code>)\n"
            "2️⃣ <b>Трейдинг:</b> <code>/sniper TON</code>\n"
            "3️⃣ <b>Аудит:</b> <code>/audit TON</code>"
        )
    else:
        text = (
            "✅ <b>Language set: English</b>\n\n"
            "👇 <b>Menu:</b>\n"
            "1️⃣ <b>Quotes:</b> Send ticker (<code>TON</code>)\n"
            "2️⃣ <b>Trading:</b> <code>/sniper TON</code>\n"
            "3️⃣ <b>Audit:</b> <code>/audit TON</code>"
        )
        
    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer()

# --- 3. SNIPER ---
@dp.message(Command("sniper"))
async def sniper_handler(message: types.Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Example: <code>/sniper BTC</code>", parse_mode="HTML")
        return

    ticker = args[1].upper()
    user_id = message.from_user.id
    lang = user_languages.get(user_id, "ru") 
    
    status_text = "🎯 Анализирую..." if lang == "ru" else "🎯 Analyzing..."
    loading_msg = await message.answer(f"<b>{ticker}</b>: {status_text}", parse_mode="HTML")
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    info, error = await get_crypto_price(ticker)
    
    if error:
        await loading_msg.delete()
        err_text = "❌ Тикер не найден." if lang == "ru" else "❌ Ticker not found."
        await message.answer(err_text)
        return

    analysis_text = await get_sniper_analysis(ticker, info['name'], info['price'], lang=lang)

    await loading_msg.delete()
    await message.answer(analysis_text, parse_mode="HTML")

# --- 4. AUDIT ---
@dp.message(Command("audit"))
async def audit_handler(message: types.Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Example: <code>/audit BTC</code>", parse_mode="HTML")
        return

    ticker = args[1].upper()
    user_id = message.from_user.id
    lang = user_languages.get(user_id, "ru")

    status_text = "🛡 Проверяю..." if lang == "ru" else "🛡 Auditing..."
    loading_msg = await message.answer(f"<b>{ticker}</b>: {status_text}", parse_mode="HTML")
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")

    info, error = await get_crypto_price(ticker)
    if error:
        await loading_msg.delete()
        err_text = "❌ Тикер не найден." if lang == "ru" else "❌ Ticker not found."
        await message.answer(err_text)
        return

    analysis_text = await get_crypto_analysis(ticker, info['name'], lang=lang)

    await loading_msg.delete()
    await message.answer(analysis_text, parse_mode="HTML")

# --- 5. PRICE ---
@dp.message()
async def get_price_handler(message: types.Message):
    ticker = message.text.upper().replace("/", "")
    if len(ticker) > 6: return

    user_id = message.from_user.id
    lang = user_languages.get(user_id, "ru")

    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    info, error = await get_crypto_price(ticker)

    if error:
        help_text = "Тикер не найден." if lang == "ru" else "Ticker not found."
        await message.answer(help_text)
    else:
        if lang == "ru":
            price_label = "Текущая цена"
        else:
            price_label = "Current Price"

        header = f"🪙 <b>{info['name']}</b> ({info['ticker']})"
        if info['rank'] != "?":
            header += f" #{info['rank']}"
            
        response = (
            f"{header}\n"
            f"💵 <b>{price_label}:</b> ${info['price']}"
        )
        await message.answer(response, parse_mode="HTML")

async def main():
    print("Bot is starting...")
    await setup_bot_commands()
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped.")