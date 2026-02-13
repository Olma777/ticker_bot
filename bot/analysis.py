"""
AI analysis module with retry logic and centralized configuration.
"""

import os
import logging
from datetime import datetime, timezone
from typing import Optional

import ccxt.async_support as ccxt
from openai import AsyncOpenAI
from aiolimiter import AsyncLimiter
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, retry_if_exception

from bot.config import SECTOR_CANDIDATES, EXCHANGE_OPTIONS, RATE_LIMITS, RETRY_ATTEMPTS
from bot.prices import get_crypto_price
from bot.indicators import get_technical_indicators
from bot.cache import TieredCache
from bot.logger import logger
from bot.order_calc import validate_signal

logger = logging.getLogger(__name__)

# ===== AI ANALYST INTEGRATION =====
try:
    from bot.ai_analyst import get_ai_sniper_analysis
    AI_ANALYST_AVAILABLE = True
    logger.info("✓ AI Analyst module loaded successfully")
except ImportError as e:
    AI_ANALYST_AVAILABLE = False
    logger.warning(f"⚠ AI Analyst not available: {e}. Using legacy analysis.")

# --- RATE LIMITER ---
rate_limiter = AsyncLimiter(RATE_LIMITS.openrouter_requests, RATE_LIMITS.openrouter_period)

# --- CACHE ---
daily_cache: dict[str, str] = {}


# --- HELPER FUNCTIONS ---

def _format_price(price: float) -> str:
    """
    Адаптивное форматирование цены для Telegram.
    Критично для активов < $1 (HBAR, SHIB и т.д.)
    """
    if price is None or price == 0:
        return "$0"
    
    abs_price = abs(price)
    
    if abs_price >= 10000:
        return f"${price:,.0f}"
    elif abs_price >= 1000:
        return f"${price:,.2f}"
    elif abs_price >= 1:
        return f"${price:.2f}"
    elif abs_price >= 0.1:
        return f"${price:.3f}"
    elif abs_price >= 0.01:
        return f"${price:.4f}"
    elif abs_price >= 0.001:
        return f"${price:.5f}"
    else:
        return f"${price:.6f}"


async def fetch_ticker_multisource(
    exchanges: dict[str, ccxt.Exchange], 
    symbol: str
) -> Optional[dict]:
    """Fetch ticker from multiple exchanges with fallback."""
    for name, exchange in exchanges.items():
        try:
            ticker = await exchange.fetch_ticker(symbol)
            if not ticker or ticker['last'] is None:
                continue
            return {
                "price": ticker['last'],
                "change": ticker['percentage'],
                "vol": ticker['quoteVolume'] if ticker['quoteVolume'] else 0,
                "source": name
            }
        except Exception:
            continue
    return None


async def fetch_real_market_data() -> tuple[str, list[str]]:
    """Fetch real market data from multiple exchanges."""
    exchanges = {
        "Binance": ccxt.binance(EXCHANGE_OPTIONS["binance"]),
        "Bybit": ccxt.bybit(EXCHANGE_OPTIONS["bybit"]),
        "MEXC": ccxt.mexc(EXCHANGE_OPTIONS["mexc"]),
        "BingX": ccxt.bingx(EXCHANGE_OPTIONS["bingx"])
    }
    market_report = ""
    valid_tickers_list: list[str] = []
    
    try:
        btc_data = await fetch_ticker_multisource(exchanges, 'BTC/USDT')
        if btc_data:
            market_report += f"🛑 GLOBAL BTC: ${btc_data['price']} ({btc_data['change']}%)\n"
        
        market_report += "📊 VERIFIED MARKET DATA:\n"
        for sector, tickers in SECTOR_CANDIDATES.items():
            market_report += f"--- {sector} ---\n"
            found_any = False
            for ticker in tickers:
                data = await fetch_ticker_multisource(exchanges, ticker)
                if data:
                    vol_str = f"${int(data['vol']):,}"
                    market_report += (
                        f"ID: {ticker} | Price: {data['price']} | "
                        f"Change: {data['change']}% | Vol: {vol_str} | Src: {data['source']}\n"
                    )
                    valid_tickers_list.append(ticker)
                    found_any = True
            if not found_any:
                market_report += f"(No data for {sector})\n"
            market_report += "\n"
    except Exception as e:
        logger.error(f"Error fetching market data: {e}")
        market_report += "Error fetching data."
    finally:
        for exchange in exchanges.values():
            await exchange.close()
    
    return market_report, valid_tickers_list


