"""Tests for LayeredCache, RuntimeCache, and RedisCache resilience."""
import time
from unittest.mock import MagicMock, patch
import pytest

from app.services.cache import (
    RuntimeCache,
    RedisCache,
    LayeredCache,
    build_cache,
    get_global_cache,
    reset_global_cache,
)


def test_runtime_cache_get_set_ttl():
    """Verify in-memory RuntimeCache basic get, set, default, and expiry."""
    cache = RuntimeCache(default_ttl_seconds=1)
    cache.set("foo", {"data": 123})
    assert cache.get("foo") == {"data": 123}
    assert cache.exists("foo") is True
    assert cache.get_or_default("missing", 42) == 42

    # Test deletion
    cache.delete("foo")
    assert cache.get("foo") is None
    assert cache.exists("foo") is False

    # Test TTL expiration
    cache.set("short_lived", "bar", ttl_seconds=0.05)
    time.sleep(0.06)
    assert cache.get("short_lived") is None


def test_layered_cache_read_through_and_write_through():
    """Verify LayeredCache writes to both layers and reads fallback when primary misses."""
    mock_redis = MagicMock(spec=RedisCache)
    mock_redis.get.return_value = None  # Redis miss
    mock_redis.default_ttl_seconds = 1800

    fallback = RuntimeCache(default_ttl_seconds=1800)
    layered = LayeredCache(primary=mock_redis, fallback=fallback)

    # Set value
    layered.set("key1", {"temp": 42.5})
    assert fallback.get("key1") == {"temp": 42.5}
    mock_redis.set.assert_called_once_with("key1", {"temp": 42.5}, ttl_seconds=None)

    # Get value (Redis returns None, fallback fulfills)
    val = layered.get("key1")
    assert val == {"temp": 42.5}

    # Primary hit scenario
    mock_redis.get.return_value = {"from_redis": True}
    val2 = layered.get("redis_key")
    assert val2 == {"from_redis": True}


def test_layered_cache_resilience_on_redis_exception():
    """Verify LayeredCache handles primary Redis exceptions gracefully without raising."""
    mock_redis = MagicMock(spec=RedisCache)
    mock_redis.get.side_effect = ConnectionError("Redis down")
    mock_redis.set.side_effect = ConnectionError("Redis down")

    fallback = RuntimeCache(default_ttl_seconds=1800)
    fallback.set("safe_key", "survives_outage")

    layered = LayeredCache(primary=mock_redis, fallback=fallback)

    # Get should not throw, returns fallback
    assert layered.get("safe_key") == "survives_outage"

    # Set should not throw, writes to fallback
    layered.set("new_key", "still_cached")
    assert fallback.get("new_key") == "still_cached"


def test_build_cache_fallback_when_no_redis():
    """Verify build_cache returns RuntimeCache when redis_url is None or unreachable."""
    cache = build_cache(redis_url=None, default_ttl_seconds=300)
    assert isinstance(cache, RuntimeCache)
    assert cache.default_ttl_seconds == 300

    # Unreachable redis
    cache_unreach = build_cache(redis_url="redis://localhost:9999/0", default_ttl_seconds=300)
    assert isinstance(cache_unreach, RuntimeCache)


def test_global_cache_singleton():
    """Verify get_global_cache singleton behavior and reset."""
    reset_global_cache()
    c1 = get_global_cache()
    c2 = get_global_cache()
    assert c1 is c2

    reset_global_cache()
    c3 = get_global_cache()
    assert c3 is not None
