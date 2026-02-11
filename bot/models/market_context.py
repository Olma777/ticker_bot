from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Optional


@dataclass(frozen=True)
class MarketContext:
    symbol: str
    price: float
    btc_regime: Literal["bullish", "bearish", "neutral"]
    atr: float
    vwap: Optional[float] = None
    funding_rate: Optional[float] = None
    timestamp: datetime = datetime.now()

    @property
    def volatility_regime(self) -> str:
        return "high" if self.atr / self.price > 0.03 else "low"
