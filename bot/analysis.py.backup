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
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from bot.config import SECTOR_CANDIDATES, EXCHANGE_OPTIONS, RATE_LIMITS, RETRY_ATTEMPTS
from bot.prices import get_crypto_price
from bot.indicators import get_technical_indicators

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


@retry(
    stop=stop_after_attempt(RETRY_ATTEMPTS),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True
)
async def _call_openai(prompt: str, temperature: float = 0.0) -> str:
    """Call OpenAI API with retry logic."""
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
        report = await _call_openai(prompt, temperature=0.0)
        daily_cache.clear()
        daily_cache[cache_key] = report
        return report
    except Exception as e:
        logger.error(f"Daily briefing error: {e}")
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
        return await _call_openai(prompt, temperature=0.1)
    except Exception as e:
        logger.error(f"Audit error: {e}")
        return f"⚠️ Ошибка аудита: {e}"


# --- 3. SNIPER ---

async def get_sniper_analysis(ticker: str, language: str = "ru") -> str:
    """
    Generate professional analysis using AI Analyst.
    Falls back to legacy analysis if AI fails.
    """
    # PRIORITY 1: Use AI Analyst (your professional template)
    if AI_ANALYST_AVAILABLE:
        try:
            logger.info(f"🎯 Using AI Analyst for {ticker}")
            analysis = await get_ai_sniper_analysis(ticker)
            
            # Basic validation of AI output
            if analysis and len(analysis) > 50 and "⚠️" not in analysis[:100]:
                return analysis
            else:
                logger.warning(f"AI analysis failed quality check for {ticker}")
                # Fall through to legacy
        except Exception as e:
            logger.error(f"❌ AI Analyst failed for {ticker}: {e}")
            # Fall through to legacy
    
    # PRIORITY 2: Legacy analysis (backup - KEEP EXISTING CODE)
    logger.info(f"🔄 Using legacy analysis for {ticker}")

    price_data, error = await get_crypto_price(ticker)
    if not price_data:
        return f"⚠️ Не удалось найти {ticker}."

    indicators = await get_technical_indicators(ticker)
    if not indicators:
        return f"⚠️ Ошибка получения индикаторов для {ticker}."

    curr_price = indicators['price']
    change = indicators['change']
    calc_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    
    p_score = indicators['p_score']
    strat = indicators['strategy']
    
    # Determine sentiment
    try:
        f_val = float(indicators['funding'].strip('%').replace('+', ''))
        sentiment = "Бычье" if f_val > 0.01 else "Медвежье" if f_val < -0.01 else "Нейтральное"
    except (ValueError, AttributeError):
        sentiment = "N/A"

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