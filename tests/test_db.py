"""
Tests for bot.db module.
"""

import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


class TestDatabase:
    """Tests for database operations."""

    @pytest.fixture(autouse=True)
    def setup_temp_db(self, tmp_path):
        """Create temporary database for each test."""
        self.test_db = tmp_path / "test_users.db"
        self.test_data_dir = tmp_path
        
        # Patch the paths before importing
        with patch("bot.config.DB_PATH", self.test_db), \
             patch("bot.config.DATA_DIR", self.test_data_dir):
            # Import after patching
            from bot import db
            self.db = db
            # Reload to pick up patched values
            import importlib
            importlib.reload(db)
            
            # Re-patch after reload
            db.DB_PATH = self.test_db
            db.DATA_DIR = self.test_data_dir
            
            # Initialize
            db.init_db()
            yield

    def test_init_creates_db(self):
        """init_db should create database file."""
        assert self.test_db.exists()

    def test_set_and_get_user_setting(self):
        """Should store and retrieve user settings."""
        self.db.set_user_setting(12345, 9)
        result = self.db.get_user_setting(12345)
        assert result == 9

    def test_get_nonexistent_user(self):
        """Should return None for unknown user."""
        result = self.db.get_user_setting(99999)
        assert result is None

    def test_update_user_setting(self):
        """Should update existing user setting."""
        self.db.set_user_setting(12345, 9)
        self.db.set_user_setting(12345, 15)
        result = self.db.get_user_setting(12345)
        assert result == 15

    def test_delete_user_setting(self):
        """Should delete user setting."""
        self.db.set_user_setting(12345, 9)
        self.db.delete_user_setting(12345)
        result = self.db.get_user_setting(12345)
        assert result is None

    def test_get_users_for_hour(self):
        """Should return all users for specific hour."""
        self.db.set_user_setting(1, 9)
        self.db.set_user_setting(2, 9)
        self.db.set_user_setting(3, 15)
        
        users = self.db.get_all_users_for_hour(9)
        assert len(users) == 2
        assert 1 in users
        assert 2 in users
        assert 3 not in users

    def test_get_users_for_empty_hour(self):
        """Should return empty list for hour with no users."""
        users = self.db.get_all_users_for_hour(23)
        assert users == []
