"""
P-Score Engine - СИНХРОНИЗИРОВАНО с Pine v3.7
Быстрая оценка вероятности для Decision Engine
"""

from bot.config import Config
from bot.decision_models import MarketContext, SentimentContext, PScoreResult

def calculate_score(
    event: dict,
    market: MarketContext,
    sentiment: SentimentContext
) -> PScoreResult:
    """
    Расчет P-Score (0-100)
    УПРОЩЕННАЯ версия для мгновенных решений
    """
    score = 50
    breakdown = ["База: 50"]
    
    # 1. Сила уровня (из Pine Script)
    sc = float(event.get('score', 0))
    
    # GHOST LEVEL - мгновенная блокировка
    if sc < -10:
        return PScoreResult(0, ["GHOST LEVEL: принудительный WAIT"])
    
    # STRONG LEVEL (SC >= 1.0) = +15
    if sc >= 1.0:
        score += 15
        breakdown.append(f"Уровень STRONG 🟢 ({sc:.1f}): +15")
    # WEAK LEVEL (SC < 0) = -20
    elif sc < 0.0:
        score -= 20
        breakdown.append(f"Уровень WEAK 🔴 ({sc:.1f}): -20")
    else:
        breakdown.append(f"Уровень MEDIUM 🟡 ({sc:.1f}): 0")
    
    # 2. Режим BTC
    if market.regime == "EXPANSION":
        score += 10
        breakdown.append("Режим EXPANSION: +10")
    elif market.regime == "COMPRESSION":
        score -= 10
        breakdown.append("Режим COMPRESSION: -10")
    else:
        breakdown.append("Режим NEUTRAL: 0")
    
    # 3. Контекст RSI (только контртренд)
    event_type = event.get('event', '')
    is_support = "SUPPORT" in event_type
    
    if is_support and market.rsi < 35:
        score += 5
        breakdown.append(f"RSI Oversold ({market.rsi:.1f}): +5")
    elif not is_support and market.rsi > 65:
        score += 5
        breakdown.append(f"RSI Overbought ({market.rsi:.1f}): +5")
    
    # 4. HOT sentiment (высокий OI)
    if sentiment.is_hot:
        score += 10
        breakdown.append("Sentiment HOT: +10")
    else:
        score -= 5
        breakdown.append("Sentiment COLD: -5")
    
    # Клиппинг 0-100
    score = max(0, min(100, int(score)))
    
    return PScoreResult(score, breakdown)