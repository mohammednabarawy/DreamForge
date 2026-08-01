"""Tests for dreamforge_provider_registry — registration, enable/disable, info."""

import pytest

from dreamforge_provider_base import DiscoveryProvider, ProviderSearchParams, ProviderSearchResult
from dreamforge_provider_registry import ProviderRegistry, default_provider_registry


class FakeProvider(DiscoveryProvider):
    id = "fake"
    display_name = "Fake"
    supported_kinds = ("checkpoint", "lora")

    def search(self, params):
        return ProviderSearchResult(provider=self.id)


class AnotherProvider(DiscoveryProvider):
    id = "another"
    display_name = "Another"
    supported_kinds = ("vae",)

    def search(self, params):
        return ProviderSearchResult(provider=self.id)


class TestProviderRegistry:
    def test_register_and_count(self):
        reg = ProviderRegistry()
        assert reg.count == 0
        reg.register(FakeProvider())
        assert reg.count == 1

    def test_register_duplicate_raises(self):
        reg = ProviderRegistry()
        reg.register(FakeProvider())
        with pytest.raises(ValueError):
            reg.register(FakeProvider())

    def test_register_empty_id_raises(self):
        class NoId(DiscoveryProvider):
            id = ""
            display_name = "NoId"
            supported_kinds = ()

            def search(self, params):
                return ProviderSearchResult(provider="")

        reg = ProviderRegistry()
        with pytest.raises(ValueError):
            reg.register(NoId())

    def test_get(self):
        reg = ProviderRegistry()
        reg.register(FakeProvider())
        assert reg.get("fake") is not None
        assert reg.get("missing") is None

    def test_unregister(self):
        reg = ProviderRegistry()
        reg.register(FakeProvider())
        reg.unregister("fake")
        assert reg.count == 0
        assert reg.get("fake") is None

    def test_set_enabled(self):
        reg = ProviderRegistry()
        reg.register(FakeProvider())
        assert len(reg.enabled_providers()) == 1
        reg.set_enabled("fake", False)
        assert len(reg.enabled_providers()) == 0
        reg.set_enabled("fake", True)
        assert len(reg.enabled_providers()) == 1

    def test_set_enabled_unknown_raises(self):
        reg = ProviderRegistry()
        with pytest.raises(KeyError):
            reg.set_enabled("missing", True)

    def test_providers_for_kind(self):
        reg = ProviderRegistry()
        reg.register(FakeProvider())
        reg.register(AnotherProvider())
        assert len(reg.providers_for("checkpoint")) == 1
        assert len(reg.providers_for("vae")) == 1
        assert len(reg.providers_for("")) == 2

    def test_ids(self):
        reg = ProviderRegistry()
        reg.register(FakeProvider())
        reg.register(AnotherProvider())
        assert set(reg.ids()) == {"fake", "another"}

    def test_info_shape(self):
        reg = ProviderRegistry()
        reg.register(FakeProvider())
        info = reg.info()
        assert info["ok"] is True
        assert len(info["providers"]) == 1
        p = info["providers"][0]
        assert p["id"] == "fake"
        assert p["enabled"] is True
        assert "credential_configured" in p


class TestDefaultRegistry:
    def test_default_has_civitai_and_huggingface(self):
        reg = default_provider_registry()
        ids = set(reg.ids())
        assert "civitai" in ids
        assert "huggingface" in ids

    def test_default_providers_for_checkpoint(self):
        reg = default_provider_registry()
        providers = reg.providers_for("checkpoint")
        assert len(providers) >= 1
