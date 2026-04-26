"""TTL-based in-memory cache for deterministic prediction results."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class CacheItem:
    """Single cache entry with expiry metadata."""

    payload: Dict[str, Any]
    expires_at: float
    model_version: str


class CacheService:
    """Thread-safe in-memory cache with TTL and model-version invalidation."""

    _instance: "CacheService | None" = None
    _instance_lock = threading.Lock()

    def __init__(self, ttl_seconds: int = 300) -> None:
        self.ttl_seconds = int(ttl_seconds)
        self._lock = threading.Lock()
        self._store: Dict[str, CacheItem] = {}

    @classmethod
    def get_instance(cls, ttl_seconds: int = 300) -> "CacheService":
        """Get singleton cache service instance."""
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = CacheService(ttl_seconds=ttl_seconds)
            else:
                cls._instance.ttl_seconds = int(ttl_seconds)
        return cls._instance

    def get(self, key: str, model_version: str) -> Optional[Dict[str, Any]]:
        """Get cached payload if key exists, unexpired, and model_version matches."""
        now = time.time()
        with self._lock:
            item = self._store.get(key)
            if item is None:
                return None
            if item.expires_at < now:
                self._store.pop(key, None)
                return None
            if item.model_version != str(model_version):
                self._store.pop(key, None)
                return None
            return item.payload

    def set(self, key: str, payload: Dict[str, Any], model_version: str) -> None:
        """Set cache entry for key using configured TTL."""
        expiry = time.time() + max(self.ttl_seconds, 1)
        with self._lock:
            self._store[key] = CacheItem(payload=payload, expires_at=expiry, model_version=str(model_version))

    def invalidate_all(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._store.clear()

    def cleanup_expired(self) -> int:
        """Remove expired cache keys and return count."""
        now = time.time()
        removed = 0
        with self._lock:
            for key in list(self._store.keys()):
                if self._store[key].expires_at < now:
                    self._store.pop(key, None)
                    removed += 1
        return removed

    def stats(self) -> Dict[str, Any]:
        """Return simple cache statistics."""
        with self._lock:
            return {
                "size": len(self._store),
                "ttl_seconds": self.ttl_seconds,
            }
