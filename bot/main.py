"""
Market Lens Telegram Bot - Main Entry Point
"""

import asyncio
import logging
import sys
import os
import re
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.enums import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot.db import init_db, get_user_setting, set_user_setting, delete_user_setting, get_all_users_for_hour
from bot.prices import get_crypto_price, get_market_summary
from bot.analysis import get_crypto_analysis, get_sniper_analysis, get_daily_briefing, get_market_scan

# --- CONFIGURATION ---
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

if not TOKEN:
    print("❌ ОШИБКА: Токен бота не найден! Убедитесь, что BOT_TOKEN есть в .env")
    sys.exit(1)

# --- LOGGING ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- BOT INITIALIZATION ---
bot = Bot(token=TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()


# --- HELPER FUNCTIONS ---

def validate_ticker(ticker: str) -> tuple[bool, str]:
    """Validate ticker to protect against injection and incorrect input."""
    if not ticker or len(ticker) < 2:
        return False, "❌ Тикер слишком короткий. Минимум 2 символа."
    
    if len(ticker) > 10:
        return False, "❌ Тикер слишком длинный. Максимум 10 символов."
    
    if not re.match(r'^[A-Z0-9]+$', ticker):
        return False, "❌ Неверный формат тикера. Используйте только заглавные буквы и цифры."
    
    return True, ""


def get_time_keyboard() -> InlineKeyboardMarkup:
    """Create keyboard for briefing time selection."""
    hours = [7, 8, 9, 10, 11, 12]
    row = [InlineKeyboardButton(text=f"{h:02d}:00", callback_data=f"set_time_{h}") for h in hours]
    buttons = [row, [InlineKeyboardButton(text="🔕 Отключить рассылку", callback_data="set_time_off")]]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# --- SCHEDULED TASKS ---

async def check_and_send_briefings() -> None:
    """Run every hour. Check who needs briefing and send it."""
    current_hour = datetime.now(timezone.utc).hour
    users_to_send = get_all_users_for_hour(current_hour)
    
    if not users_to_send:
        return

    logger.info(f"⏰ {current_hour}:00. Sending briefing to {len(users_to_send)} users.")

    try:
        briefing_text = await get_daily_briefing()
        
        for user_id in users_to_send:
            try:
                await bot.send_message(user_id, briefing_text, parse_mode=ParseMode.HTML)
            except Exception as e:
                logger.error(f"Failed to send to user {user_id}: {e}")
                delete_user_setting(user_id)
    except Exception as e:
        logger.error(f"⚠️ Briefing error: {e}")


async def broadcast_daily_briefing() -> None:
    """Auto-post briefing to public channel."""
    logger.info(f"🚀 Starting broadcast. Channel ID: {CHANNEL_ID}")
    
    if not CHANNEL_ID:
        logger.error("❌ CHANNEL_ID not found!")
        return

    try:
        briefing_text = await get_daily_briefing()
        await bot.send_message(chat_id=CHANNEL_ID, text=briefing_text, parse_mode=ParseMode.HTML)
        logger.info(f"✅ Message sent to channel {CHANNEL_ID}")
    except Exception as e:
        logger.error(f"❌ Broadcast error: {e}")


# --- COMMAND HANDLERS ---

@dp.message(Command("start"))
async def cmd_start(message: Message) -> None:
    """Welcome and onboarding."""
    user_id = message.from_user.id if message.from_user else 0
    
    if get_user_setting(user_id) is None:
        set_user_setting(user_id, 9)
    
    text = (
        "🕶 <b>Market Lens | AI Signals</b>\n\n"
        "Добро пожаловать в закрытую аналитическую систему Market Lens.\n\n"
        "Мы не даем советов. Мы предоставляем информационное преимущество.\n\n"
        "Система в реальном времени сканирует рынок, вычисляя математические уровни "
        "поддержки/сопротивления и интерпретируя действия маркетмейкеров через гибридную AI-модель.\n\n"
        "<b>Доступные команды:</b>\n\n"
        "• /sniper [TICKER] — Полный технический и психологический разбор актива. Цели, уровни, зоны ликвидности.\n"
        "• /scan — Топ-5 монет со скрытой аккумуляцией (Скринер).\n"
        "• /daily — Секторальный обзор: AI, RWA, DePIN, L2. Где сейчас сосредоточен капитал.\n"
        "• /audit [TICKER] — VC-стиль аудит проекта: токеномика, команда, риски.\n\n"
        "<b>Настройки:</b>\n"
        "/settings — Управление уведомлениями и персонализация.\n\n"
        "📧 <b>Контакты:</b> hello@mlens.ai"
    )
    await message.answer(text, parse_mode=ParseMode.HTML)


@dp.message(Command("settings"))
async def cmd_settings(message: Message) -> None:
    """Briefing time settings menu."""
    current_utc_time = datetime.now(timezone.utc).strftime("%H:%M")

    await message.answer(
        f"🕒 <b>Настройка времени брифинга</b>\n\n"
        f"Сейчас на сервере: <b>{current_utc_time} (UTC)</b>.\n\n"
        f"⚠️ <b>Важно:</b> Бот работает по времени UTC (Гринвич).\n"
        f"Чтобы получать брифинг в <b>09:00</b> по вашему времени, посмотрите разницу с сервером.\n\n"
        f"<i>Пример: Если у вас сейчас 12:00, а на сервере 09:00 (разница 3 часа), "
        f"ставьте таймер на 06:00, чтобы получить его в 9 утра.</i>\n\n"
        f"Введите желаемое время (в формате UTC) через двоеточие, например: <code>06:00</code>",
        reply_markup=get_time_keyboard(),
        parse_mode=ParseMode.HTML
    )


@dp.callback_query(F.data.startswith("set_time_"))
async def callback_time(callback: CallbackQuery) -> None:
    """Handle time button presses."""
    if not callback.data or not callback.message:
        return
    
    action = callback.data.split("_")[2]
    user_id = callback.from_user.id if callback.from_user else 0
    
    if action == "off":
        delete_user_setting(user_id)
        await callback.message.edit_text(
            "🔕 <b>Рассылка отключена.</b>\n"
            "Я больше не буду беспокоить вас по утрам.\n"
            "Включить снова: /settings",
            parse_mode=ParseMode.HTML
        )
    else:
        hour = int(action)
        set_user_setting(user_id, hour)
        await callback.message.edit_text(
            f"✅ <b>Время установлено!</b>\n"
            f"Я буду готовить для вас отчет каждый день ровно в <b>{hour:02d}:00</b>.",
            parse_mode=ParseMode.HTML
        )
    
    await callback.answer()


@dp.message(Command("audit"))
async def audit_handler(message: Message) -> None:
    """Fundamental analysis of a coin."""
    args = message.text.split() if message.text else []
    if len(args) < 2:
        await message.answer("⚠️ Введите тикер.\nПример: <code>/audit SOL</code>", parse_mode=ParseMode.HTML)
        return
    
    ticker = args[1].upper().strip()
    
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
        
        text = await get_crypto_analysis(ticker, price_data.get('name', ticker), "ru")
        await loading_msg.delete()
        await message.answer(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Error in audit_handler: {e}")
        error_text = f"⚠️ <b>Ошибка анализа:</b>\n{str(e)[:200]}"
        
        try:
            await loading_msg.edit_text(error_text, parse_mode=ParseMode.HTML)
        except Exception:
            await message.answer(error_text, parse_mode=ParseMode.HTML)


@dp.message(Command("sniper"))
async def cmd_sniper(message: Message) -> None:
    """Sniper analysis (Smart Money)."""
    args_list = message.text.split() if message.text else []
    args = args_list[1] if len(args_list) > 1 else None

    if not args:
        await message.answer("⚠️ Используйте: /sniper [TICKER]\nПример: /sniper LTC")
        return
    
    loading_msg = await message.answer(f"🔭 Снайпер-модуль сканирует {args.upper()}...")
    
    try:
        report = await get_sniper_analysis(args.upper(), "ru")
        await loading_msg.delete()
        
        try:
            await message.answer(report, parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.error(f"HTML Parse Error: {e}")
            clean_report = report.replace("<b>", "").replace("</b>", "").replace("<code>", "").replace("</code>", "")
            await message.answer(f"⚠️ Ошибка форматирования (Raw Text):\n\n{clean_report}")
        
    except Exception as e:
        logger.error(f"Error in cmd_sniper: {e}", exc_info=True)
        await message.answer(f"⚠️ Ошибка: {e}")


@dp.message(Command("daily"))
async def daily_manual_handler(message: Message) -> None:
    """Manual daily briefing request."""
    loading = await message.answer("☕️ Сканирую сектора рынка...")
    try:
        report = await get_daily_briefing()
        await loading.delete()
        await message.answer(report, parse_mode="HTML")
    except Exception as e:
        await message.answer(f"⚠️ Ошибка: {e}")


@dp.message(Command("scan"))
async def cmd_scan(message: Message) -> None:
    """Market scanner - hidden accumulation search."""
    loading = await message.answer("🔭 Сканирую рынок на предмет скрытой аккумуляции...")
    try:
        report = await get_market_scan()
        await loading.delete()
        await message.answer(report, parse_mode="HTML")
    except Exception as e:
        await message.answer(f"⚠️ Ошибка: {e}")


@dp.message(Command("test_post"))
async def cmd_test_post(message: Message) -> None:
    """Test command for channel auto-posting."""
    await message.reply("⏳ Запускаю тестовую отправку в канал...", parse_mode=ParseMode.HTML)
    await broadcast_daily_briefing()
    await message.reply("🏁 Тест завершен. Проверьте канал и логи.", parse_mode=ParseMode.HTML)


# --- MAIN ---

async def main() -> None:
    """Main entry point."""
    # Initialize database
    init_db()
    
    # Setup scheduler
    scheduler.add_job(check_and_send_briefings, 'cron', minute=0)
    scheduler.add_job(broadcast_daily_briefing, 'cron', hour=7, minute=0)
    scheduler.start()
    logger.info("📅 Scheduler started (07:00 UTC)")
    
    # Set bot commands
    await bot.set_my_commands([
        types.BotCommand(command="start", description="🦁 Главное меню"),
        types.BotCommand(command="scan", description="🔭 Скринер (Скрытая аккумуляция)"),
        types.BotCommand(command="sniper", description="🎯 Точка входа (Smart Money)"),
        types.BotCommand(command="daily", description="☀️ Ежедневный брифинг"),
        types.BotCommand(command="audit", description="🛡 VC-Аудит токена"),
        types.BotCommand(command="help", description="ℹ️ Помощь и Инструкция")
    ])
    logger.info("📋 Bot commands updated")
    
    print("🤖 Бот запущен! Планировщик активен.")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Bot stopped!")