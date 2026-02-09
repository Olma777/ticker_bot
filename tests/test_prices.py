"""
Tests for price formatting utility.
"""

import pytest


def format_price(price: float) -> str:
    """Format price based on magnitude (copy from prices.py for isolated testing)."""
    if price < 0.01:
        return f"{price:.8f}"
    elif price < 1:
        return f"{price:.4f}"
    return f"{price:.2f}"


class TestFormatPrice:
    """Tests for price formatting function."""

    def test_very_small_price(self):
        """Prices < 0.01 should show 8 decimals."""
        result = format_price(0.00000123)
        assert result == "0.00000123"

    def test_small_price(self):
        """Prices 0.01-1 should show 4 decimals."""
        result = format_price(0.1234)
        assert result == "0.1234"

    def test_normal_price(self):
        """Prices >= 1 should show 2 decimals."""
        result = format_price(123.456)
        assert result == "123.46"

    def test_large_price(self):
        """Large prices should show 2 decimals."""
        result = format_price(96542.12)
        assert result == "96542.12"

    def test_edge_case_one(self):
        """Price of exactly 1 should show 2 decimals."""
        result = format_price(1.0)
        assert result == "1.00"

    def test_edge_case_small_boundary(self):
        """Price of 0.01 should show 4 decimals."""
        result = format_price(0.01)
        assert result == "0.0100"
