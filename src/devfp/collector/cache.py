"""Disk-based cache for GitHub API responses."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import diskcache


_DEFAULT_CACHE_DIR = Path.home() / ".cache" / "dev-fingerprint"


class GitHubCache:
    def __init__(self, cache_dir: Optional[Path] = None, ttl: int = 86400 * 7) -> None:
        self._dir = cache_dir or _DEFAULT_CACHE_DIR
        self._dir.mkdir(parents=True, exist_ok=True)
        self._cache: diskcache.Cache = diskcache.Cache(str(self._dir))
        self._ttl = ttl

    def get(self, key: str) -> Optional[Any]:
        return self._cache.get(key)

    def set(self, key: str, value: Any) -> None:
        self._cache.set(key, value, expire=self._ttl)

    def clear(self) -> None:
        self._cache.clear()

    def close(self) -> None:
        self._cache.close()

    def __enter__(self) -> GitHubCache:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
