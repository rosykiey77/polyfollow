import asyncio
import time
from typing import Any, Optional
from app.core.config import settings


class TTLCache:
    """Lightweight in-memory TTL cache with automatic expiration and prefix invalidation."""

    def __init__(self, default_ttl: int = 15):
        self._cache: dict[str, tuple[float, Any]] = {}
        self._default_ttl = default_ttl
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        if not settings.ENABLE_CACHE:
            return None

        async with self._lock:
            if key not in self._cache:
                return None

            expire_at, value = self._cache[key]
            if time.time() > expire_at:
                del self._cache[key]
                return None

            return value

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        if not settings.ENABLE_CACHE:
            return

        effective_ttl = ttl if ttl is not None else self._default_ttl
        expire_at = time.time() + effective_ttl

        async with self._lock:
            # Self-clean expired keys if cache exceeds 500 items
            if len(self._cache) > 500:
                now = time.time()
                keys_to_remove = [k for k, (exp, _) in self._cache.items() if now > exp]
                for k in keys_to_remove:
                    del self._cache[k]

            self._cache[key] = (expire_at, value)

    async def invalidate_prefix(self, prefix: str) -> int:
        """Invalidate all cached items starting with a specific prefix (e.g. 'signals:', 'metrics:')."""
        async with self._lock:
            keys_to_remove = [k for k in self._cache if k.startswith(prefix)]
            for k in keys_to_remove:
                del self._cache[k]
            return len(keys_to_remove)

    async def clear(self) -> None:
        async with self._lock:
            self._cache.clear()


memory_cache = TTLCache(default_ttl=settings.CACHE_TTL_SECONDS)
