"""
Market Lens Telegram Bot - Main Entry Point
"""

import asyncio
# import logging  # Removed to avoid conflict with structlog
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
import structlog  # Added import

from bot.db import init_db as init_user_db
from bot.database import init_db as init_events_db

# ... (rest of imports)

async def main() -> None:
    """Main entry point with single-instance lock."""
    
    # === SINGLE INSTANCE LOCK (Env Var + File) ===
    # Railway/Cloud specific check
    if os.getenv("BOT_INSTANCE_LOCK") == "locked":
         print("❌ Another instance is already running (Env Lock). Exiting.")
         sys.exit(1)
         
    # File Lock (Local dev)
    lock_file = "/tmp/marketlens-bot.lock"
    try:
        fd = os.open(lock_file, os.O_CREAT | os.O_RDWR)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (IOError, BlockingIOError):
        print("❌ Another instance is already running (File Lock). Exiting.")
        sys.exit(1)
    # ==============================

    # configure_logging(json_logs=True)  # Already configured globally
    logger.info("bot_started", version="v3.7.1-HOTFIX")
    
    # Initialize databases
    await init_user_db()
    await init_events_db() # Fix: Initialize events table
from bot.prices import get_crypto_price, get_market_summary
from bot.analysis import get_crypto_analysis, get_sniper_analysis, get_daily_briefing, get_market_scan, format_signal_html
from bot.validators import SymbolNormalizer, InvalidSymbolError
from bot.prices import PriceUnavailableError
from bot.logger import configure_logging  # Removed logger import to avoid circular dep or re-init
from bot.utils import batch_process

# --- CONFIGURATION ---
from bot.config import Config

# --- CONFIGURATION ---
# load_dotenv() # Loaded in Config
TOKEN = Config.TELEGRAM_TOKEN
CHANNEL_ID = Config.TELEGRAM_CHAT_ID

if not TOKEN:
    print("❌ ОШИБКА: Токен бота не найден! Убедитесь, что TELEGRAM_TOKEN (или BOT_TOKEN) есть в .env")
    sys.exit(1)

# --- LOGGING ---
configure_logging(json_logs=True)
logger = structlog.get_logger()

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
    users_to_send = await get_all_users_for_hour(current_hour)
    
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
                await delete_user_setting(user_id)
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
    
    if await get_user_setting(user_id) is None:
        await set_user_setting(user_id, 9)
    
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
        await delete_user_setting(user_id)
        await callback.message.edit_text(
            "🔕 <b>Рассылка отключена.</b>\n"
            "Я больше не буду беспокоить вас по утрам.\n"
            "Включить снова: /settings",
            parse_mode=ParseMode.HTML
        )
    else:
        hour = int(action)
        await set_user_setting(user_id, hour)
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
    symbol_raw = args[1]
    try:
        norm = SymbolNormalizer.normalize(symbol_raw)
        ticker = norm['base']
    except InvalidSymbolError as e:
        await message.answer(f"❌ Invalid symbol: {e}")
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
    except PriceUnavailableError as e:
        await message.answer(f"⚠️ Price unavailable: {e}")


