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
# Убедитесь, что запускаете бота из корня проекта: python3 -m bot.main
from bot.prices import get_crypto_price, get_market_summary
from bot.analysis import get_crypto_analysis, get_sniper_analysis, get_daily_briefing

# Загрузка переменных окружения
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    print("❌ ОШИБКА: Токен бота не найден! Убедитесь, что BOT_TOKEN есть в .env")
    sys.exit(1)

# Логирование
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
bot = Bot(token=TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

# --- ВРЕМЕННАЯ БАЗА ДАННЫХ (В ПАМЯТИ) ---
# Хранит настройки времени рассылки для пользователей.
# Формат: { user_id: hour_int }
# Пример: { 12345678: 9, 87654321: 14 }
# При перезапуске бота очищается (для продакшена нужна база данных типа SQLite/Postgres)
USER_SETTINGS = {}

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def get_time_keyboard():
    """Создает клавиатуру для выбора времени рассылки."""
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

async def check_and_send_briefings():
    """
    Запускается каждый час. Проверяет, кому нужно отправить брифинг именно сейчас.
    """
    # 1. Получаем текущий час сервера
    current_hour = datetime.now().hour
    
    # 2. Фильтруем пользователей, которые выбрали этот час
    users_to_send = [uid for uid, hour in USER_SETTINGS.items() if hour == current_hour]
    
    if not users_to_send:
        return

    logging.info(f"⏰ {current_hour}:00. Отправка брифинга для {len(users_to_send)} пользователей.")

    try:
        # 3. Генерируем контент ОДИН РАЗ для всех (экономия запросов к AI)
        market_data = await get_market_summary()
        briefing_text = await get_daily_briefing(market_data)
        
        # 4. Рассылаем
        for user_id in users_to_send:
            try:
                await bot.send_message(user_id, briefing_text, parse_mode=ParseMode.HTML)
            except Exception:
                # Если пользователь заблокировал бота, удаляем его из памяти
                if user_id in USER_SETTINGS:
                    del USER_SETTINGS[user_id]
    except Exception as e:
        logging.error(f"⚠️ Ошибка при рассылке: {e}")

# --- ОБРАБОТЧИКИ КОМАНД (HANDLERS) ---

@dp.message(Command("start"))
async def start_handler(message: Message):
    """Приветствие и онбординг."""
    # Автоматически подписываем на 09:00, если пользователя нет в базе
    if message.from_user.id not in USER_SETTINGS:
        USER_SETTINGS[message.from_user.id] = 9
        
    msg_text = (
        "👁 <b>Market Lens</b> — приватная аналитическая система\n\n"
        "🧭 для навигации в крипторынке без шума и догадок.\n\n"
        "⚙️ Система объединяет <b>точную математику</b> и <b>AI-интерпретацию</b>, "
        "чтобы выявлять действия <b>Smart Money</b>, а не пересказывать новости или индикаторы.\n\n"
        "🔒 <b>Никаких автоматических рассылок.</b>\n"
        "Вы запрашиваете — система отвечает.\n\n"
        "📌 <b>Доступные команды:</b>\n\n"
        "🎯 <code>/sniper [тикер]</code> — поиск точки входа и риска (SMC)\n"
        "🧠 <code>/audit [тикер]</code>  — разбор проекта «под капотом»\n"
        "📊 <code>/daily</code>          — сжатый рыночный контекст\n"
        "⏰ <code>/time</code>           — настройка времени брифинга"
    )

    await message.answer(msg_text, parse_mode=ParseMode.HTML)

@dp.message(Command("time"))
async def time_handler(message: Message):
    """Меню настройки времени рассылки."""
    
    # Получаем текущее время UTC
    current_utc_time = datetime.utcnow().strftime("%H:%M")

    await message.answer(
        f"🕒 <b>Настройка времени брифинга</b>\n\n"
        f"Сейчас на сервере: <b>{current_utc_time} (UTC)</b>.\n\n"
        f"⚠️ <b>Важно:</b> Бот работает по времени UTC (Гринвич).\n"
        f"Чтобы получать брифинг в <b>09:00</b> по вашему времени, посмотрите разницу с сервером.\n\n"
        f"<i>Пример: Если у вас сейчас 12:00, а на сервере 09:00 (разница 3 часа), ставьте таймер на 06:00, чтобы получить его в 9 утра.</i>\n\n"
        f"Введите желаемое время (в формате UTC) через двоеточие, например: <code>06:00</code>",
        reply_markup=get_time_keyboard(),
        parse_mode=ParseMode.HTML
    )

@dp.callback_query(F.data.startswith("set_time_"))
async def callback_time(callback: CallbackQuery):
    """Обработка нажатия кнопок времени."""
    action = callback.data.split("_")[2] # "9" или "off"
    user_id = callback.from_user.id
    
    if action == "off":
        if user_id in USER_SETTINGS:
            del USER_SETTINGS[user_id]
        await callback.message.edit_text(
            "🔕 <b>Рассылка отключена.</b>\n"
            "Я больше не буду беспокоить вас по утрам.\n"
            "Включить снова: /time", 
            parse_mode=ParseMode.HTML
        )
    else:
        hour = int(action)
        USER_SETTINGS[user_id] = hour
        await callback.message.edit_text(
            f"✅ <b>Время установлено!</b>\n"
            f"Я буду готовить для вас отчет каждый день ровно в <b>{hour:02d}:00</b>.", 
            parse_mode=ParseMode.HTML
        )
    
    await callback.answer()

@dp.message(Command("audit"))
async def audit_handler(message: Message):
    """Фундаментальный анализ монеты."""
    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Введите тикер.\nПример: <code>/audit SOL</code>", parse_mode=ParseMode.HTML)
        return
    
    ticker = args[1].upper()
    loading_msg = await message.answer(f"🛡 <b>Изучаю проект {ticker}...</b>", parse_mode=ParseMode.HTML)
    
    try:
        price_data, error = await get_crypto_price(ticker)
        if not price_data:
            await loading_msg.edit_text("❌ Тикер не найден. Проверьте название.")
            return
        
        text = await get_crypto_analysis(ticker, price_data['name'], "ru")
        await loading_msg.delete()
        await message.answer(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        await loading_msg.edit_text(f"⚠️ Ошибка анализа: {e}")

@dp.message(Command("sniper"))
async def sniper_handler(message: Message):
    """Технический анализ и поиск точки входа."""
    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Введите тикер.\nПример: <code>/sniper BTC</code>", parse_mode=ParseMode.HTML)
        return
    
    ticker = args[1].upper()
    loading_msg = await message.answer(f"🦅 <b>Рассчитываю сетап по {ticker}...</b>", parse_mode=ParseMode.HTML)
    
    try:
        # Вся логика получения цены и анализа теперь внутри get_sniper_analysis
        text = await get_sniper_analysis(ticker, "ru")
        await loading_msg.delete()
        await message.answer(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        await loading_msg.edit_text(f"⚠️ Ошибка анализа: {e}")

@dp.message(Command("daily"))
async def daily_manual_handler(message: Message):
    """Ручной вызов брифинга."""
    # Если пользователь вызвал вручную, тоже подписываем его (если не был подписан)
    if message.from_user.id not in USER_SETTINGS:
         USER_SETTINGS[message.from_user.id] = 9

    loading_msg = await message.answer("☕️ <b>Готовлю свежий брифинг...</b>", parse_mode=ParseMode.HTML)
    try:
        # market_data теперь получается внутри функции, если не передан
        text = await get_daily_briefing()
        await loading_msg.delete()
        await message.answer(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        await loading_msg.edit_text(f"⚠️ Не удалось собрать данные: {e}")

# --- ЗАПУСК БОТА ---
async def main():
    # Настраиваем планировщик: запускать check_and_send_briefings каждый час в 00 минут
    scheduler.add_job(check_and_send_briefings, 'cron', minute=0)
    scheduler.start()
    
    print("🤖 Бот запущен! Планировщик активен.")
    # Запуск поллинга (прослушивания сообщений)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Bot stopped!")