"""
SQLite database module for webhook event storage.
Handles event deduplication and persistence.
"""

import sqlite3
import logging
from contextlib import contextmanager

from bot.config import Config

logger = logging.getLogger(__name__)


def init_db() -> None:
    """Initialize database and create tables."""
    Config.DATA_DIR.mkdir(parents=True, exist_ok=True)

    with get_connection() as conn:
        conn.execute("""
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
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_bar_time 
            ON events(bar_time)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_symbol 
            ON events(symbol)
        """)
        conn.commit()
    logger.info(f"Database initialized at {Config.DATABASE_URL}")


@contextmanager
def get_connection():
    """Context manager for database connections."""
    conn = sqlite3.connect(Config.DATABASE_URL)
    try:
        yield conn
    finally:
        conn.close()


def save_event(
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
    with get_connection() as conn:
        try:
            conn.execute(
                """
                INSERT INTO events (event_id, bar_time, symbol, event_type, payload_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (event_id, bar_time, symbol, event_type, payload_json),
            )
            conn.commit()
            logger.info(f"Saved event: {event_id[:16]}... ({symbol} {event_type})")
            return True
        except sqlite3.IntegrityError:
            # Duplicate event_id
            logger.debug(f"Duplicate event ignored: {event_id[:16]}...")
            return False


def get_recent_events(symbol: str = None, limit: int = 50) -> list[dict]:
    """Get recent events, optionally filtered by symbol."""
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        
        if symbol:
            cursor = conn.execute(
                """
                SELECT * FROM events 
                WHERE symbol = ? 
                ORDER BY bar_time DESC 
                LIMIT ?
                """,
                (symbol, limit),
            )
        else:
            cursor = conn.execute(
                """
                SELECT * FROM events 
                ORDER BY bar_time DESC 
                LIMIT ?
                """,
                (limit,),
            )
        
        return [dict(row) for row in cursor.fetchall()]
