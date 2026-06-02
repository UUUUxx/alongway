"""
Simple in-memory LLM result cache for v2 optimization.

Uses query hash as key. Same query → instant cache hit, no StepFun API call.
Supports TTL-based expiration.

Usage:
    cache = LLMCache(enabled=True, ttl_seconds=300)
    result = cache.get("从武大去光谷...")
    if result is None:
        result = await call_llm(...)
        cache.set("从武大去光谷...", result)
"""
from __future__ import annotations

import hashlib
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)


class LLMCache:
    """In-memory dict cache for LLM intent parsing results."""

    def __init__(self, enabled: bool = True, ttl_seconds: int = 300) -> None:
        self._store: dict[str, tuple[float, dict]] = {}
        self.enabled = enabled
        self.ttl_seconds = ttl_seconds
        self._hits = 0
        self._misses = 0

    @staticmethod
    def _hash(query: str) -> str:
        """Generate a stable hash for a query string."""
        normalized = query.strip().lower()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]

    def get(self, query: str) -> Optional[dict]:
        """Retrieve cached result. Returns None on miss or if disabled."""
        if not self.enabled:
            self._misses += 1
            return None

        key = self._hash(query)
        entry = self._store.get(key)
        if entry is None:
            self._misses += 1
            logger.debug("LLM cache MISS: query_hash=%s", key)
            return None

        timestamp, result = entry
        if time.time() - timestamp > self.ttl_seconds:
            del self._store[key]
            self._misses += 1
            logger.debug("LLM cache EXPIRED: query_hash=%s", key)
            return None

        self._hits += 1
        logger.info("LLM cache HIT: query_hash=%s", key)
        return dict(result)  # return a copy to prevent mutation

    def set(self, query: str, result: dict) -> None:
        """Store result in cache."""
        if not self.enabled:
            return
        key = self._hash(query)
        self._store[key] = (time.time(), dict(result))
        logger.debug("LLM cache SET: query_hash=%s", key)

    @property
    def stats(self) -> dict:
        """Return cache statistics."""
        return {
            "hits": self._hits,
            "misses": self._misses,
            "size": len(self._store),
            "enabled": self.enabled,
        }

    def clear(self) -> None:
        """Clear all cached entries."""
        self._store.clear()
        self._hits = 0
        self._misses = 0