def _get_openai_client() -> AsyncOpenAI:
    """Create OpenAI client for OpenRouter."""
    return AsyncOpenAI(
        api_key=os.getenv("OPENROUTER_API_KEY"),
        base_url="https://openrouter.ai/api/v1"
    )

# Custom retry filter for 429/500/502/503
def is_retryable_error(exception):
    if hasattr(exception, "status_code"):
        return exception.status_code in [429, 500, 502, 503]
    return False

@retry(
    retry=retry_if_exception_type(Exception) & retry_if_exception(is_retryable_error),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=4, max=20),
    reraise=True
)
async def _call_openai(prompt: str, temperature: float = 0.0) -> str:
    """Call OpenAI API with robust retry logic for 429s."""
    client = _get_openai_client()
    async with rate_limiter:
        completion = await client.chat.completions.create(
            model=os.getenv("MODEL_NAME", "deepseek/deepseek-chat"),
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature
        )
    return completion.choices[0].message.content or ""


# --- 1. DAILY BRIEFING ---

async def get_daily_briefing(user_input: Optional[str] = None) -> str:
    """Generate daily market briefing."""
    cache_key = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H")
    if cache_key in daily_cache:
        return daily_cache[cache_key]

    real_market_data, valid_tickers = await fetch_real_market_data()
    if not valid_tickers:
        return "⚠️ Ошибка: Не удалось получить рыночные данные. Попробуйте позже."

    prompt = f"""
    Ты — алгоритмический аналитик Market Lens. СЕГОДНЯ: {datetime.now(timezone.utc).strftime("%Y-%m-%d")}.
    
    РЫНОЧНЫЕ ДАННЫЕ:
    {real_market_data}
    
    ЗАДАЧА:
    Выбери 3-4 наиболее перспективных актива.
    
    ТРЕБОВАНИЯ К ДИЗАЙНУ:
    1. ИСПОЛЬЗУЙ ТОЛЬКО HTML ТЕГИ (`<b>`, `<i>`).
    2. ЗАПРЕЩЕНО использовать Markdown (`**`, `##`, `---`).
    3. Используй эмодзи.
    
    СТРУКТУРА ОТВЕТА (HTML):
    
    🦁 <b>Market Lens | Daily Alpha</b>
    📉 <b>BTC Context:</b> [Цена] ([Изменение]%)
    
    🤖 <b>[ТИКЕР]</b> | [Сектор]
    💰 Цена: [Цена] ([Изменение]%) | 🏦 [Биржа]
    ▪️ <b>Драйвер:</b> [Краткая причина]
    🎯 <b>План:</b> Вход (Market) | TP (+5%) | SL (-3%)
    
    (Повторить для остальных)
    
    ⚖️ <b>Disclaimer:</b> Не финансовый совет. DYOR.
    """
    
    try:
        start_ts = datetime.now(timezone.utc)
        report = await _call_openai(prompt, temperature=0.0)
        latency = (datetime.now(timezone.utc) - start_ts).total_seconds() * 1000
        # LEGACY: logging.info("Daily briefing generated")
        logger.info("llm_response", symbol="DAILY", price=None, latency_ms=int(latency), tokens_used=None)
        daily_cache.clear()
        daily_cache[cache_key] = report
        return report
    except Exception as e:
        # LEGACY: logger.error(f"Daily briefing error: {e}")
        logger.error("llm_response_error", symbol="DAILY", exc_info=True)
        return f"⚠️ Ошибка Daily: {e}"


# --- 2. AUDIT (VC STYLE) ---

