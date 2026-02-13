"""
SQLite persistence layer for user settings.
Persists user preferences across bot restarts.
"""

import aiosqlite
import logging
from typing import Optional

from bot.config import DATA_DIR, DB_PATH

logger = logging.getLogger(__name__)


async def init_db() -> None:
    """Initialize the database and create tables if they don't exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                briefing_hour INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await conn.commit()
    logger.info(f"Database initialized at {DB_PATH}")


async def get_user_setting(user_id: int) -> Optional[int]:
    """Get the briefing hour for a user. Returns None if not set."""
    async with aiosqlite.connect(DB_PATH) as conn:
        async with conn.execute(
            "SELECT briefing_hour FROM user_settings WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None


async def set_user_setting(user_id: int, hour: int) -> None:
    """Set or update the briefing hour for a user."""
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute("""
            INSERT INTO user_settings (user_id, briefing_hour, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET 
                briefing_hour = excluded.briefing_hour,
                updated_at = CURRENT_TIMESTAMP
        """, (user_id, hour))
        await conn.commit()


async def delete_user_setting(user_id: int) -> None:
    """Remove a user's briefing settings."""
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            "DELETE FROM user_settings WHERE user_id = ?",
            (user_id,)
        )
        await conn.commit()


async def get_all_users_for_hour(hour: int) -> list[int]:
    """Get all user IDs that have briefing scheduled for the given hour."""
    async with aiosqlite.connect(DB_PATH) as conn:
        async with conn.execute(
            "SELECT user_id FROM user_settings WHERE briefing_hour = ?",
            (hour,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]
