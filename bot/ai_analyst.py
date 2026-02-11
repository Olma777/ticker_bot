"""
AI Analyst Module - Minimal version for testing
"""

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

async def get_ai_sniper_analysis(ticker: str) -> str:
    """
    Minimal AI analyst for testing.
    Returns formatted message in your template style.
    """
    try:
        # Get legacy indicators (temporary)
        from bot.indicators import get_technical_indicators
        
        indicators = await get_technical_indicators(ticker)
        if not indicators:
            return f"⚠️ No data for {ticker}"
        
        # Extract key data
        price = indicators.get('price', 0)
        change = indicators.get('change', '0%')
        rsi = indicators.get('rsi', 50)
        support = indicators.get('support', 'N/A')
        resistance = indicators.get('resistance', 'N/A')
        p_score = indicators.get('p_score', 0)
        
        # Simple market phase logic
        if p_score >= 50 and rsi > 50:
            phase = "БЫЧЬЯ ФАЗА / НАКОПЛЕНИЕ"
            direction = "ЛОНГ"
            entry = f"${price * 0.995:.2f}"
        elif p_score >= 50 and rsi < 50:
            phase = "МЕДВЕЖЬЯ ФАЗА / РАСПРЕДЕЛЕНИЕ"
            direction = "ШОРТ"
            entry = f"${price * 1.005:.2f}"
        else:
            phase = "КОНСОЛИДАЦИЯ / НЕОПРЕДЕЛЕННОСТЬ"
            direction = "WAIT"
            entry = "N/A"
        
        # Format output in your template
        return f"""
📊 <b>{ticker} | AI SNIPER ANALYSIS</b>
🕒 <b>Время:</b> {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}

🎯 <b>1. КЛЮЧЕВЫЕ УРОВНИ:</b>
• <b>Поддержка:</b> {support}
• <b>Сопротивление:</b> {resistance}

📈 <b>2. ТЕКУЩАЯ ФАЗА:</b>
• <b>Фаза:</b> {phase}
• <b>Цена:</b> ${price} ({change})
• <b>RSI:</b> {rsi}
• <b>Strategy Score:</b> {p_score}%

💰 <b>3. АНАЛИЗ НАСТРОЕНИЯ:</b>
• <b>Вердикт:</b> {'Перекупленность' if rsi > 70 else 'Перепроданность' if rsi < 30 else 'Нейтрально'}

🎯 <b>4. ТОРГОВЫЙ СИГНАЛ:</b>
• <b>Направление:</b> {direction}
• <b>Точка входа:</b> {entry}
• <b>Тейк-профиты:</b> TP1: N/A | TP2: N/A | TP3: N/A
• <b>Stop Loss:</b> N/A

⚠️ <b>УСЛОВИЯ:</b>
• Это тестовый AI-анализ (модуль в разработке)
• Реальный анализ будет использовать ваш полный шаблон
"""
        
    except Exception as e:
        logger.error(f"AI Analyst error: {e}")
        return f"⚠️ AI Analysis Error: {str(e)[:150]}"