"""Provider registry for DreamForge Discover & Library.

Registers all available search providers, answers which providers can satisfy
a given search, and exposes provider metadata (including credential status) to
the renderer without ever exposing secrets.
"""

from __future__ import annotations

from typing import Any

from dreamforge_provider_base import DiscoveryProvider, ProviderSearchParams


class ProviderRegistry:
    """Registry of DiscoveryProvider instances, keyed by provider id."""

    def __init__(self) -> None:
        self._providers: dict[str, DiscoveryProvider] = {}
        self._enabled: set[str] = set()

    def register(self, provider: DiscoveryProvider) -> None:
        """Register a provider. Id must be unique and non-empty."""
        if not provider.id:
            raise ValueError("Provider must have a non-empty id")
        if provider.id in self._providers:
            raise ValueError(f"Provider already registered: {provider.id}")
        self._providers[provider.id] = provider
        self._enabled.add(provider.id)

    def unregister(self, provider_id: str) -> None:
        self._providers.pop(provider_id, None)
        self._enabled.discard(provider_id)

    def set_enabled(self, provider_id: str, enabled: bool) -> None:
        if provider_id not in self._providers:
            raise KeyError(f"Unknown provider: {provider_id}")
        if enabled:
            self._enabled.add(provider_id)
        else:
            self._enabled.discard(provider_id)

    def get(self, provider_id: str) -> DiscoveryProvider | None:
        return self._providers.get(provider_id)

    def providers(self) -> list[DiscoveryProvider]:
        return list(self._providers.values())

    def enabled_providers(self) -> list[DiscoveryProvider]:
        return [self._providers[p] for p in self._enabled if p in self._providers]

    def providers_for(self, kind: str) -> list[DiscoveryProvider]:
        """Enabled providers that can search for the given asset kind."""
        return [p for p in self.enabled_providers() if p.supports_kind(kind)]

    def ids(self) -> list[str]:
        return list(self._providers.keys())

    def info(self) -> dict[str, Any]:
        from dreamforge_credentials import credential_redacted_status

        status = credential_redacted_status()
        return {
            "ok": True,
            "providers": [
                {
                    **p.info(),
                    "enabled": p.id in self._enabled,
                    "credential_configured": bool((status.get(p.id) or {}).get("configured")),
                }
                for p in self.providers()
            ],
        }

    @property
    def count(self) -> int:
        return len(self._providers)


def default_provider_registry() -> ProviderRegistry:
    """Build the standard registry with all bundled providers."""
    from dreamforge_civitai_provider import CivitaiProvider
    from dreamforge_huggingface_provider import HuggingFaceProvider

    registry = ProviderRegistry()
    registry.register(CivitaiProvider())
    registry.register(HuggingFaceProvider())
    return registry
