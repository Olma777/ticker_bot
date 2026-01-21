# --- 3. DAILY BRIEFING (УТРЕННЯЯ ГАЗЕТА) ---
async def get_daily_briefing(market_data):
    date_str = datetime.now().strftime("%d.%m.%Y")
    cache_key = f"daily_briefing_{date_str}"
    
    if cache_key in ANALYSIS_CACHE:
        timestamp, cached_text = ANALYSIS_CACHE[cache_key]
        if time.time() - timestamp < DAILY_CACHE_TTL:
            return cached_text

    system_prompt = f"""
    # РОЛЬ
    Ты — ведущий аналитик хедж-фонда. Твоя задача — дать четкий торговый план на утро.
    
    # ВХОДНЫЕ ДАННЫЕ
    1. Дата: {date_str}
    2. BTC Dom: {market_data.get('btc_dominance')}%
    3. Рынок: {market_data.get('top_coins')}
    
    # ЗАДАЧА (Watchlist)
    Из списка лидеров роста выбери 3 монеты. Для каждой придумай логичный SMC-сценарий (Smart Money Concepts).
    
    ВАЖНО: Не просто пиши "что случилось", а пиши "ЧТО ДЕЛАТЬ".
    Для каждой монеты укажи:
    - Направление (LONG/SHORT)
    - Конкретный план (где ждать вход).

    # ФОРМАТ ВЫВОДА (HTML)

    🌅 <b>Market Pulse: {date_str}</b>

    📊 <b>Макро:</b> {{BULLISH / NEUTRAL}} (BTC Dom {market_data.get('btc_dominance')}%)
    {{Одно предложение вывода по рынку}}.

    🔥 <b>Сектор дня:</b> #{{SECTOR}}
    Лидеры: {{COIN1}}, {{COIN2}}.

    💎 <b>Watchlist (Торговые идеи):</b>

    1. <b>#{{TICKER}}</b> {{📈 LONG / 📉 SHORT}}
       └ <i>Сетап:</i> {{Что сделал ММ? Например: "Сняли ликвидность снизу и вернулись в диапазон"}}
       └ <i>План:</i> {{Инструкция. Например: "Лимитный ордер от ретеста ${{PRICE}}. Цель ${{TARGET}}"}}

    2. <b>#{{TICKER}}</b> {{📈 LONG / 📉 SHORT}}
       └ <i>Сетап:</i> {{Например: "Формирование Order Block на 4H"}}
       └ <i>План:</i> {{Инструкция. Например: "Вход на пробое ${{PRICE}}. Стоп короткий"}}

    3. <b>#{{TICKER}}</b> {{📈 LONG / 📉 SHORT}}
       └ <i>Сетап:</i> {{Например: "Поджим к уровню сопротивления"}}
       └ <i>План:</i> {{Инструкция}}

    🛠 <b>Инструменты:</b>
    👇 Жми для детального расчета:
    /sniper {{TICKER1}} — Точная точка входа
    /audit {{TICKER1}} — Фундаментал
    """

    try:
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "You are a pro crypto trader. Output format: Telegram HTML."},
                {"role": "user", "content": system_prompt}
            ],
            temperature=0.3,
            extra_headers={"HTTP-Referer": "https://telegram.org", "X-Title": "CryptoBot"}
        )
        result = clean_html(response.choices[0].message.content)
        ANALYSIS_CACHE[cache_key] = (time.time(), result)
        return result

    except Exception as e:
        return f"⚠️ Error generating briefing: {str(e)}"