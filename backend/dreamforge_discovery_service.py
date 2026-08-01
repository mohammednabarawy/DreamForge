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

import threading
from dataclasses import replace
from pathlib import Path
from typing import Any

from dreamforge_discovery_cache import get_cached_response, params_cache_key, put_cached_response
from dreamforge_provider_base import ProviderSearchParams, ProviderSearchResult
from dreamforge_provider_registry import ProviderRegistry, default_provider_registry


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

        try:
            for result in results:
                if result.ok:
                    ok_count += 1
                else:
                    error_count += 1
                for asset in result.assets:
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
                    all_assets.append(asset_dict)
        finally:
            if owns_registry:
                local_registry.close()

        # Rank: installed assets (is_local) sort after remote; keep provider order stable.
        all_assets.sort(key=lambda a: (bool(a.get("is_local")), a.get("name") or ""))

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
