import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# --- PATHS (for db.py compatibility) ---
BOT_DIR = Path(__file__).parent
DATA_DIR = BOT_DIR / "data"
DB_PATH = DATA_DIR / "users.db"


class Config:
    # --- INFRASTRUCTURE ---
    WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
    DATABASE_URL = "market_lens.db"

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

    @classmethod
    def validate(cls):
        """Security check. Called via Server Lifespan."""
        if not cls.WEBHOOK_SECRET or cls.WEBHOOK_SECRET == "change_me_in_prod":
            print("CRITICAL: WEBHOOK_SECRET is missing or default. Exiting.")
            sys.exit(1)
        if not cls.TELEGRAM_TOKEN or not cls.TELEGRAM_CHAT_ID:
            print("WARNING: Telegram credentials missing. Alerts will not be sent.")
