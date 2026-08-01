"""Provider response cache for DreamForge Discover.

Persists normalized provider responses to JSON files on disk so repeated
searches (pagination, filtering tweaks) avoid re-hitting the network. Keyed by
provider id + a deterministic hash of the normalized params. TTL-bounded with a
safe default of 10 minutes.

Cache layout (under BACKEND_ROOT/cache/discover/):
- ``responses/<key>.json``   : one cached provider response
- ``index.json``             : key -> {cached_at, ttl}
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from _paths import BACKEND_ROOT

DEFAULT_TTL_SECONDS = 600

CACHE_DIR = BACKEND_ROOT / "cache" / "discover"
_RESPONSES_DIR = CACHE_DIR / "responses"
_INDEX_PATH = CACHE_DIR / "index.json"


def _now() -> float:
    return time.time()


def params_cache_key(provider_id: str, params: Any) -> str:
    """Deterministic cache key for a provider + normalized params."""
    payload = json.dumps(
        {
            "provider": provider_id,
            "query": params.query,
            "kind": params.kind,
            "limit": params.limit,
            "page": params.page,
            "filters": params.filters.to_cache_key(),
        },
        sort_keys=True,
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
    return f"{provider_id}_{digest}"


def _load_index() -> dict[str, dict[str, Any]]:
    if _INDEX_PATH.exists():
        try:
            with open(_INDEX_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_index(index: dict[str, dict[str, Any]]) -> None:
    _INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)


def get_cached_response(key: str, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> dict[str, Any] | None:
    """Return a cached provider response dict, or None if missing/expired."""
    index = _load_index()
    entry = index.get(key)
    if not entry:
        return None
    cached_at = float(entry.get("cached_at") or 0)
    if _now() - cached_at > ttl_seconds:
        return None
    path = _RESPONSES_DIR / f"{key}.json"
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def put_cached_response(key: str, data: dict[str, Any], ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
    """Store a provider response for a given key."""
    _RESPONSES_DIR.mkdir(parents=True, exist_ok=True)
    with open(_RESPONSES_DIR / f"{key}.json", "w", encoding="utf-8") as f:
        json.dump(data, f)
    index = _load_index()
    index[key] = {"cached_at": _now(), "ttl": ttl_seconds}
    _save_index(index)


def invalidate(provider_id: str | None = None) -> int:
    """Clear cache entries, optionally filtered by provider id. Returns count."""
    index = _load_index()
    removed = 0
    for key in list(index.keys()):
        if provider_id is None or key.startswith(provider_id + "_"):
            path = _RESPONSES_DIR / f"{key}.json"
            if path.exists():
                path.unlink()
            index.pop(key, None)
            removed += 1
    _save_index(index)
    return removed
