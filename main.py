import asyncio
import logging
import sys
import os
from datetime import datetime
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.enums import ParseMode

# Подключаем планировщик
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Импорт наших модулей
from prices import get_crypto_price, get_market_summary
from analysis import get_crypto_analysis, get_sniper_analysis, get_daily_briefing

# Загрузка переменных
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

# Логирование
logging.basicConfig(level=logging.INFO)

# Инициализация бота
bot = Bot(token=TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

# --- ВРЕМЕННАЯ БАЗА ДАННЫХ (В ПАМЯТИ) ---
# Формат: { user_id: hour_int }
USER_SETTINGS = {}

# --- КЛАВИАТУРА ВЫБОРА ВРЕМЕНИ ---
def get_time_keyboard():
    buttons = []
    # Создаем кнопки с 07:00 до 12:00
    hours = [7, 8, 9, 10, 11, 12] 
    
    row = []
    for h in hours:
        btn_text = f"{h:02d}:00"
        row.append(InlineKeyboardButton(text=btn_text, callback_data=f"set_time_{h}"))
        
    buttons.append(row)
    buttons.append([InlineKeyboardButton(text="🔕 Отключить рассылку", callback_data="set_time_off")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# --- ПЛАНИРОВЩИК (РАБОТАЕТ КАЖДЫЙ ЧАС) ---
async def check_and_send_briefings():
    current_hour = datetime.now().hour
    users_to_send = [uid for uid, hour in USER_SETTINGS.items() if hour == current_hour]
    
    if not users_to_send:
        return

    print(f"⏰ {current_hour}:00. Отправка брифинга для {len(users_to_send)} чел.")

    try:
        # Генерируем контент ОДИН РАЗ
        market_data = await get_market_summary()
        briefing_text = await get_daily_briefing(market_data)
        
        # Рассылаем
        for user_id in users_to_send:
            try:
                await bot.send_message(user_id, briefing_text, parse_mode=ParseMode.HTML)
            except Exception:
                if user_id in USER_SETTINGS:
                    del USER_SETTINGS[user_id]
    except Exception as e:
        print(f"⚠️ Ошибка рассылки: {e}")

# --- ОБРАБОТЧИКИ КОМАНД ---

@dp.message(Command("start"))
async def start_handler(message: Message):
    # По умолчанию подписываем на 9 утра
    if message.from_user.id not in USER_SETTINGS:
        USER_SETTINGS[message.from_user.id] = 9
        
    await message.answer(
        "👋 <b>Добро пожаловать в AI Crypto Analyst!</b>\n\n"
        "✅ <b>Вы успешно подписаны на «Утренний Брифинг».</b>\n"
        "Каждый день ровно в <b>09:00</b> я буду присылать вам:\n"
        "• Макро-настроение рынка\n"
        "• Горячий сектор дня\n"
        "• Топ монет со скрытой аккумуляцией\n\n"
        "⚙️ <b>Неудобное время?</b>\n"
        "Нажмите /time, чтобы выбрать час рассылки или отключить её.\n\n"
        "<b>👇 Мои инструменты (доступны 24/7):</b>\n"
        "🦅 <code>/sniper [тикер]</code> — Найти точку входа (SMC)\n"
        "🛡 <code>/audit [тикер]</code> — Проверить токеномику\n"
        "🌅 <code>/daily</code> — Получить брифинг прямо сейчас",
        parse_mode=ParseMode.HTML
    )

@dp.message(Command("time"))
async def time_handler(message: Message):
    current_time = USER_SETTINGS.get(message.from_user.id, "Отключено")
    if current_time != "Отключено":
        current_time = f"{current_time:02d}:00"
        
    await message.answer(
        f"⏰ <b>Настройка рассылки</b>\n"
        f"Текущее время: <b>{current_time}</b>\n\n"
        "Выберите, во сколько вам удобно получать аналитику:",
        reply_markup=get_time_keyboard(),
        parse_mode=ParseMode.HTML
    )

@dp.callback_query(F.data.startswith("set_time_"))
async def callback_time(callback: CallbackQuery):
    action = callback.data.split("_")[2]
    user_id = callback.from_user.id
    
    if action == "off":
        if user_id in USER_SETTINGS:
            del USER_SETTINGS[user_id]
        await callback.message.edit_text("🔕 <b>Рассылка отключена.</b>\nВы не будете получать утренние брифинги.\nВключить снова: /time", parse_mode=ParseMode.HTML)
    else:
        hour = int(action)
        USER_SETTINGS[user_id] = hour
        await callback.message.edit_text(f"✅ <b>Время установлено!</b>\nЯ буду присылать брифинг каждый день в <b>{hour:02d}:00</b>.", parse_mode=ParseMode.HTML)
    
    await callback.answer()

# --- ОСТАЛЬНЫЕ КОМАНДЫ ---

@dp.message(Command("audit"))
async def audit_handler(message: Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Пример: <code>/audit SOL</code>", parse_mode=ParseMode.HTML)
        return
    ticker = args[1].upper()
    loading_msg = await message.answer(f"🛡 <b>Аудит {ticker}...</b>", parse_mode=ParseMode.HTML)
    try:
        price_data, error = await get_crypto_price(ticker)
        if not price_data:
            await loading_msg.edit_text("❌ Тикер не найден.")
            return
        text = await get_crypto_analysis(ticker, price_data['name'], "ru")
        await loading_msg.delete()
        await message.answer(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        await loading_msg.edit_text(f"Ошибка: {e}")

@dp.message(Command("sniper"))
async def sniper_handler(message: Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Пример: <code>/sniper BTC</code>", parse_mode=ParseMode.HTML)
        return
    ticker = args[1].upper()
    loading_msg = await message.answer(f"🦅 <b>Снайпер-анализ {ticker}...</b>", parse_mode=ParseMode.HTML)
    try:
        price_data, error = await get_crypto_price(ticker)
        if not price_data:
            await loading_msg.edit_text("❌ Тикер не найден.")
            return
        text = await get_sniper_analysis(ticker, price_data['name'], price_data['price'], "ru")
        await loading_msg.delete()
        await message.answer(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        await loading_msg.edit_text(f"Ошибка: {e}")

@dp.message(Command("daily"))
async def daily_manual_handler(message: Message):
    # Если вручную вызвал daily - тоже подписываем (если не был подписан)
    if message.from_user.id not in USER_SETTINGS:
         USER_SETTINGS[message.from_user.id] = 9

    loading_msg = await message.answer("☕️ <b>Готовлю брифинг...</b>", parse_mode=ParseMode.HTML)
    try:
        market_data = await get_market_summary()
        text = await get_daily_briefing(market_data)
        await loading_msg.delete()
        await message.answer(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        await loading_msg.edit_text(f"Ошибка: {e}")

# --- ЗАПУСК ---
async def main():
    scheduler.add_job(check_and_send_briefings, 'cron', minute=0)
    scheduler.start()
    print("🤖 Бот запущен! Планировщик активен.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Bot stopped!")