@dp.message(Command("sniper"))
async def cmd_sniper(message: Message) -> None:
    """Sniper analysis (Smart Money)."""
    args_list = message.text.split() if message.text else []
    args = args_list[1] if len(args_list) > 1 else None

    if not args:
        await message.answer("⚠️ Используйте: /sniper [TICKER]\nПример: <code>/sniper LTC</code>", parse_mode=ParseMode.HTML)
        return
    
    try:
        norm = SymbolNormalizer.normalize(args)
        ticker = norm['base']
    except InvalidSymbolError as e:
        await message.answer(f"❌ Invalid symbol: {e}")
        return
    loading_msg = await message.answer(f"🔭 Снайпер-модуль сканирует {ticker}...")
    
    try:
        signal = await get_sniper_analysis(ticker, "ru")
        await loading_msg.delete()
        
        # 1. Validation Logic (Safety Net)
        if signal.get("status") != "OK":
            reason = signal.get("reason", "Unknown")
            status = signal.get("status", "ERROR")
            
            # If blocked by Kevlar or Logic, show FRIENDLY message
            if status == "BLOCKED":
                kevlar_passed = signal.get("kevlar_passed", True)
                p_score = signal.get("p_score", 0)
                
                # Friendly mapping of reasons
                friendly_reason = reason
                advice = "Рынок в неопределенности. Рекомендуем проверить актив через 30-60 минут."
                
                if "Low Score" in reason:
                    friendly_reason = f"Низкий P-Score ({p_score}/100). Недостаточно аргументов для входа."
                elif "No levels" in reason:
                    friendly_reason = "Цена находится в 'воздухе' между уровнями. Ждем теста поддержки или сопротивления."
                elif "Kevlar" in reason:
                    friendly_reason = "Сработала защита Kevlar (фильтр опасных движений)."
                    advice = "Высокая волатильность или риск 'падающего ножа'. Оставайтесь в стороне."
                elif "No valid setup" in reason:
                    friendly_reason = f"Нет четкой структуры. P-Score: {p_score}/100."
                
                text = (
                    f"⏳ <b>СИГНАЛ В ОЖИДАНИИ</b> | {ticker}\n"
                    f"─────────────────\n"
                    f"🛑 <b>Причина:</b> {friendly_reason}\n"
                    f"🛡 <b>Kevlar:</b> {'ПРОЙДЕН ✅' if kevlar_passed else 'БЛОКИРОВАН ❌'}\n\n"
                    f"💡 <b>Совет:</b> {advice}"
                )
            else:
                text = f"⚠️ Ошибка данных для {ticker}\nПроверьте биржу или тикер.\nДетали: {reason}"
                
            await message.answer(text, parse_mode=ParseMode.HTML)
            return

        if signal.get("type") != "TRADE":
             await message.answer(f"⛔ Нет торгового сигнала: {signal.get('reason', 'Wait')}")
             return
             
        # 2. Field Integrity Check
        required_fields = ["entry", "sl", "tp1", "tp2", "tp3", "rrr"]
        # Allow 0 for some fields if logic permits, but None is bad. Order calc ensures floats.
        missing = [f for f in required_fields if f not in signal or signal[f] is None]
        
        if missing:
             await message.answer(f"⚠️ Ошибка расчета ордера. Отсутствуют поля: {', '.join(missing)}")
             return
            
        # 3. SUCCESS - Format Trade
        try:
            report = format_signal_html(signal)
            await message.answer(report, parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.error(f"HTML Parse Error: {e}")
            await message.answer(f"⚠️ Ошибка форматирования сигнала: {e}")
        
    except Exception as e:
        logger.error(f"Error in cmd_sniper: {e}", exc_info=True)
        await message.answer(f"⚠️ Критическая ошибка бота: {e}")
    except PriceUnavailableError as e:
        await message.answer(f"⚠️ Price unavailable: {e}")


@dp.message(Command("daily"))
async def daily_manual_handler(message: Message) -> None:
    """Manual daily briefing request."""
    # Reduced list to avoid rate limits/timeouts
    symbols = ["BTC", "ETH", "SOL", "XRP", "DOGE"]
    loading = await message.answer("☕️ Параллельно собираю дайджест по рынку (лимит: 5)...")
    try:
        # get_sniper_analysis expects ticker without USDT usually, or normalized?
        # get_sniper_analysis calls get_ai_sniper_analysis which calls get_technical_indicators
        # which calls get_market_context which handles symbol/USDT normalization.
        # But here we pass "BTC", "ETH" etc.
        # So s.replace("USDT", "") is correct if input is "BTCUSDT".
        # But my list is ["BTC", ...]
        # Wait, the TARGET content has ["BTCUSDT"...]
        # I am changing it to ["BTC"...]
        results = await batch_process(
            symbols,
            lambda s: get_sniper_analysis(s, "ru"),
            concurrency=3
        )
        await loading.delete()
        response = ["📊 <b>Market Digest</b>\n"]
        
        for symbol, result in zip(symbols, results):
            if isinstance(result, Exception):
                response.append(f"{symbol}: ⚠️ Error")
                continue
            
            # Helper safely handles dict or str (if legacy)
            if isinstance(result, dict):
                status = result.get("status", "OK")
                if status == "BLOCKED":
                    reason = result.get("reason", "Blocked")
                    response.append(f"{symbol}: 🛑 {reason}")
                elif status == "ERROR":
                     response.append(f"{symbol}: ⚠️ Error")
                elif status == "OK" and result.get("type") == "TRADE":
                     price = result.get("entry", 0)
                     side = "L" if result.get("side") == "long" else "S"
                     response.append(f"{symbol}: ✅ {side} @ {price:.2f}")
                else:
                     response.append(f"{symbol}: ⚪️ Neutral")
            else:
                 response.append(f"{symbol}: ❓ {str(result)[:20]}...")

        try:
            report = format_signal_html(signal)
            await message.answer(report, parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.error(f"HTML formatting failed: {e}")
            # Fallback: Send basic text if HTML fails
            fallback_report = (
                f"💎 {signal['symbol']} | M30 SNIPER\n"
                f"🎯 P-Score: {signal.get('p_score', 'N/A')}\n"
                f"⚠️ Full analysis unavailable (HTML Error).\n"
                f"Entry: {signal.get('entry', 'N/A')}"
            )
            await message.answer(fallback_report)
    except Exception as e:
        await message.answer(f"⚠️ Ошибка: {e}")


@dp.message(Command("scan"))
async def cmd_scan(message: Message) -> None:
    """Market scanner - hidden accumulation search."""
    args_list = message.text.split() if message.text else []
    if len(args_list) > 1:
        symbol_raw = args_list[1]
        try:
            SymbolNormalizer.normalize(symbol_raw)
        except InvalidSymbolError as e:
            await message.answer(f"❌ Invalid symbol: {e}")
            return
    loading = await message.answer("🔭 Сканирую рынок на предмет скрытой аккумуляции...")
    try:
        report = await get_market_scan()
        await loading.delete()
        await message.answer(report, parse_mode="HTML")
    except Exception as e:
        await message.answer(f"⚠️ Ошибка: {e}")
    except PriceUnavailableError as e:
        await message.answer(f"⚠️ Price unavailable: {e}")


@dp.message(Command("test_post"))
async def cmd_test_post(message: Message) -> None:
    """Test command for channel auto-posting."""
    await message.reply("⏳ Запускаю тестовую отправку в канал...", parse_mode=ParseMode.HTML)
    await broadcast_daily_briefing()
    await message.reply("🏁 Тест завершен. Проверьте канал и логи.", parse_mode=ParseMode.HTML)


# --- MAIN ---

import fcntl
import os 
import sys
import aiosqlite  # Added for DB lock
from datetime import datetime, timedelta, timezone

async def acquire_instance_lock():
    """
    SQLite-based distributed lock for Railway.
    Ensures only one instance runs at a time using a shared DB file.
    """
    lock_db = Config.DATA_DIR / "instance.lock"
    Config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    async with aiosqlite.connect(lock_db) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS instance_lock (
                id INTEGER PRIMARY KEY,
                pid INTEGER,
                started_at TIMESTAMP,
                expires_at TIMESTAMP
            )
        """)
        
        # Check if an active instance exists (Valid/Alive if expires_at > now)
        # We use UTC for consistency
        now_utc = datetime.now(timezone.utc)
        cutoff = now_utc
        
        cursor = await db.execute(
            "SELECT pid FROM instance_lock WHERE expires_at > ?",
            (cutoff,)
        )
        existing = await cursor.fetchone()
        
        if existing:
            # Check if process is actually alive (Local/Same Container check)
            # In a new container, this PID check might be irrelevant for the OLD container,
            # but the DB lock timestamp is the real guard across containers.
            # If the DB lock is fresh, we back off.
            existing_pid = existing[0]
            try:
                # If we are on the same machine, strict check
                if existing_pid != os.getpid():
                     os.kill(existing_pid, 0)
                     print(f"❌ Instance {existing_pid} is alive and holding lock. Exiting.")
                     sys.exit(1)
            except ProcessLookupError:
                # Process is dead locally, but DB says alive?
                # On shared volume, this means another container is holding it.
                # On ephemeral, the file shouldn't exist unless checking failure.
                pass
            
            # If we get here, and DB lock is valid, we assume conflict in Orchestrator
            print(f"❌ Active lock found in DB (expires in future). Another instance likely running.")
            sys.exit(1)

        # Acquire Lock
        # Clear old locks
        await db.execute("DELETE FROM instance_lock")
        
        # Insert new lock (TTL 60s)
        expires = now_utc + timedelta(seconds=60)
        await db.execute(
            "INSERT INTO instance_lock (pid, started_at, expires_at) VALUES (?, ?, ?)",
            (os.getpid(), now_utc, expires)
        )
        await db.commit()
        print(f"🔒 Instance locked (PID: {os.getpid()})")

async def lock_heartbeat():
    """Updates the lock TTL every 30 seconds."""
    lock_db = Config.DATA_DIR / "instance.lock"
    while True:
        try:
            await asyncio.sleep(30)
            now_utc = datetime.now(timezone.utc)
            new_expires = now_utc + timedelta(seconds=60)
            
            async with aiosqlite.connect(lock_db) as db:
                await db.execute(
                    "UPDATE instance_lock SET expires_at = ? WHERE pid = ?",
                    (new_expires, os.getpid())
                )
                await db.commit()
        except Exception as e:
            print(f"⚠️ Lock heartbeat failed: {e}")
            # Don't exit, just retry next tick

async def main() -> None:
    """Main entry point with single-instance lock."""
    
    # === DISTRIBUTED INSTANCE LOCK (SQLite) ===
    # Prevents Railway double-instance issues during redeploy
    await acquire_instance_lock()
    # Start heartbeat task
    asyncio.create_task(lock_heartbeat())
    # ==========================================

    logger.info("bot_started", version="v3.7.1-HOTFIX-2")
    # Initialize database
    await init_user_db()
    await init_events_db()
    
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
