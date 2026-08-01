"""Tests for dreamforge_discovery_service — parallel search, failure isolation, dedupe."""

import pytest

from dreamforge_discovery_cache import invalidate
from dreamforge_discovery_service import DiscoveryService
from dreamforge_provider_base import (
    DiscoveryProvider,
    ProviderSearchParams,
    ProviderSearchResult,
)
from dreamforge_provider_registry import ProviderRegistry


class FakeProvider(DiscoveryProvider):
    def __init__(self, provider_id, assets=None, error_code="", error_msg=""):
        self.id = provider_id
        self.display_name = provider_id
        self.supported_kinds = ("checkpoint", "lora")
        self._assets = assets or []
        self._error_code = error_code
        self._error_msg = error_msg
        self.call_count = 0

    def search(self, params):
        self.call_count += 1
        return ProviderSearchResult(
            provider=self.id,
            assets=self._assets,
            error=self._error_msg,
            error_code=self._error_code,
            page=params.page,
        )


def _make_asset(asset_id, sha="", name=""):
    from dreamforge_assets import AssetFile, AssetVersion, DreamForgeAsset, Provenance

    file_obj = AssetFile(filename="m.safetensors", sha256=sha)
    version = AssetVersion(id="v1", name="v1", files=[file_obj])
    return DreamForgeAsset(
        id=asset_id,
        name=name or asset_id,
        versions=[version],
        provenance=Provenance(provider="test", provider_asset_id=asset_id),
    )


@pytest.fixture(autouse=True)
def clean_cache():
    invalidate()
    yield
    invalidate()


class TestDiscoveryServiceSearch:
    def test_search_runs_all_providers(self):
        reg = ProviderRegistry()
        reg.register(FakeProvider("a"))
        reg.register(FakeProvider("b"))
        svc = DiscoveryService(registry=reg, use_cache=False)
        result = svc.search(query="test")
        assert result["ok"] is True
        assert result["provider_ok"] == 2
        assert result["provider_errors"] == 0

    def test_partial_results_on_failure(self):
        reg = ProviderRegistry()
        reg.register(FakeProvider("good"))
        reg.register(FakeProvider("bad", error_code="timeout", error_msg="Timed out"))
        svc = DiscoveryService(registry=reg, use_cache=False)
        result = svc.search(query="test")
        assert result["provider_ok"] == 1
        assert result["provider_errors"] == 1
        providers = {p["provider"]: p for p in result["providers"]}
        assert providers["good"]["ok"] is True
        assert providers["bad"]["ok"] is False
        assert providers["bad"]["error_code"] == "timeout"

    def test_dedupe_by_sha256(self):
        reg = ProviderRegistry()
        reg.register(FakeProvider("a", assets=[_make_asset("a1", sha="shared_sha")]))
        reg.register(FakeProvider("b", assets=[_make_asset("b1", sha="shared_sha")]))
        svc = DiscoveryService(registry=reg, use_cache=False)
        result = svc.search(query="test")
        assert result["count"] == 2
        deduped = [a for a in result["assets"] if a.get("deduplicated_from")]
        assert len(deduped) == 1
        assert deduped[0]["deduplicated_from"] in ("a", "b")

    def test_provider_ids_filter(self):
        reg = ProviderRegistry()
        reg.register(FakeProvider("a"))
        reg.register(FakeProvider("b"))
        svc = DiscoveryService(registry=reg, use_cache=False)
        result = svc.search(query="test", provider_ids=["a"])
        assert result["provider_ok"] == 1

    def test_kind_filter(self):
        reg = ProviderRegistry()
        reg.register(FakeProvider("a"))
        svc = DiscoveryService(registry=reg, use_cache=False)
        result = svc.search(query="test", kind="checkpoint")
        assert result["ok"] is True

    def test_search_provider_single(self):
        reg = ProviderRegistry()
        reg.register(FakeProvider("a", assets=[_make_asset("x1")]))
        svc = DiscoveryService(registry=reg, use_cache=False)
        result = svc.search_provider("a", ProviderSearchParams(query="test"))
        assert result.provider == "a"
        assert len(result.assets) == 1

    def test_search_provider_unknown(self):
        reg = ProviderRegistry()
        svc = DiscoveryService(registry=reg, use_cache=False)
        result = svc.search_provider("missing", ProviderSearchParams())
        assert result.error_code == "provider_error"

    def test_cache_hit(self):
        reg = ProviderRegistry()
        provider = FakeProvider("a", assets=[_make_asset("x1")])
        reg.register(provider)
        svc = DiscoveryService(registry=reg, use_cache=True)
        result1 = svc.search(query="test")
        assert result1["provider_ok"] == 1
        result2 = svc.search(query="test")
        assert result2["provider_ok"] == 1
        providers = result2["providers"]
        assert providers[0]["from_cache"] is True

    def test_disabled_provider_excluded(self):
        reg = ProviderRegistry()
        reg.register(FakeProvider("a"))
        reg.set_enabled("a", False)
        svc = DiscoveryService(registry=reg, use_cache=False)
        result = svc.search(query="test")
        assert result["provider_ok"] == 0
