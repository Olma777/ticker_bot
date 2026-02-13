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
from bot.decision_engine import make_decision
from bot.notifier import send_decision_card

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
    
    # Note: save_event is sync for sqlite, but fast enough. 
    # Ideally async if high volume, but SQLite WAL is plenty fast.
    is_new = save_event(
        event_id=event_id,
        bar_time=payload.bar_time,
        symbol=payload.symbol,
        event_type=payload.event,
        payload_json=json.dumps(data)
    )

    if not is_new:
        return {"status": "ignored_duplicate", "id": event_id}

    # 4. DECISION ENGINE (Async Pipeline)
    # We await the decision process (fetching data) -> usually 1-2s.
    # If this timeout concerns arise, we can move this entirely to background_tasks,
    # but spec implies immediate process trigger.
    try:
        decision_result = await make_decision(data)
        
        # 5. Notify (Background Sync)
        background_tasks.add_task(send_decision_card, decision_result, data)
        
    except Exception as e:
        logger.error(f"Decision Pipeline Failed: {e}")
        # Even if decision fails, we return 200 as we saved the event
    
    return {"status": "received", "id": event_id}
