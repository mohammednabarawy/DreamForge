"""Discovery service for DreamForge Discover & Library.

Coordinates searches across registered providers (plan §11):

- Searches enabled providers **in parallel**.
- Each provider runs under a hard per-provider timeout so a slow provider can
  never hang the Discover screen.
- Failures are captured per-provider and returned as partial results — "one
  provider failing must not blank the entire Discover screen".
- Responses are cached on disk via :mod:`dreamforge_discovery_cache`.
- Results are deduplicated across providers by physical-file SHA256
  (plan §31.14 identity rule) while preserving each provider's copy.
"""

from __future__ import annotations

import re
import threading
from dataclasses import replace
from pathlib import Path
from typing import Any

from dreamforge_discovery_cache import get_cached_response, params_cache_key, put_cached_response
from dreamforge_provider_base import ProviderSearchParams, ProviderSearchResult
from dreamforge_provider_registry import ProviderRegistry, default_provider_registry


def _compact_text(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


def _asset_query_relevance(asset: dict[str, Any], query: str) -> int:
    """Score how closely an asset matches the user's search query (0 = unrelated)."""
    raw_query = (query or "").strip().lower()
    if not raw_query:
        return 1
    compact_q = _compact_text(raw_query)
    tokens = [tok for tok in re.split(r"[\s/_-]+", raw_query) if tok]
    compact_tokens = [_compact_text(tok) for tok in tokens if _compact_text(tok)]

    name = str(asset.get("name") or "")
    name_lower = name.lower()
    name_compact = _compact_text(name)
    arch = str(asset.get("architecture") or "").lower()
    arch_compact = _compact_text(arch)
    tags_text = " ".join(str(t) for t in (asset.get("tags") or []))
    versions = asset.get("versions") or []
    base_models = " ".join(str(v.get("base_model") or "") for v in versions)
    filenames = " ".join(
        str(f.get("filename") or "")
        for v in versions
        for f in (v.get("files") or [])[:12]
    )
    author = str((asset.get("provenance") or {}).get("author") or "")
    description = str(asset.get("description") or "")

    score = 0
    if compact_q and name_compact == compact_q:
        score += 140
    elif compact_q and name_compact.startswith(compact_q):
        score += 110
    elif raw_query in name_lower or (compact_q and compact_q in name_compact):
        score += 85

    if compact_q and (compact_q in arch_compact or compact_q in _compact_text(base_models)):
        score += 55

    meta_blob = f"{name} {arch} {base_models} {tags_text} {author} {filenames}".lower()
    meta_compact = _compact_text(meta_blob)
    if compact_q and compact_q in meta_compact:
        score += 35

    if compact_tokens:
        matched_tokens = sum(1 for tok in compact_tokens if tok in meta_compact)
        if matched_tokens == len(compact_tokens):
            score += 40
        elif matched_tokens > 0:
            score += matched_tokens * 12

    if score == 0 and compact_q:
        desc_compact = _compact_text(description)
        if compact_q in desc_compact:
            score += 15
    return score


class DiscoveryService:
    """Runs normalized searches across registered providers."""

    def __init__(
        self,
        registry: ProviderRegistry | None = None,
        asset_registry: Any | None = None,
        use_cache: bool = True,
        max_workers: int = 8,
        cache_ttl_seconds: int = 600,
    ) -> None:
        self.registry = registry or default_provider_registry()
        self.asset_registry = asset_registry
        self.use_cache = use_cache
        self.max_workers = max_workers
        self.cache_ttl_seconds = cache_ttl_seconds
        self._lock = threading.Lock()

    def search(
        self,
        params: ProviderSearchParams | None = None,
        *,
        provider_ids: list[str] | None = None,
        provider_cursors: dict[str, str] | None = None,
        query: str = "",
        kind: str = "",
        limit: int = 20,
        page: int = 1,
        nsfw: bool = False,
        sort: str = "relevance",
    ) -> dict[str, Any]:
        """Search enabled providers in parallel. Returns the response envelope."""
        if params is None:
            from dreamforge_provider_base import SearchFilters

            params = ProviderSearchParams(
                query=query or "",
                kind=kind or "",
                limit=max(1, limit),
                page=max(1, page),
                filters=SearchFilters(nsfw=nsfw, sort=sort),
            )

        providers = self._selected_providers(params.kind, provider_ids)
        results: list[ProviderSearchResult] = [None] * len(providers)  # type: ignore[list-item]

        def run(index: int, provider_id: str) -> None:
            provider = self.registry.get(provider_id)
            if provider is None:
                results[index] = ProviderSearchResult(
                    provider=provider_id,
                    error="Unknown provider",
                    error_code="provider_error",
                    page=params.page,
                )
                return
            provider_params = replace(
                params,
                cursor=str((provider_cursors or {}).get(provider_id) or ""),
            )
            results[index] = self._search_one(provider, provider_params)

        threads = [
            threading.Thread(target=run, args=(i, p.id), name=f"discover-{p.id}")
            for i, p in enumerate(providers)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        ordered = [r for r in results if r is not None]
        return self._assemble_response(ordered, params)

    def search_provider(self, provider_id: str, params: ProviderSearchParams) -> ProviderSearchResult:
        """Search a single named provider."""
        provider = self.registry.get(provider_id)
        if provider is None:
            return ProviderSearchResult(
                provider=provider_id,
                error="Unknown provider",
                error_code="provider_error",
                page=params.page,
            )
        return self._search_one(provider, params)

    def _search_one(self, provider: Any, params: ProviderSearchParams) -> ProviderSearchResult:
        key = params_cache_key(provider.id, params) if self.use_cache else ""
        if key:
            cached = get_cached_response(key, ttl_seconds=self.cache_ttl_seconds)
            if cached is not None:
                from dreamforge_assets import DreamForgeAsset

                assets = [DreamForgeAsset.from_dict(a) for a in cached.get("assets", [])]
                result = ProviderSearchResult(
                    provider=provider.id,
                    assets=assets,
                    error="",
                    error_code="",
                    from_cache=True,
                    total=int(cached.get("total") or 0),
                    page=params.page,
                    next_cursor=str(cached.get("next_cursor") or ""),
                )
                return result

        result = provider.search(params)
        if self.use_cache and result.ok:
            with self._lock:
                put_cached_response(key, result.to_dict(), ttl_seconds=self.cache_ttl_seconds)
        return result

    def _selected_providers(self, kind: str, provider_ids: list[str] | None) -> list[Any]:
        if provider_ids:
            return [p for pid in provider_ids if (p := self.registry.get(pid))]
        return self.registry.providers_for(kind)

    def _assemble_response(self, results: list[ProviderSearchResult], params: ProviderSearchParams) -> dict[str, Any]:
        """Merge per-provider results, dedupe by SHA256, and rank."""
        local_registry = self.asset_registry
        owns_registry = local_registry is None
        if local_registry is None:
            from dreamforge_asset_registry import AssetRegistry

            local_registry = AssetRegistry()
        all_assets: list[dict[str, Any]] = []
        seen_sha: dict[str, str] = {}
        ok_count = 0
        error_count = 0

        from dreamforge_capability_registry import SUPPORTED_ARCHITECTURES
        from dreamforge_compute_profile import (
            assess_asset_device_compatibility,
            detect_compute_profile,
        )

        compute = detect_compute_profile("auto")
        query_text = (params.query or "").strip()

        try:
            for result in results:
                if result.ok:
                    ok_count += 1
                else:
                    error_count += 1
                for idx, asset in enumerate(result.assets):
                    asset_dict = asset.to_dict()
                    self._mark_installed(asset_dict, local_registry)
                    sha = asset.all_sha256 or None
                    duplicate_provider = ""
                    if sha:
                        first_sha = next(iter(sha))
                        if first_sha in seen_sha:
                            duplicate_provider = seen_sha[first_sha]
                        else:
                            seen_sha[first_sha] = result.provider
                    asset_dict["deduplicated_from"] = duplicate_provider
                    asset_dict["compatibility"] = assess_asset_device_compatibility(
                        asset, compute, SUPPORTED_ARCHITECTURES
                    )
                    asset_dict["_relevance"] = _asset_query_relevance(asset_dict, query_text)
                    asset_dict["_provider_rank"] = idx
                    all_assets.append(asset_dict)
        finally:
            if owns_registry:
                local_registry.close()

        if query_text:
            relevant = [a for a in all_assets if int(a.get("_relevance") or 0) > 0]
            if relevant:
                all_assets = relevant
            all_assets.sort(
                key=lambda a: (
                    -int(a.get("_relevance") or 0),
                    int(a.get("_provider_rank") or 0),
                    bool(a.get("is_local")),
                )
            )
        else:
            all_assets.sort(
                key=lambda a: (
                    int(a.get("_provider_rank") or 0),
                    bool(a.get("is_local")),
                    (a.get("name") or "").lower(),
                )
            )

        for asset_dict in all_assets:
            asset_dict.pop("_relevance", None)
            asset_dict.pop("_provider_rank", None)

        return {
            "ok": True,
            "query": params.query,
            "kind": params.kind,
            "page": params.page,
            "limit": params.limit,
            "count": len(all_assets),
            "assets": all_assets,
            "providers": [r.to_dict() for r in results],
            "provider_ok": ok_count,
            "provider_errors": error_count,
            "compute_profile": compute.to_dict(),
        }

    @staticmethod
    def _mark_installed(asset: dict[str, Any], asset_registry: Any) -> None:
        """Reconcile provider results with the SHA256-backed local registry."""
        installed = False
        for version in asset.get("versions") or []:
            for file_ in version.get("files") or []:
                record = asset_registry.file_by_sha256(str(file_.get("sha256") or ""))
                local_path = str((record or {}).get("local_path") or "")
                if local_path and Path(local_path).is_file():
                    file_["local_path"] = local_path
                    installed = True
        asset["is_local"] = installed
