"""
Cache layer for FlashAPI with graceful fallback.

Prevents Bug #4 (cache failure crash) by catching exceptions and continuing without cache.
Supports Redis, Memcached, and in-memory stores.
"""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from typing import Any


class CacheBackend(ABC):
    """Abstract cache interface."""

    @abstractmethod
    def get(self, key: str) -> Any | None:
        """Get value from cache. Returns None if not found or error."""
        ...

    @abstractmethod
    def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """Set value in cache with TTL (seconds). Returns success."""
        ...

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete key from cache. Returns success."""
        ...

    @abstractmethod
    def clear(self) -> bool:
        """Clear all cache. Returns success."""
        ...


class InMemoryCache(CacheBackend):
    """In-memory cache (for development/testing)."""

    def __init__(self):
        self._store: dict[str, tuple[Any, float]] = {}  # {key: (value, expire_at)}

    def get(self, key: str) -> Any | None:
        if key not in self._store:
            return None
        value, expire_at = self._store[key]
        if time.time() > expire_at:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        self._store[key] = (value, time.time() + ttl)
        return True

    def delete(self, key: str) -> bool:
        if key in self._store:
            del self._store[key]
            return True
        return False

    def clear(self) -> bool:
        self._store.clear()
        return True


class RedisCache(CacheBackend):
    """Redis cache with graceful fallback."""

    def __init__(self, host: str = "localhost", port: int = 6379, db: int = 0):
        try:
            import redis
            self._redis = redis.Redis(host=host, port=port, db=db, decode_responses=True)
            self._redis.ping()  # Test connection
            self._available = True
        except Exception:
            self._redis = None
            self._available = False

    def get(self, key: str) -> Any | None:
        if not self._available:
            return None
        try:
            value = self._redis.get(key)
            if value is None:
                return None
            return json.loads(value)
        except Exception:
            return None

    def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        if not self._available:
            return False
        try:
            self._redis.setex(key, ttl, json.dumps(value))
            return True
        except Exception:
            return False

    def delete(self, key: str) -> bool:
        if not self._available:
            return False
        try:
            self._redis.delete(key)
            return True
        except Exception:
            return False

    def clear(self) -> bool:
        if not self._available:
            return False
        try:
            self._redis.flushdb()
            return True
        except Exception:
            return False


class CacheLayer:
    """
    Cache layer with graceful fallback for FlashAPI.

    Usage:
        from flashapi.features.cache import CacheLayer, RedisCache

        cache = CacheLayer(RedisCache(host='localhost'))

        # Get (never crashes)
        value = cache.get('users:123')  # Returns None if cache down

        # Set (never crashes)
        cache.set('users:123', {'name': 'John'}, ttl=600)

    Features:
        - Automatic exception handling (never crashes app)
        - Graceful fallback if cache unavailable
        - Logging for debugging
    """

    def __init__(self, backend: CacheBackend | None = None, log_errors: bool = True):
        self.backend = backend or InMemoryCache()
        self.log_errors = log_errors

    def get(self, key: str) -> Any | None:
        """Get value from cache. Never crashes."""
        try:
            return self.backend.get(key)
        except Exception as e:
            if self.log_errors:
                print(f"[FlashAPI Cache] GET error: {e}")
            return None

    def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """Set value in cache. Never crashes."""
        try:
            return self.backend.set(key, value, ttl)
        except Exception as e:
            if self.log_errors:
                print(f"[FlashAPI Cache] SET error: {e}")
            return False

    def delete(self, key: str) -> bool:
        """Delete key from cache. Never crashes."""
        try:
            return self.backend.delete(key)
        except Exception as e:
            if self.log_errors:
                print(f"[FlashAPI Cache] DELETE error: {e}")
            return False

    def clear(self) -> bool:
        """Clear all cache. Never crashes."""
        try:
            return self.backend.clear()
        except Exception as e:
            if self.log_errors:
                print(f"[FlashAPI Cache] CLEAR error: {e}")
            return False


# Global cache instance
_CACHE: CacheLayer | None = None


def register_cache(cache: CacheLayer) -> None:
    """Register global cache instance."""
    global _CACHE
    _CACHE = cache


def get_cache() -> CacheLayer | None:
    """Get global cache instance."""
    return _CACHE


# Convenience decorators for route caching
def cached(ttl: int = 300, key_prefix: str = ""):
    """
    Decorator to cache route responses.

    Usage:
        @cached(ttl=600, key_prefix='users')
        def get_user(user_id):
            return {...}
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            cache = get_cache()
            if cache is None:
                return func(*args, **kwargs)

            # Build cache key
            cache_key = f"{key_prefix}:{func.__name__}:{args}:{kwargs}"

            # Try cache first
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                return cached_value

            # Cache miss: compute and store
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl)
            return result

        return wrapper
    return decorator