async def analyze_token_fundamentals(ticker: str) -> str:
    """Perform fundamental analysis of a token."""
    price_data, _ = await get_crypto_price(ticker)
    curr_price = price_data.get('price', 'N/A') if price_data else 'N/A'
    vol = price_data.get('volume_24h', 'N/A') if price_data else 'N/A'
    
    prompt = f"""
    Ты — старший аналитик венчурного фонда (VC Researcher).
    Актив: {ticker.upper()} | Цена: ${curr_price} | Объем: {vol}
    
    ЗАДАЧА:
    Проведи фундаментальный аудит проекта.
    Ищи "Красные флаги" (риски) и "Зеленые флаги" (потенциал).
    
    ТРЕБОВАНИЯ К ФОРМАТУ:
    1. ИСПОЛЬЗУЙ ТОЛЬКО HTML (`<b>`, `<i>`). ЗАПРЕЩЕНО Markdown (`**`, `##`).
    2. Используй эмодзи для списков.
    3. Стиль: Лаконичный, жесткий, без воды.
    
    СТРУКТУРА ОТВЕТА (HTML):
    
    🛡 <b>{ticker.upper()} | Fundamental Audit</b>
    💰 Цена: ${curr_price}
    
    1️⃣ <b>Продукт и Утилити</b>
    ▪️ Суть: [Что они делают? 1 предложение]
    ▪️ Проблема: [Какую боль решают?]
    ▪️ Конкуренты: [Кто дышит в спину?]
    
    2️⃣ <b>Токеномика (On-Chain)</b>
    ▪️ Эмиссия: [Ограничена или бесконечна?]
    ▪️ Разлоки/Давление: [Есть ли риск дампа от фондов?]
    ▪️ Утилити токена: [Зачем он нужен? Газ/Говернанс?]
    
    3️⃣ <b>Риски и Угрозы (Red Flags)</b>
    🚩 [Риск 1]
    🚩 [Риск 2]
    
    4️⃣ <b>Вердикт VC</b>
    🏆 <b>Оценка: [1-10]/10</b>
    ▪️ Вывод: [Инвестировать / Наблюдать / Скам]
    
    ⚖️ <b>Market Lens Disclaimer:</b> Не финансовый совет.
    """

    try:
        start_ts = datetime.now(timezone.utc)
        resp = await _call_openai(prompt, temperature=0.1)
        latency = (datetime.now(timezone.utc) - start_ts).total_seconds() * 1000
        logger.info("llm_response", symbol=ticker, price=None, latency_ms=int(latency), tokens_used=None)
        return resp
    except Exception as e:
        logger.error("llm_response_error", symbol=ticker, exc_info=True)
        return f"⚠️ Ошибка аудита: {e}"


