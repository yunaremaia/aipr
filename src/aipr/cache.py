"""Thread-safe TTL cache for policy detection results."""

from __future__ import annotations

import copy
import os
import threading
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from aipr.detector import Policy


# Default TTL: 24 hours (in seconds)
DEFAULT_CACHE_TTL = int(os.environ.get("AIPR_CACHE_TTL", "86400"))
MAX_CACHE_SIZE = int(os.environ.get("AIPR_CACHE_SIZE", "1024"))


@dataclass
class CacheEntry:
    ts: float
    policy: object  # Policy dataclass


class TTLCache:
    """Thread-safe TTL cache with LRU eviction and deep copy on read.
    
    Replaces lru_cache for Policy objects to ensure:
    1. Thread safety via threading.Lock
    2. TTL-based expiration (configurable via AIPR_CACHE_TTL env var)
    3. Deep copy on read to prevent mutation of cached state
    """

    def __init__(self, ttl: int = DEFAULT_CACHE_TTL, maxsize: int = MAX_CACHE_SIZE):
        self._ttl = ttl
        self._maxsize = maxsize
        self._cache: dict[str, CacheEntry] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[object]:
        """Get a cached Policy, returning a deep copy.
        
        Returns None if key not found or entry expired.
        """
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            if time.time() - entry.ts > self._ttl:
                del self._cache[key]
                return None
            return copy.deepcopy(entry.policy)

    def put(self, key: str, policy: object) -> None:
        """Store a Policy with current timestamp.
        
        Evicts oldest entries if cache exceeds maxsize.
        """
        with self._lock:
            while len(self._cache) >= self._maxsize:
                oldest_key = min(self._cache, key=lambda k: self._cache[k].ts)
                del self._cache[oldest_key]
            self._cache[key] = CacheEntry(ts=time.time(), policy=copy.deepcopy(policy))

    def clear(self) -> None:
        """Clear all cached entries."""
        with self._lock:
            self._cache.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._cache)

    def __contains__(self, key: str) -> bool:
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return False
            if time.time() - entry.ts > self._ttl:
                del self._cache[key]
                return False
            return True
