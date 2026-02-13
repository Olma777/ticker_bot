"""
SQLite persistence layer for user settings.
Persists user preferences across bot restarts.
"""

import sqlite3
import logging
from typing import Optional
from contextlib import contextmanager

from bot.config import DATA_DIR, DB_PATH

logger = logging.getLogger(__name__)


def init_db() -> None:
    """Initialize the database and create tables if they don't exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                briefing_hour INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
    logger.info(f"Database initialized at {DB_PATH}")


@contextmanager
def get_connection():
    """Context manager for database connections."""
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


def get_user_setting(user_id: int) -> Optional[int]:
    """Get the briefing hour for a user. Returns None if not set."""
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT briefing_hour FROM user_settings WHERE user_id = ?",
            (user_id,)
        )
        row = cursor.fetchone()
        return row[0] if row else None


def set_user_setting(user_id: int, hour: int) -> None:
    """Set or update the briefing hour for a user."""
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO user_settings (user_id, briefing_hour, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET 
                briefing_hour = excluded.briefing_hour,
                updated_at = CURRENT_TIMESTAMP
        """, (user_id, hour))
        conn.commit()


def delete_user_setting(user_id: int) -> None:
    """Remove a user's briefing settings."""
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM user_settings WHERE user_id = ?",
            (user_id,)
        )
        conn.commit()


def get_all_users_for_hour(hour: int) -> list[int]:
    """Get all user IDs that have briefing scheduled for the given hour."""
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT user_id FROM user_settings WHERE briefing_hour = ?",
            (hour,)
        )
        return [row[0] for row in cursor.fetchall()]
