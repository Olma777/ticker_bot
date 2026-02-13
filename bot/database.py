"""
SQLite database module for webhook event storage.
Handles event deduplication and persistence.
"""

import aiosqlite
import logging

from bot.config import Config

logger = logging.getLogger(__name__)


async def init_db() -> None:
    """Initialize database and create tables."""
    Config.DATA_DIR.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(Config.DATABASE_URL) as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT UNIQUE NOT NULL,
                bar_time INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_bar_time 
            ON events(bar_time)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_symbol 
            ON events(symbol)
        """)
        await conn.commit()
    logger.info(f"Database initialized at {Config.DATABASE_URL}")


async def save_event(
    event_id: str,
    bar_time: int,
    symbol: str,
    event_type: str,
    payload_json: str,
) -> bool:
    """
    Save event to database.
    
    Returns:
        True if new event was inserted, False if duplicate.
    """
    async with aiosqlite.connect(Config.DATABASE_URL) as conn:
        try:
            await conn.execute(
                """
                INSERT INTO events (event_id, bar_time, symbol, event_type, payload_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (event_id, bar_time, symbol, event_type, payload_json),
            )
            await conn.commit()
            logger.info(f"Saved event: {event_id[:16]}... ({symbol} {event_type})")
            return True
        except aiosqlite.IntegrityError:
            # Duplicate event_id
            logger.debug(f"Duplicate event ignored: {event_id[:16]}...")
            return False


async def get_recent_events(symbol: str = None, limit: int = 50) -> list[dict]:
    """Get recent events, optionally filtered by symbol."""
    async with aiosqlite.connect(Config.DATABASE_URL) as conn:
        conn.row_factory = aiosqlite.Row
        
        if symbol:
            async with conn.execute(
                """
                SELECT * FROM events 
                WHERE symbol = ? 
                ORDER BY bar_time DESC 
                LIMIT ?
                """,
                (symbol, limit),
            ) as cursor:
                rows = await cursor.fetchall()
        else:
            async with conn.execute(
                """
                SELECT * FROM events 
                ORDER BY bar_time DESC 
                LIMIT ?
                """,
                (limit,),
            ) as cursor:
                rows = await cursor.fetchall()
        
        return [dict(row) for row in rows]
