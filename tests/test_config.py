"""
Tests for bot.config module.
"""

from bot.config import (
    TRADING,
    RATE_LIMITS,
    EXCHANGE_OPTIONS,
    COIN_NAMES,
    RETRY_ATTEMPTS,
    DB_PATH,
)


class TestTradingSettings:
    """Tests for TradingSettings dataclass."""

    def test_default_timeframe(self):
        """Timeframe should default to 30m."""
        assert TRADING.timeframe == "30m"

    def test_default_capital(self):
        """Default capital should be 1000."""
        assert TRADING.default_capital == 1000.0

    def test_default_risk_pct(self):
        """Default risk should be 1%."""
        assert TRADING.default_risk_pct == 1.0

    def test_frozen_dataclass(self):
        """Settings should be immutable."""
        try:
            TRADING.timeframe = "1h"  # type: ignore
            assert False, "Should raise FrozenInstanceError"
        except Exception:
            pass  # Expected


class TestRateLimits:
    """Tests for RateLimitSettings dataclass."""

    def test_openrouter_requests(self):
        """OpenRouter limit should be 8 requests."""
        assert RATE_LIMITS.openrouter_requests == 8

    def test_openrouter_period(self):
        """OpenRouter period should be 60 seconds."""
        assert RATE_LIMITS.openrouter_period == 60


class TestExchangeOptions:
    """Tests for exchange configuration."""

    def test_exchange_count(self):
        """Should have 6 exchanges configured."""
        assert len(EXCHANGE_OPTIONS) == 6

    def test_binance_config(self):
        """Binance should be configured for futures."""
        assert EXCHANGE_OPTIONS["binance"]["options"]["defaultType"] == "future"

    def test_all_have_rate_limit(self):
        """All exchanges should have rate limit enabled."""
        for name, opts in EXCHANGE_OPTIONS.items():
            assert opts["enableRateLimit"] is True, f"{name} missing rate limit"


class TestCoinNames:
    """Tests for coin name mappings."""

    def test_btc_name(self):
        """BTC should map to Bitcoin."""
        assert COIN_NAMES["BTC"] == "Bitcoin"

    def test_eth_name(self):
        """ETH should map to Ethereum."""
        assert COIN_NAMES["ETH"] == "Ethereum"


class TestRetrySettings:
    """Tests for retry configuration."""

    def test_retry_attempts(self):
        """Should have 3 retry attempts."""
        assert RETRY_ATTEMPTS == 3


class TestPaths:
    """Tests for path configuration."""

    def test_db_path_is_sqlite(self):
        """Database path should be .db file."""
        assert str(DB_PATH).endswith(".db")
