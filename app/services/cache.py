"""Layered caching infrastructure (Redis primary + thread-safe in-memory fallback).

Adapted from WalkFit reference (app/services/redis_cache.py).
Ensures sub-millisecond fast-path reads and survives Redis unavailability.
"""
from __future__ import annotations

import json
import logging
from threading import Lock
from time import time
from typing import Any

logger = logging.getLogger("coolpath.cache")


class RuntimeCache:
    """Thread-safe in-memory TTL dictionary cache."""

    def __init__(self, default_ttl_seconds: int = 1800) -> None:
        self.default_ttl_seconds = default_ttl_seconds
        self._values: dict[str, tuple[float, Any]] = {}
        self._lock = Lock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            item = self._values.get(key)
            if item is None:
                return None
            expires_at, value = item
            if expires_at < time():
                self._values.pop(key, None)
                return None
            return value

    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl_seconds
        with self._lock:
            self._values[key] = (time() + ttl, value)

    def get_or_default(self, key: str, default: Any = None) -> Any:
        val = self.get(key)
        return default if val is None else val

    def exists(self, key: str) -> bool:
        return self.get(key) is not None

    def delete(self, key: str) -> None:
        with self._lock:
            self._values.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._values.clear()


class RedisCache:
    """Synchronous Redis-backed cache with automatic JSON serialization."""

    KEY_PREFIX = "coolpath:cache"

    def __init__(self, redis_url: str, *, default_ttl_seconds: int = 1800) -> None:
        import redis
        self._redis = redis.Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=0.5,  # fail fast if Redis is not running
            socket_timeout=0.5,
        )
        self.default_ttl_seconds = default_ttl_seconds
        self._redis_url = redis_url

    def _key(self, key: str) -> str:
        return f"{self.KEY_PREFIX}:{key}"

    def get(self, key: str) -> Any | None:
        try:
            raw = self._redis.get(self._key(key))
            if raw is None:
                return None
            try:
                return json.loads(raw)
            except (TypeError, ValueError):
                logger.warning("RedisCache: non-JSON value at %r; treating as miss", key[:80])
                return None
        except Exception as exc:
            logger.warning("RedisCache.get failed (%s) for key %s", type(exc).__name__, key[:80])
            return None

    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        try:
            payload = json.dumps(value)
        except (TypeError, ValueError):
            logger.warning("RedisCache: refusing to set non-JSON-serialisable value for %r", key[:80])
            return

        try:
            ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl_seconds
            self._redis.setex(self._key(key), ttl, payload)
        except Exception as exc:
            logger.warning("RedisCache.set failed (%s) for key %s", type(exc).__name__, key[:80])

    def get_or_default(self, key: str, default: Any = None) -> Any:
        val = self.get(key)
        return default if val is None else val

    def exists(self, key: str) -> bool:
        try:
            return bool(self._redis.exists(self._key(key)))
        except Exception:
            return False

    def delete(self, key: str) -> None:
        try:
            self._redis.delete(self._key(key))
        except Exception as exc:
            logger.warning("RedisCache.delete failed (%s) for key %s", type(exc).__name__, key[:80])

    def clear(self) -> None:
        try:
            keys = self._redis.keys(f"{self.KEY_PREFIX}:*")
            if keys:
                self._redis.delete(*keys)
        except Exception as exc:
            logger.warning("RedisCache.clear failed (%s)", type(exc).__name__)


class LayeredCache:
    """Read-through / write-through layered cache (Redis primary + in-memory fallback).
    
    Guarantees that write operations write to local memory first, and reads seamlessly
    fall back to memory on Redis connection timeout, error, or miss.
    """

    def __init__(self, primary: RedisCache, fallback: RuntimeCache) -> None:
        self.primary = primary
        self.fallback = fallback
        self.default_ttl_seconds = fallback.default_ttl_seconds

    def get(self, key: str) -> Any | None:
        try:
            val = self.primary.get(key)
            if val is not None:
                return val
        except Exception as exc:
            logger.warning(
                "LayeredCache: primary get failed (%s) for %r; using fallback",
                type(exc).__name__, key[:80],
            )
        return self.fallback.get(key)

    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        # Fallback in-memory first — guarantees local availability
        self.fallback.set(key, value, ttl_seconds=ttl_seconds)
        try:
            self.primary.set(key, value, ttl_seconds=ttl_seconds)
        except Exception as exc:
            logger.warning(
                "LayeredCache: primary set failed (%s) for %r; fallback already written",
                type(exc).__name__, key[:80],
            )

    def get_or_default(self, key: str, default: Any = None) -> Any:
        val = self.get(key)
        return default if val is None else val

    def exists(self, key: str) -> bool:
        if self.fallback.exists(key):
            return True
        try:
            return self.primary.exists(key)
        except Exception:
            return False

    def delete(self, key: str) -> None:
        self.fallback.delete(key)
        try:
            self.primary.delete(key)
        except Exception:
            pass

    def clear(self) -> None:
        self.fallback.clear()
        try:
            self.primary.clear()
        except Exception:
            pass


def build_cache(*, redis_url: str | None = None, default_ttl_seconds: int = 1800) -> RuntimeCache | LayeredCache:
    """Factory creating LayeredCache if Redis is reachable, otherwise RuntimeCache."""
    fallback = RuntimeCache(default_ttl_seconds=default_ttl_seconds)
    if not redis_url:
        return fallback

    try:
        primary = RedisCache(redis_url, default_ttl_seconds=default_ttl_seconds)
        # Probe Redis connection directly to bypass get() error swallowing
        primary._redis.ping()
        return LayeredCache(primary, fallback)
    except Exception as exc:
        logger.info("Redis unavailable (%s); using in-process RuntimeCache", type(exc).__name__)
        return fallback


_cache_instance: RuntimeCache | LayeredCache | None = None


def get_global_cache() -> RuntimeCache | LayeredCache:
    """Return the shared global cache instance."""
    global _cache_instance
    if _cache_instance is None:
        from app.config import get_settings
        settings = get_settings()
        _cache_instance = build_cache(
            redis_url=settings.redis_url,
            default_ttl_seconds=settings.cache_default_ttl_seconds,
        )
    return _cache_instance


def reset_global_cache() -> None:
    """Reset the singleton instance (useful for test isolation)."""
    global _cache_instance
    _cache_instance = None


__all__ = [
    "RuntimeCache",
    "RedisCache",
    "LayeredCache",
    "build_cache",
    "get_global_cache",
    "reset_global_cache",
]