def _clean_telegram_html(text: str) -> str:
    """
    Удаляет все теги, не поддерживаемые Telegram HTML.
    Оставляет только: b, strong, i, em, u, ins, s, strike, del, code, pre, span
    Критическое исправление: Обрабатывает списки ДО удаления тегов.
    """
    if not text:
        return ""

    import re
    
    # 1. Сначала обрабатываем списки, пока теги живы
    # Заменяем <li> на буллет с новой строки
    text = re.sub(r'<li[^>]*>', '\n  • ', text, flags=re.IGNORECASE)
    # Удаляем закрывающие </li>, <ul>, <ol>
    text = re.sub(r'</li[^>]*>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'</?[ou]l[^>]*>', '', text, flags=re.IGNORECASE)
    
    # 2. Заменяем <br> и <p> на переносы строк
    text = re.sub(r'<br[^>]*>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</p[^>]*>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<p[^>]*>', '', text, flags=re.IGNORECASE)

    allowed_tags = {
        'b', 'strong', 'i', 'em', 'u', 'ins', 
        's', 'strike', 'del', 'code', 'pre', 'span', 'a'
    }
    
    def remove_tag(match):
        tag_full = match.group(0)
        tag_name = match.group(2).lower()
        
        # Если это ссылка <a href="...">, оставляем как есть
        if tag_name == 'a':
            return tag_full
            
        if tag_name in allowed_tags:
            return tag_full
        
        return '' # Удаляем запрещенный тег, но оставляем контент
    
    # 3. Удаляем все остальные теги, кроме разрешенных
    text = re.sub(r'<(/?)\"?([^>\\s\"]+)[^>]*>', remove_tag, text)
    
    # 4. Чистим множественные переносы строк
    lines = [line.strip() for line in text.split('\n')]
    # Фильтруем пустые строки, но оставляем одиночные разделители
    clean_text = '\n'.join([l for l in lines if l])
    
    return clean_text.strip()


async def _generate_ai_contextual_analysis(
    ticker: str,
    price: float,
    change: str,
    rsi: float,
    funding: float,
    oi: str,
    supports: list[dict],
    resistances: list[dict],
    p_score: int,
    mm_phase: str,
    mm_verdict: list[str],
    liquidity_hunts: list[str],
    spoofing_signals: list[str],
    btc_regime: str
) -> str:
    """
    ГЛУБОКИЙ СРЕДНЕСРОЧНЫЙ АНАЛИЗ МОНЕТЫ ЧЕРЕЗ OPENAI.
    """
    # 1. Форматирование уровней для промпта
    sup_formatted = []
    for l in supports[:5]:
        emoji = "🟢" if l['score'] >= 3.0 else "🟡" if l['score'] >= 1.0 else "🔴"
        strength = l.get('strength', 'N/A')
        sup_formatted.append(f"      {emoji} ${l['price']:.2f} (Score: {l['score']:.1f}, {strength})")
    
    res_formatted = []
    for l in resistances[:5]:
        emoji = "🟢" if l['score'] >= 3.0 else "🟡" if l['score'] >= 1.0 else "🔴"
        strength = l.get('strength', 'N/A')
        res_formatted.append(f"      {emoji} ${l['price']:.2f} (Score: {l['score']:.1f}, {strength})")
    
    sup_text = "\n".join(sup_formatted) if sup_formatted else "      • НЕТ АКТИВНЫХ УРОВНЕЙ"
    res_text = "\n".join(res_formatted) if res_formatted else "      • НЕТ АКТИВНЫХ УРОВНЕЙ"
    
    # 2. Форматирование MM анализа
    mm_text = "\n".join([f"      {line}" for line in mm_verdict if line.strip()]) if mm_verdict else "      • Нейтральная фаза"
    liq_text = "\n".join([f"      {line}" for line in liquidity_hunts if line.strip()]) if liquidity_hunts else "      • Нет явных зон охоты"
    spoof_text = "\n".join([f"      {line}" for line in spoofing_signals if line.strip()]) if spoofing_signals else "      • Нет признаков манипуляции"
    
    # 3. Промпт (ТОЧНО по шаблону)
    # 3. Промпт (ТОЧНО по шаблону)
    prompt = f"""
    Краткий анализ для {ticker} по данным индикатора:

    Цена: ${price:.2f}
    Фаза MM: {mm_phase}
    Funding: {funding*100:.3f}%
    OI: {oi}
    
    ПОДДЕРЖКА:
    {sup_text}
    
    СОПРОТИВЛЕНИЕ:
    {res_text}

    Дай 4 коротких пункта в формате:
    1. КЛЮЧЕВЫЕ УРОВНИ: (2 уровня)
    2. ФАЗА РЫНКА: (1 предложение)
    3. ДЕЙСТВИЯ MM: (1 предложение по funding/OI и ликвидности)
    4. КОНТЕКСТ СИГНАЛА: Объясни, насколько математический сигнал {direction} с входом {entry} согласуется с текущей фазой рынка. НЕ давай свои цены входа/SL/TP - используй только предоставленные данные.

    ТОЛЬКО HTML, БЕЗ Markdown. Кратко, по делу.

    ВАЖНОЕ ТРЕБОВАНИЕ ПО ФОРМАТИРОВАНИЮ:
    - ЗАПРЕЩЕНО использовать теги <ol>, <ul>, <li>, <h1>, <h2>, <div>, <p>, <br>
    - РАЗРЕШЕНЫ только: <b>, <i>, <code>, <pre>
    - Для списков используй простые цифры с точкой (1. Текст) и перенос строки
    - НЕ ИСПОЛЬЗУЙ никакие другие HTML теги
    - НЕ ИСПОЛЬЗУЙ Markdown (**)
    """

    try:
        completion = await _call_openai(prompt, temperature=0.3)
        if not completion:
            logger.error("AI Analysis returned empty response")
            return ""
            
        cleaned = _clean_telegram_html(completion)
        return cleaned
        
    except Exception as e:
        logger.error(f"AI contextual analysis failed: {str(e)}", exc_info=True)
        # Re-raise to let caller handle fallback
        raise e


# --- 3. SNIPER ---


# ===== AI ANALYST - FORCED MODE =====
try:
    from bot.ai_analyst import get_ai_sniper_analysis
    AI_ANALYST_AVAILABLE = True
    logger.info("✅ AI Analyst FORCED MODE - ENABLED")
except ImportError as e:
    AI_ANALYST_AVAILABLE = False
    logger.error(f"❌ AI Analyst MISSING - BOT WILL FAIL: {e}")

async def get_sniper_analysis(ticker: str, language: str = "ru") -> dict:
    """FORCED AI ANALYST - NO FALLBACK - Returns Dict"""
    
    if not AI_ANALYST_AVAILABLE:
        return {
            "status": "ERROR", 
            "reason": "AI Analyst module is missing",
            "symbol": ticker
        }
    
    try:
        # LEGACY: logger.info(f"🎯 AI Analyst processing: {ticker}")
        start_ts = datetime.now(timezone.utc)
        signal = await get_ai_sniper_analysis(ticker)
        latency = (datetime.now(timezone.utc) - start_ts).total_seconds() * 1000
        logger.info("llm_response", symbol=ticker, price=None, latency_ms=int(latency), tokens_used=None)
        
        return signal
            
    except Exception as e:
        logger.error("llm_response_error", symbol=ticker, exc_info=True)
        return {
            "status": "ERROR",
            "reason": str(e),
            "symbol": ticker
        }

async def _generate_legacy_analysis(ticker: str, strat: dict, indicators: dict) -> str:
    """Generate analysis using legacy OpenAI prompt (backup)"""
    curr_price = indicators['price']
    change = indicators['change']
    p_score = strat['score']
    
    # Calculate calc_time just in case it's missing
    calc_time = datetime.now(timezone.utc).strftime("%H:%M UTC")

    def fmt(val: float) -> str:
        return f"${val:.4f}" if isinstance(val, (int, float)) and val > 0 else "N/A"
    
    entry_str = fmt(strat['entry'])
    stop_str = fmt(strat['stop'])
    tp1_str = fmt(strat['tp1'])
    tp2_str = fmt(strat['tp2'])
    tp3_str = fmt(strat['tp3'])
    
    # Position size formatting
    pos_size_val = strat['position_size']
    if pos_size_val > 0:
        pos_size_str = f"{pos_size_val:.0f}" if curr_price < 1.0 else f"{pos_size_val:.4f}"
    else:
        pos_size_str = "0"

    # Risk info block
    risk_info = ""
    if strat['action'] != "WAIT":
        risk_info = (
            f"🛡 <b>RISK MANAGEMENT (Cap $1000, Risk 1%):</b>\n"
            f"• <b>Stop Loss:</b> {strat['risk_pct']:.2f}% дистанция.\n"
            f"• <b>Position Size:</b> {pos_size_str} монет (${strat['risk_amount']} риска).\n"
            f"• <b>RRR:</b> 1:{strat['rrr']:.1f}"
        )

    # Determine trend direction
    try:
        vwap_val = float(indicators['vwap'].replace('$', ''))
        trend_dir = 'выше' if curr_price > vwap_val else 'ниже'
    except (ValueError, AttributeError):
        trend_dir = 'около'

    prompt = f"""
    Ты — Профессиональный Интрадей Трейдер (M30 Sniper).
    Твоя задача — проанализировать данные и выдать четкий торговый план.
    
    ВАЖНО: ИСПОЛЬЗУЙ ТОЛЬКО ПОДДЕРЖИВАЕМЫЕ HTML ТЕГИ: <b>, <code>, <i>.
    ЗАМЕНЯЙ СИМВОЛЫ "БОЛЬШЕ/МЕНЬШЕ" НА СЛОВА "выше/ниже".
    
    МЕТАДАННЫЕ:
    • Время расчета: {calc_time}
    
    ВХОДНЫЕ ДАННЫЕ:
    • Цена: ${curr_price} ({change}%)
    • VWAP (24h): {indicators['vwap']}
    • RSI (M30): {indicators['rsi']}
    • ATR: {indicators['atr_val']}
    • Regime: {indicators['btc_regime']}
    
    SENTIMENT:
    • Funding: {indicators['funding']} ({sentiment})
    • OI: {indicators['open_interest']}
    • Volatility Bands (ATR): {indicators['vol_low']} — {indicators['vol_high']}
    
    УРОВНИ (С ЦВЕТОВОЙ ИНДИКАЦИЕЙ):
    • RESISTANCE: {indicators['resistance']}
    • SUPPORT: {indicators['support']}
    (🟢=Сильный, 🟡=Средний, 🔴=Слабый)
    
    STRATEGY SCORE DECOMPOSITION ({p_score}%):
    {indicators['p_score_details']}
    
    ТОРГОВЫЙ ПЛАН (РАССЧИТАН АЛГОРИТМОМ):
    • Action: {strat['action']}
    • Reason: {strat['reason']}
    • Entry: {entry_str} | Stop: {stop_str}
    • TPs: {tp1_str} | {tp2_str} | {tp3_str}

    СТРУКТУРА ОТВЕТА (HTML):

    📊 <b>{ticker.upper()} | M30 SNIPER</b>
    🕒 <b>Расчет:</b> {calc_time}
    💰 Цена: <code>${curr_price}</code> ({change}%)

    📡 <b>MARKET CONTEXT:</b>
    • <b>RSI:</b> {indicators['rsi']}. <b>Regime:</b> {indicators['btc_regime']}.
    • <b>Sentiment:</b> Funding {indicators['funding']} | OI {indicators['open_interest']}.
    • <b>Volatility:</b> ATR {indicators['atr_val']}. Bands: {indicators['vol_low']} — {indicators['vol_high']}.

    🎯 <b>ЗОНЫ (M30):</b>
    • <b>RES:</b> {indicators['resistance']}
    • <b>SUP:</b> {indicators['support']}

    1️⃣ <b>СТРУКТУРА & ЛОГИКА</b>
    • <b>Тренд:</b> Цена {trend_dir} VWAP.
    • <b>Strategy Score:</b> <b>{p_score}%</b>.
    • <b>Декомпозиция:</b>
      [Скопируй сюда пункты из STRATEGY SCORE DECOMPOSITION].
    • <b>Анализ:</b> [Объясни Score. Если уровни 🔴 или 🟡 — укажи на слабость структуры. Если 🟢 — подтверди силу].

    2️⃣ <b>СНАЙПЕРСКИЙ ПЛАН</b>
    🚦 <b>Тип:</b> {strat['action']}
    🚪 <b>Вход:</b> <code>{entry_str}</code>
    🛡 <b>Стоп-лосс:</b> 🔴 <code>{stop_str}</code>
    ✅ <b>Тейк-профиты:</b>
       🟢 TP1: <code>{tp1_str}</code> (Safe)
       🟢 TP2: <code>{tp2_str}</code> (Level)
       🟢 TP3: <code>{tp3_str}</code> (Runner)

    {risk_info}

    <b>ОБОСНОВАНИЕ:</b>
    {strat['reason']}

    ⚠️ <b>УСЛОВИЯ ВХОДА:</b>
    • Вход строго лимитным ордером.
    • Жди закрытия свечи M30 для подтверждения.
    """

    try:
        return await _call_openai(prompt, temperature=0.0)
    except Exception as e:
        logger.error(f"Sniper AI Error: {e}")
        return f"⚠️ Ошибка анализа: {e}"


# --- 4. MARKET SCAN ---

async def get_market_scan() -> str:
    """Scan market for hidden accumulation signals."""
    real_market_data, valid_tickers = await fetch_real_market_data()
    if not valid_tickers:
        return "⚠️ Ошибка: Не удалось получить данные с бирж."
    
    prompt = f"""
    Ты — алгоритмический скринер Market Lens (Liquidity Hunter).
    ДАТА: {datetime.now(timezone.utc).strftime("%Y-%m-%d")}.
    
    ПОЛНЫЙ СПИСОК РЫНКА (ДАННЫЕ):
    {real_market_data}
    
    ЗАДАЧА:
    Проанализируй данные (Цену, Изменение, Объем) и найди ТОП-5 монет, где происходит "Скрытая Аккумуляция" или подготовка к движению.
    Критерии: Аномальный объем при малом изменении цены, удержание важных уровней, расхождение с BTC.
    
    ФОРМАТ ОТВЕТА (СТРОГО HTML, Clean UI):
    1. ИСПОЛЬЗУЙ ТОЛЬКО HTML ТЕГИ (`<b>`, `<i>`).
    2. ЗАПРЕЩЕНО Markdown.
    3. Стиль: Профессиональный скринер.

    СТРУКТУРА ОТВЕТА:

    🔭 <b>Market Lens | Hidden Accumulation Scan</b>
    📅 Дата: {datetime.now(timezone.utc).strftime("%d.%m.%Y")} | 🏦 Market: Global

    📊 <b>Топ-5 Лидеров (Heatmap):</b>
    1. <b>[TICKER]</b> — [Причина одним словом, например: "Рост объема"] (P-Score: [XX]%)
    2. <b>[TICKER]</b> — ...
    (до 5)
    
    ---
    
    (ДЕТАЛЬНЫЙ РАЗБОР ДЛЯ КАЖДОЙ ИЗ 5 МОНЕТ):
    
    🤖 <b>1. [TICKER] | [Сектор]</b>
    💰 Цена: [Цена] ([Изменение]%) | Vol: [Объем]
    ▪️ <b>Сигнал:</b> [Почему это скрытая аккумуляция? Опиши паттерн]
    📉 <b>Техника:</b> [Тренд / Уровни]
    ⚠️ <b>Риски:</b> [Чего опасаться]
    
    (Повторить для остальных)
    
    ---
    
    💡 <b>Действия трейдера:</b>
    
    1️⃣ <b>Хотите точный вход?</b>
    Используйте снайпер-модуль для расчета лимиток:
    👉 Скопируйте: <code>/sniper [TICKER]</code>
    
    2️⃣ <b>Сомневаетесь в проекте?</b>
    Закажите глубокий VC-аудит (разлоки, риски):
    👉 Скопируйте: <code>/audit [TICKER]</code>
    
    ⚖️ <b>Disclaimer:</b> Сгенерировано AI. DYOR.
    """

    try:
        return await _call_openai(prompt, temperature=0.1)
    except Exception as e:
        logger.error(f"Scan Error: {e}")
        return f"⚠️ Ошибка сканера: {e}"


# --- COMPATIBILITY LAYER ---

async def get_crypto_analysis(ticker: str, name: str, language: str = "ru") -> str:
    """Legacy function - redirects to analyze_token_fundamentals."""
    return await analyze_token_fundamentals(ticker)

# Tiered Cache: Fundamental
_fund_cache = TieredCache()

async def _original_fetch_logic(symbol: str) -> str:
    sym = symbol.upper().replace("USDT", "").replace("USD", "")
    return await analyze_token_fundamentals(sym)

async def get_fundamental(symbol: str) -> str:
    return await _fund_cache.get_or_set(
        f"fundamental:{symbol}",
        lambda: _original_fetch_logic(symbol),
        "fundamental"
    )


def format_signal_html(signal: dict) -> str:
    """Форматирование торгового сигнала с полным MM и AI анализом."""
    
    required = ["symbol", "side", "entry", "sl", "tp1", "tp2", "tp3", "rrr", "p_score"]
    for field in required:
        if field not in signal:
            raise ValueError(f"Missing field: {field}")
    
    # ----- AI CONTEXTUAL ANALYSIS -----
    ai_analysis = signal.get("ai_analysis", "")
    ai_section = ""
    if ai_analysis:
        ai_section = f"""
─────────────────────────
🤖 <b>DEEP AI CONTEXT</b>
{ai_analysis}
"""
    
    side_emoji = "🟢 LONG" if signal['side'] == 'long' else '🔴 SHORT' if signal['side'] == 'short' else '⚪ WAIT'
    
    stop_dist = abs(signal["entry"] - signal["sl"])
    rrr_tp1 = abs(signal["tp1"] - signal["entry"]) / stop_dist if stop_dist > 0 else 0
    rrr_tp2 = abs(signal["tp2"] - signal["entry"]) / stop_dist if stop_dist > 0 else 0
    rrr_tp3 = abs(signal["tp3"] - signal["entry"]) / stop_dist if stop_dist > 0 else 0
    
    # ----- FILTERED MM VERDICT (без дублей) -----
    mm_phase = signal.get("mm_phase", "⚪ NEUTRAL")
    mm_verdict = signal.get("mm_verdict", [])
    filtered_verdict = []
    for line in mm_verdict:
        line_stripped = line.strip()
        if (not line_stripped.startswith("• <b>Phase:</b>") and 
            not line_stripped.startswith("Phase:") and
            "Accumulation signals:" not in line_stripped and
            "Distribution signals:" not in line_stripped):
            filtered_verdict.append(line)
    
    mm_text = "\n".join(filtered_verdict) if filtered_verdict else "• Нет дополнительных сигналов"
    
    # ----- DEDUPLICATED LIQUIDITY -----
    liquidity_all = signal.get("liquidity_hunts", [])
    unique_liquidity = []
    seen_patterns = set()
    
    for line in liquidity_all:
        if ":" in line:
            pattern = line.split(":")[0]
        else:
            pattern = line[:20]  # Первые 20 символов
            
        if pattern not in seen_patterns:
            unique_liquidity.append(line)
            seen_patterns.add(pattern)
            
    liquidity_text = "\n".join(unique_liquidity) if unique_liquidity else "• Нет явных зон охоты"
    
    # ----- SPOOFING -----
    spoofing = signal.get("spoofing_signals", [])
    spoofing_text = "\n".join(spoofing) if spoofing else "• Нет признаков манипуляции"
    
    # ----- LEVELS (ПОКАЗЫВАЕМ ВСЕ, С ИКОНКАМИ) -----
    strong_supports = signal.get("strong_supports", "НЕТ")
    strong_resists = signal.get("strong_resists", "НЕТ")
    
    # ----- LOGIC -----
    logic_setup = signal.get("logic_setup", "No logic")
    logic_summary = signal.get("logic_summary", "No summary")
    
    # ----- RRR CALCULATION -----
    # Already calc above
    
    # P0 FIX: Display REAL PRICE, not entry
    display_price = signal.get('current_price', signal['entry'])
    
    final_text = f"""
💎 <b>{signal['symbol']}</b> | M30 SNIPER
💰 ${display_price:,.2f} ({signal.get('change', 0):+.2f}%)
─────────────────────────
🎯 P-Score: {signal['p_score']}/100
🛡️ Kevlar: {'ПРОЙДЕН ✅' if signal.get('kevlar_passed') else 'БЛОКИРОВАН ❌'}

{side_emoji}
Вход:     <code>{_format_price(signal['entry'])}</code>
Стоп:     🔴 <code>{_format_price(signal['sl'])}</code>
TP1:      🟢 <code>{_format_price(signal['tp1'])}</code> ({rrr_tp1:.2f}x)
TP2:      🟢 <code>{_format_price(signal['tp2'])}</code> ({rrr_tp2:.2f}x)
TP3:      🟢 <code>{_format_price(signal['tp3'])}</code> ({rrr_tp3:.2f}x)
RRR (TP2): {signal['rrr']:.2f}

─────────────────────────
🧠 <b>SMART MONEY ФАЗА</b>
{mm_phase}
{mm_text}

🩸 <b>ЛИКВИДНОСТЬ И СТОП-ОХОТА</b>
{liquidity_text}

🎭 <b>МАНИПУЛЯЦИИ / СПУФИНГ</b>
{spoofing_text}

📊 <b>КЛЮЧЕВЫЕ УРОВНИ</b>
🟢 Поддержка: {strong_supports}
🔴 Сопротивление: {strong_resists}
{ai_section}
⚙️ <b>ЛОГИКА СДЕЛКИ</b>
• {logic_setup}
• {logic_summary}
• RSI: {signal.get('rsi', 'N/A')}

─────────────────────────
⚠️ Риск 1% | Лимитный ордер
🕒 {datetime.now(timezone.utc).strftime('%H:%M UTC')}
"""
    return _clean_telegram_html(final_text)
