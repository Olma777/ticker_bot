"""
Centralized configuration for Market Lens Bot.
All settings, constants, and shared configurations in one place.
Updated for P1-FIX (Strict Order Calc).
"""

import os
import sys
from pathlib import Path
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

# --- PATHS ---
BOT_DIR = Path(__file__).parent
DATA_DIR = BOT_DIR / "data"
DB_PATH = DATA_DIR / "users.db"


# --- TRADING SETTINGS (SYNCED WITH PINE v3.7) ---
@dataclass(frozen=True)
class TradingSettings:
    """Trading parameters synced with Pine Script v3.7."""
    timeframe: str = "30m"
    react_bars: int = 24
    k_react: float = 1.3
    merge_atr: float = 0.6
    wt: float = 1.0          # Weight for touches
    wa: float = 0.35         # Weight for age decay
    t_min: int = 5
    sc_min: float = -100.0
    max_dist_pct: float = 30.0
    atr_len: int = 14
    zone_width_mult: float = 0.5
    z_win: int = 180
    z_thr: float = 1.25
    default_capital: float = 1000.0
    default_risk_pct: float = 1.0
    p_score_threshold: int = 35
    funding_threshold: float = 0.0003
    
    # --- P1-FIX-OrderCalc (Strict Formulas) ---
    sl_buffer_atr: float = 0.25
    tp1_atr: float = 0.75
    tp2_atr: float = 1.25
    tp3_atr: float = 2.00
    min_rrr: float = 1.10


TRADING = TradingSettings()


# --- RATE LIMITS ---
@dataclass(frozen=True)
class RateLimitSettings:
    """API rate limiting configuration."""
    openrouter_requests: int = 8
    openrouter_period: int = 60  # seconds


RATE_LIMITS = RateLimitSettings()


# --- RETRY SETTINGS ---
RETRY_ATTEMPTS = 3
RETRY_WAIT_SECONDS = 2


# --- EXCHANGE CONFIGURATION ---
EXCHANGE_OPTIONS = {
    "binance": {"options": {"defaultType": "future"}, "enableRateLimit": True},
    "bybit": {"options": {"defaultType": "linear"}, "enableRateLimit": True},
    "okx": {"options": {"defaultType": "swap"}, "enableRateLimit": True},
    "mexc": {"options": {"defaultType": "swap"}, "enableRateLimit": True},
    "bingx": {"options": {"defaultType": "swap"}, "enableRateLimit": True},
    "gateio": {"options": {"defaultType": "future"}, "enableRateLimit": True},
}

EXCHANGE_PRIORITY = ["binance", "bybit", "okx", "mexc", "bingx", "gateio"]


# --- SECTOR TICKERS ---
SECTOR_CANDIDATES = {
    "AI": ["FET/USDT", "RENDER/USDT", "WLD/USDT", "ARKM/USDT", "GRT/USDT", "NEAR/USDT"],
    "RWA": ["ONDO/USDT", "PENDLE/USDT", "OM/USDT", "TRU/USDT", "DUSK/USDT"],
    "L2": ["OP/USDT", "ARB/USDT", "POL/USDT", "METIS/USDT", "MANTA/USDT", "STRK/USDT"],
    "DePIN": ["FIL/USDT", "AR/USDT", "IOTX/USDT", "THETA/USDT", "HBAR/USDT"],
}


# --- COIN NAMES ---
COIN_NAMES = {
    "BTC": "Bitcoin", "ETH": "Ethereum", "USDT": "Tether", "BNB": "BNB",
    "SOL": "Solana", "XRP": "XRP", "USDC": "USDC", "ADA": "Cardano",
    "AVAX": "Avalanche", "DOGE": "Dogecoin", "TON": "Toncoin",
    "PEPE": "Pepe", "SHIB": "Shiba Inu", "SUI": "Sui", "ARB": "Arbitrum",
    "APT": "Aptos", "LDO": "Lido DAO", "OP": "Optimism", "TIA": "Celestia",
}


class Config:
    """Runtime configuration with environment variables."""
    
    # --- INFRASTRUCTURE ---
    WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
    DATABASE_URL = DATA_DIR / "market_lens.db"

    # --- STRATEGY CONSTANTS (STRICTLY SYNCED WITH PINE v3.7) ---
    REACT_BARS = 24
    ATR_LEN = 14
    K_REACT = 1.3
    MERGE_ATR = 0.6
    WT_TOUCH = 1.0
    WA_DECAY = 0.35
    TMIN = 5
    ZONE_WIDTH_MULT = 0.5
    MAX_DIST_PCT = 30.0
    P_SCORE_THRESHOLD = 35
    FUNDING_THRESHOLD = 0.0003
    
    # --- P1-FIX-OrderCalc Defaults ---
    DEFAULT_CAPITAL = 1000.0
    DEFAULT_RISK_PCT = 1.0
    MIN_RRR = TRADING.min_rrr

    # --- KEVLAR FILTERS ---
    KEVLAR_MOMENTUM_ATR_MULT = 1.5      # K1
    KEVLAR_MISSED_ENTRY_ATR_MULT = 1.0  # K2
    KEVLAR_RSI_LOW = 20                 # K3
    KEVLAR_RSI_HIGH = 80                # K3
    KEVLAR_STRONG_PSCORE = 50           # K3

    @classmethod
    def validate(cls):
        """Security check. Called via Server Lifespan."""
        if not cls.WEBHOOK_SECRET or cls.WEBHOOK_SECRET == "change_me_in_prod":
            print("CRITICAL: WEBHOOK_SECRET is missing or default. Exiting.")
            sys.exit(1)
        if not cls.TELEGRAM_TOKEN or not cls.TELEGRAM_CHAT_ID:
            print("WARNING: Telegram credentials missing. Alerts will not be sent.")
