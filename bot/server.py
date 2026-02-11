"""
Market Lens - Webhook Endpoint.
Receives TradingView alerts and triggers the Decision Engine.
Phase 2 Update: Background processing for instant 200 OK.
"""

import logging
import json
import hashlib
import hmac
from contextlib import asynccontextmanager
from fastapi import FastAPI, Header, HTTPException, BackgroundTasks
from pydantic import BaseModel, field_validator
from typing import Literal

from bot.config import Config
from bot.database import init_db, save_event
from bot.decision_engine import process_signal
from bot.notifier import send_card

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
    score: float = Field(alias="sc")  # FIXED: Pine Script sends 'sc', we map to 'score'
    regime: str
    # Optional fields or fields used in logic
    touches: int = 0
    
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


async def run_analysis_pipeline(payload_data: dict):
    """
    Background Task: Encapsulates the Decision Engine pipeline.
    1. Parse & Process (Engine)
    2. Notify (Telegram)
    """
    try:
        # Call Decision Engine
        result = await process_signal(payload_data)
        
        # Send Notification
        await send_card(result)
        
    except Exception as e:
        logger.error(f"Analysis Pipeline Failed for {payload_data.get('symbol')}: {e}")


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
    
    # Save Event (Sync/Fast)
    is_new = save_event(
        event_id=event_id,
        bar_time=payload.bar_time,
        symbol=payload.symbol,
        event_type=payload.event,
        payload_json=json.dumps(data)
    )

    if not is_new:
        return {"status": "ignored_duplicate", "id": event_id}

    # 4. Trigger Analysis (Background)
    # Return 200 immediately to TradingView
    background_tasks.add_task(run_analysis_pipeline, data)
    
    return {"status": "received", "id": event_id}
