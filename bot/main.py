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
from bot.analysis import get_crypto_analysis, get_sniper_analysis, get_daily_briefing, get_market_scan

# 1. НАСТРОЙКИ
# Загрузка переменных окружения
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

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
USER_SETTINGS = {}

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def validate_ticker(ticker: str) -> tuple[bool, str]:
    """Валидация тикера для защиты от injection и некорректных входных данных."""
    import re
    
    if not ticker or len(ticker) < 2:
        return False, "❌ Тикер слишком короткий. Минимум 2 символа."
    
    if len(ticker) > 10:
        return False, "❌ Тикер слишком длинный. Максимум 10 символов."
    
    # Только буквы и цифры
    if not re.match(r'^[A-Z0-9]+$', ticker):
        return False, "❌ Неверный формат тикера. Используйте только заглавные буквы и цифры."
    
    return True, ""

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
        briefing_text = await get_daily_briefing()
        
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

# 2. ФУНКЦИЯ РАССЫЛКИ (С ЛОГАМИ)
async def broadcast_daily_briefing():
    """
    Авто-постинг брифинга в публичный канал.
    """
    logging.info(f"🚀 Начинаю рассылку. Channel ID: {CHANNEL_ID}")
    
    if not CHANNEL_ID:
        logging.error("❌ CHANNEL_ID не найден в переменных окружения!")
        return

    try:
        # Получаем текст (внутри функции уже есть логика получения данных)
        briefing_text = await get_daily_briefing()
        
        # Отправляем в канал
        await bot.send_message(chat_id=CHANNEL_ID, text=briefing_text, parse_mode=ParseMode.HTML)
        logging.info(f"✅ УСПЕХ: Сообщение отправлено в канал {CHANNEL_ID}")
    except Exception as e:
        logging.error(f"❌ ОШИБКА рассылки: {e}")

# --- ОБРАБОТЧИКИ КОМАНД (HANDLERS) ---

@dp.message(Command("start"))
async def cmd_start(message: Message):
    """Приветствие и онбординг."""
    # Автоматически подписываем на 09:00, если пользователя нет в базе
    if message.from_user.id not in USER_SETTINGS:
        USER_SETTINGS[message.from_user.id] = 9
        
    text = (
        "🕶 <b>Market Lens | AI Signals</b>\n\n"
        "Добро пожаловать в закрытую аналитическую систему Market Lens.\n\n"
        "Мы не даем советов. Мы предоставляем информационное преимущество.\n\n"
        "Система в реальном времени сканирует рынок, вычисляя математические уровни поддержки/сопротивления и интерпретируя действия маркетмейкеров через гибридную AI-модель.\n\n"
        "<b>Доступные команды:</b>\n\n"
        "• /sniper [TICKER] — Полный технический и психологический разбор актива. Цели, уровни, зоны ликвидности.\n"
        "• /daily — Секторальный обзор: AI, RWA, DePIN, L2. Где сейчас сосредоточен капитал.\n"
        "• /audit [TICKER] — VC-стиль аудит проекта: токеномика, команда, риски.\n\n"
        "<b>Настройки:</b>\n"
        "/settings — Управление уведомлениями и персонализация.\n\n"
        "📧 <b>Контакты:</b> hello@mlens.ai"
    )
    await message.answer(text, parse_mode=ParseMode.HTML)

@dp.message(Command("settings"))
async def cmd_settings(message: Message):
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
            "Включить снова: /settings", 
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
    
    ticker = args[1].upper().strip()
    
    # Валидация тикера
    is_valid, error_msg = validate_ticker(ticker)
    if not is_valid:
        await message.answer(error_msg, parse_mode=ParseMode.HTML)
        return
    
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
        logging.error(f"Error in audit_handler: {e}")
        error_text = f"⚠️ <b>Ошибка анализа:</b>\n{str(e)[:200]}" # Обрезаем, если ошибка длинная
        
        try:
            # 1. Пробуем отредактировать сообщение "Загрузка..."
            await loading_msg.edit_text(error_text, parse_mode=ParseMode.HTML)
        except Exception:
            # 2. Если сообщение удалено или устарело — отправляем НОВОЕ
            await message.answer(error_text, parse_mode=ParseMode.HTML)

@dp.message(Command("sniper"))
async def cmd_sniper(message: Message):
    """Снайпер-анализ (Smart Money)."""
    # Эмуляция message.get_args()
    args_list = message.text.split()
    args = args_list[1] if len(args_list) > 1 else None

    if not args:
        await message.answer("⚠️ Используйте: /sniper [TICKER]\nПример: /sniper LTC")
        return
    
    # Отправляем сообщение о начале работы
    loading_msg = await message.answer(f"🔭 Снайпер-модуль сканирует {args.upper()}...")
    
    try:
        # Вызываем функцию (теперь она возвращает HTML)
        report = await get_sniper_analysis(args.upper(), "ru")
        
        # Удаляем сообщение о загрузке
        await loading_msg.delete()
        
        # Отправляем отчет в HTML
        await message.answer(report, parse_mode=ParseMode.HTML)
        
    except Exception as e:
        logging.error(f"Error in cmd_sniper: {e}", exc_info=True)
        await message.answer(f"⚠️ Ошибка: {e}")

@dp.message(Command("daily"))
async def daily_manual_handler(message: Message):
    """Ручной запрос дневного обзора."""
    loading = await message.answer("☕️ Сканирую сектора рынка...")
    try:
        report = await get_daily_briefing()
        await loading.delete()
        # ВАЖНО: HTML режим включен
        await message.answer(report, parse_mode="HTML")
    except Exception as e:
        await message.answer(f"⚠️ Ошибка: {e}")

@dp.message(Command("scan"))
async def cmd_scan(message: Message):
    """Скринер рынка - поиск скрытой аккумуляции."""
    loading = await message.answer("🔭 Сканирую рынок на предмет скрытой аккумуляции...")
    try:
        report = await get_market_scan()
        await loading.delete()
        await message.answer(report, parse_mode="HTML")
    except Exception as e:
        await message.answer(f"⚠️ Ошибка: {e}")


# 3. ХЕНДЛЕР ДЛЯ ТЕСТА (ОБЯЗАТЕЛЬНО)
@dp.message(Command("test_post"))
async def cmd_test_post(message: Message):
    """Тестовая команда для проверки авто-постинга в канал."""
    await message.reply("⏳ Запускаю тестовую отправку в канал...", parse_mode=ParseMode.HTML)
    await broadcast_daily_briefing()
    await message.reply("🏁 Тест завершен. Проверьте канал и логи.", parse_mode=ParseMode.HTML)

# --- ЗАПУСК БОТА ---
async def main():
    # Настраиваем планировщик:
    
    # 1. Рассылка пользователям (каждый час)
    scheduler.add_job(check_and_send_briefings, 'cron', minute=0)
    
    # 2. Авто-постинг в канал (07:00 UTC)
    scheduler.add_job(broadcast_daily_briefing, 'cron', hour=7, minute=0)
    
    scheduler.start()
    logging.info("📅 Планировщик запущен (07:00 UTC)")
    
    print("🤖 Бот запущен! Планировщик активен.")
    # Запуск поллинга (прослушивания сообщений)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Bot stopped!")