from cachetools import TTLCache
from typing import Any, Callable
import asyncio


class TieredCache:
    def __init__(self):
        self._caches = {
            "price": TTLCache(maxsize=100, ttl=5),
            "pscore": TTLCache(maxsize=50, ttl=60),
            "fundamental": TTLCache(maxsize=20, ttl=3600),
        }

    async def get_or_set(self, key: str, fetch_fn: Callable, tier: str = "price") -> Any:
        cache = self._caches.get(tier)
        if not cache:
            raise ValueError(f"Unknown tier: {tier}")
        if key in cache:
            return cache[key]
        value = await fetch_fn() if asyncio.iscoroutinefunction(fetch_fn) else fetch_fn()
        cache[key] = value
        return value
