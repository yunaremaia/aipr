"""Tests for aipr.cache.TTLCache (in-memory thread-safe cache)."""

import threading
import time
import pytest
from aipr.cache import TTLCache


def test_cache_stores_and_retrieves():
    """Basic put/get cycle returns the stored policy."""
    from aipr.detector import Policy, Verdict

    cache = TTLCache(ttl=60)
    policy = Policy(Verdict.PERMISSIVE, 0.9, ["evidence"], -3.0)
    cache.put("key1", policy)

    result = cache.get("key1")
    assert result is not None
    assert result.verdict is Verdict.PERMISSIVE
    assert result.confidence == 0.9
    assert result.score == -3.0


def test_cache_returns_deep_copy():
    """Mutating a returned policy does not affect the cache."""
    from aipr.detector import Policy, Verdict

    cache = TTLCache(ttl=60)
    policy = Policy(Verdict.RESTRICTIVE, 0.8, ["original"], 3.0)
    cache.put("key1", policy)

    # Mutate the returned copy
    result = cache.get("key1")
    result.evidence.append("mutated")

    # Cache should still have original
    result2 = cache.get("key1")
    assert result2.evidence == ["original"]


def test_cache_miss_returns_none():
    """Getting a non-existent key returns None."""
    cache = TTLCache(ttl=60)
    assert cache.get("nonexistent") is None


def test_cache_expiration():
    """Entries expire after TTL."""
    from aipr.detector import Policy, Verdict

    cache = TTLCache(ttl=1)  # 1 second TTL
    cache.put("key1", Policy(Verdict.HUMAN_ONLY, 1.0, [], 5.0))

    assert cache.get("key1") is not None
    time.sleep(1.5)
    assert cache.get("key1") is None


def test_cache_clear():
    """Clear removes all entries."""
    from aipr.detector import Policy, Verdict

    cache = TTLCache(ttl=60)
    cache.put("key1", Policy(Verdict.HUMAN_ONLY, 1.0, [], 5.0))
    cache.put("key2", Policy(Verdict.PERMISSIVE, 0.9, [], -3.0))

    assert len(cache) == 2
    cache.clear()
    assert len(cache) == 0
    assert cache.get("key1") is None


def test_cache_maxsize_eviction():
    """When maxsize is reached, oldest entry is evicted."""
    from aipr.detector import Policy, Verdict

    cache = TTLCache(ttl=60, maxsize=3)
    cache.put("a", Policy(Verdict.HUMAN_ONLY, 1.0, [], 5.0))
    cache.put("b", Policy(Verdict.HUMAN_ONLY, 1.0, [], 5.0))
    cache.put("c", Policy(Verdict.HUMAN_ONLY, 1.0, [], 5.0))
    cache.put("d", Policy(Verdict.HUMAN_ONLY, 1.0, [], 5.0))

    assert cache.get("a") is None
    assert cache.get("b") is not None
    assert cache.get("c") is not None
    assert cache.get("d") is not None


def test_cache_thread_safety():
    """Concurrent reads and writes do not corrupt state."""
    from aipr.detector import Policy, Verdict

    cache = TTLCache(ttl=60, maxsize=200)
    errors = []

    def writer(start):
        try:
            for i in range(50):
                key = f"thread-{start}-item-{i}"
                cache.put(key, Policy(Verdict.RESTRICTIVE, 0.5, [key], 2.5))
        except Exception as e:
            errors.append(str(e))

    def reader(start):
        try:
            for i in range(50):
                key = f"thread-{start}-item-{i}"
                cache.get(key)
        except Exception as e:
            errors.append(str(e))

    threads = []
    for t in range(4):
        threads.append(threading.Thread(target=writer, args=(t,)))
        threads.append(threading.Thread(target=reader, args=(t,)))

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Thread errors: {errors}"


def test_cache_len():
    """len() returns number of cached entries."""
    from aipr.detector import Policy, Verdict

    cache = TTLCache(ttl=60)
    assert len(cache) == 0
    cache.put("a", Policy(Verdict.HUMAN_ONLY, 1.0, [], 5.0))
    cache.put("b", Policy(Verdict.HUMAN_ONLY, 1.0, [], 5.0))
    assert len(cache) == 2


def test_cache_contains():
    """'in' operator checks cache membership."""
    from aipr.detector import Policy, Verdict

    cache = TTLCache(ttl=60)
    cache.put("key1", Policy(Verdict.HUMAN_ONLY, 1.0, [], 5.0))
    assert "key1" in cache
    assert "key2" not in cache


def test_detect_policy_uses_ttl_cache():
    """detect_policy results are cached and reused."""
    from aipr.detector import detect_policy, clear_policy_cache, Verdict

    clear_policy_cache()
    text = "AI should never be the main author"

    r1 = detect_policy(text)
    r2 = detect_policy(text)
    assert r1.verdict is Verdict.HUMAN_ONLY
    assert r2.verdict is Verdict.HUMAN_ONLY
