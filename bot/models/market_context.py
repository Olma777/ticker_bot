from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Optional, List


@dataclass(frozen=True)
class Candle:
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class MarketContext:
    symbol: str
    price: float
    btc_regime: Literal["bullish", "bearish", "neutral"]
    atr: float
    vwap: Optional[float] = None
    funding_rate: Optional[float] = None
    rsi: Optional[float] = None
    data_quality: Optional[str] = "OK"
    candle_open: Optional[float] = None
    candle_high: Optional[float] = None
    candle_low: Optional[float] = None
    candle_close: Optional[float] = None
    candles: List[Candle] = field(default_factory=list)
    timestamp: datetime = datetime.now()

    @property
    def volatility_regime(self) -> str:
        return "high" if self.atr / self.price > 0.03 else "low"
