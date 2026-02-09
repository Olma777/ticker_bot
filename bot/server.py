import logging
import json
import hashlib
import hmac
import html
import requests
from contextlib import asynccontextmanager
from fastapi import FastAPI, Header, HTTPException, BackgroundTasks
from pydantic import BaseModel, field_validator
from typing import Literal

from bot.config import Config
from bot.database import init_db, save_event

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MarketLens-Webhook")

# --- LIFECYCLE ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Validate Config (Fail-fast)
    Config.validate()
    
    # 2. Init DB
    init_db()
    
    logger.info("Server started successfully.")
    yield
    logger.info("Server shutting down.")

app = FastAPI(lifespan=lifespan)

# --- WEBHOOK CONTRACT ---
class TvPayload(BaseModel):
    event: Literal["SUPPORT_TEST", "RESISTANCE_TEST"]
    tv_symbol: str
    symbol: str
    tf: str
    bar_time: int  # Open Time in Seconds (Unix)
    close: float
    level: float
    atr: float
    zone_half: float
    score: float
    touches: int
    regime: str

    @field_validator('bar_time')
    def validate_time(cls, v):
        # Sanity check: Must be > Year 2020
        if v < 1_577_836_800:
            raise ValueError("bar_time must be Unix Timestamp in SECONDS (post-2020)")
        return v

# --- TELEGRAM SENDER (Sync) ---
def send_telegram_alert_sync(payload_dict: dict):
    if not Config.TELEGRAM_TOKEN or not Config.TELEGRAM_CHAT_ID:
        return

    try:
        # Secure HTML Escaping
        safe_event = html.escape(payload_dict['event'])
        safe_symbol = html.escape(payload_dict['symbol'])
        
        message = (
            f"🎯 <b>TV EVENT: {safe_event}</b>\n"
            f"Symbol: <code>{safe_symbol}</code>\n"
            f"Level: {payload_dict['level']}\n"
            f"Score: {payload_dict['score']}"
        )
        
        url = f"https://api.telegram.org/bot{Config.TELEGRAM_TOKEN}/sendMessage"
        data = {
            "chat_id": Config.TELEGRAM_CHAT_ID, 
            "text": message, 
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        
        # Short timeout (3s) to avoid hanging workers
        resp = requests.post(url, json=data, timeout=3.0)
        if resp.status_code != 200:
            logger.error(f"TG Error {resp.status_code}: {resp.text}")
            
    except Exception as e:
        logger.error(f"TG Network Error: {e}")

# --- UTILS ---
def generate_event_id(p: TvPayload) -> str:
    """
    Deterministic ID.
    Rounds floats to 8 decimals to prevent float drift.
    """
    norm_level = f"{p.level:.8f}"
    norm_zone = f"{p.zone_half:.8f}"
    
    # Structure: SYMBOL|TF|TIME|EVENT|LEVEL|ZONE
    raw_str = f"{p.tv_symbol}|{p.tf}|{p.bar_time}|{p.event}|{norm_level}|{norm_zone}"
    return hashlib.sha256(raw_str.encode()).hexdigest()

# --- ENDPOINT ---
@app.post("/tv/webhook")
async def webhook_listener(
    payload: TvPayload, 
    background_tasks: BackgroundTasks,
    x_ml_secret: str = Header(None, alias="X-ML-SECRET")
):
    # 1. Security (Constant time compare)
    if not x_ml_secret or not hmac.compare_digest(x_ml_secret, Config.WEBHOOK_SECRET):
        logger.warning("Auth failed")
        raise HTTPException(status_code=401, detail="Invalid Secret")

    # 2. Dedup ID Generation
    event_id = generate_event_id(payload)
    
    # 3. Persistence
    data = payload.model_dump()
    data['event_id'] = event_id
    
    is_new = save_event(
        event_id=event_id,
        bar_time=payload.bar_time,
        symbol=payload.symbol,
        event_type=payload.event,
        payload_json=json.dumps(data)
    )

    if not is_new:
        return {"status": "ignored_duplicate", "id": event_id}

    # 4. Notify
    background_tasks.add_task(send_telegram_alert_sync, data)

    return {"status": "received", "id": event_id}
