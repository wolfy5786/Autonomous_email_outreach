"""Check whether a company has already been sourced recently."""
import hashlib
import time
from typing import Optional
from dataclasses import dataclass


@dataclass
class CacheEntry:
    key: str
    sourced_at: float
    ttl: int


class SourceCache:
    """In-memory cache for sourced company deduplication."""

    def __init__(self, ttl_seconds: int = 86400) -> None:
        self._store: dict[str, CacheEntry] = {}
        self._ttl = ttl_seconds

    @staticmethod
    def _make_key(company_name: str, domain: str) -> str:
        raw = f"{company_name.lower().strip()}:{domain.lower().strip()}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def is_cached(self, company_name: str, domain: str) -> bool:
        key = self._make_key(company_name, domain)
        entry = self._store.get(key)
        if entry is None:
            return False
        if time.time() - entry.sourced_at > self._ttl:
            del self._store[key]
            return False
        return True

    def mark_sourced(self, company_name: str, domain: str) -> None:
        key = self._make_key(company_name, domain)
        self._store[key] = CacheEntry(key=key, sourced_at=time.time(), ttl=self._ttl)

    def clear_expired(self) -> int:
        now = time.time()
        expired = [k for k, v in self._store.items() if now - v.sourced_at > self._ttl]
        for k in expired:
            del self._store[k]
        return len(expired)

    @property
    def size(self) -> int:
        return len(self._store)
