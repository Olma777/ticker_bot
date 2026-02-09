"""
Centralized configuration for Market Lens Bot.
All settings, constants, and shared configurations in one place.
"""

from dataclasses import dataclass
from pathlib import Path

# --- PATHS ---
BOT_DIR = Path(__file__).parent
DATA_DIR = BOT_DIR / "data"
DB_PATH = DATA_DIR / "users.db"

# --- TRADING SETTINGS ---
@dataclass(frozen=True)
class TradingSettings:
    """Default trading parameters (can be overridden per-user in future)."""
    timeframe: str = '30m'
    react_bars: int = 24
    k_react: float = 1.0
    merge_atr: float = 0.6
    wt: float = 1.0          # Weight for touches
    wa: float = 0.15         # Weight for age decay
    t_min: int = 5
    sc_min: float = -100.0
    max_dist_pct: float = 50.0
    atr_len: int = 14
    z_win: int = 180
    z_thr: float = 1.25
    default_capital: float = 1000.0
    default_risk_pct: float = 1.0


TRADING = TradingSettings()

# --- RATE LIMITS ---
@dataclass(frozen=True)
class RateLimitSettings:
    """API rate limiting configuration."""
    openrouter_requests: int = 8
    openrouter_period: int = 60  # seconds


RATE_LIMITS = RateLimitSettings()

# --- EXCHANGE CONFIGURATION ---
EXCHANGE_OPTIONS = {
    "binance": {'options': {'defaultType': 'future'}, 'enableRateLimit': True},
    "bybit": {'options': {'defaultType': 'linear'}, 'enableRateLimit': True},
    "okx": {'options': {'defaultType': 'swap'}, 'enableRateLimit': True},
    "mexc": {'options': {'defaultType': 'swap'}, 'enableRateLimit': True},
    "bingx": {'options': {'defaultType': 'swap'}, 'enableRateLimit': True},
    "gateio": {'options': {'defaultType': 'future'}, 'enableRateLimit': True},
}

# Priority order for price fetching
EXCHANGE_PRIORITY = ["binance", "bybit", "okx", "mexc", "bingx", "gateio"]

# --- SECTOR TICKERS ---
SECTOR_CANDIDATES = {
    "AI": ["FET/USDT", "RENDER/USDT", "WLD/USDT", "ARKM/USDT", "GRT/USDT", "NEAR/USDT"],
    "RWA": ["ONDO/USDT", "PENDLE/USDT", "OM/USDT", "TRU/USDT", "DUSK/USDT"],
    "L2": ["OP/USDT", "ARB/USDT", "POL/USDT", "METIS/USDT", "MANTA/USDT", "STRK/USDT"],
    "DePIN": ["FIL/USDT", "AR/USDT", "IOTX/USDT", "THETA/USDT", "HBAR/USDT"]
}

# --- COIN NAMES ---
COIN_NAMES = {
    "BTC": "Bitcoin", "ETH": "Ethereum", "USDT": "Tether", "BNB": "BNB",
    "SOL": "Solana", "XRP": "XRP", "USDC": "USDC", "ADA": "Cardano",
    "AVAX": "Avalanche", "DOGE": "Dogecoin", "TON": "Toncoin",
    "PEPE": "Pepe", "SHIB": "Shiba Inu", "SUI": "Sui", "ARB": "Arbitrum",
    "APT": "Aptos", "LDO": "Lido DAO", "OP": "Optimism", "TIA": "Celestia"
}

# --- RETRY SETTINGS ---
RETRY_ATTEMPTS = 3
RETRY_WAIT_SECONDS = 2
