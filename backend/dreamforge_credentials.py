"""Secure provider credentials for DreamForge Discover & Library.

Secrets live only in the existing app config provider-key fields and
are read here on demand. They are never returned to the renderer — only a
redacted status (configured / tail). Provider tokens stay in backend memory
and are attached per-request by the provider implementations.
"""

from __future__ import annotations

from typing import Any

# Provider ids recognised by the credential store.
CREDENTIAL_PROVIDERS: tuple[str, ...] = ("civitai", "huggingface")


def _read_app_config() -> dict[str, Any]:
    from dreamforge_app_config import load_app_config

    return load_app_config(redacted=False)


def _write_app_config(config: dict[str, Any]) -> None:
    from dreamforge_app_config import save_app_config

    save_app_config(config, preserve_redacted_secrets=False)


def get_provider_credential(provider: str) -> str:
    """Return the stored credential for a provider (raw secret, backend only)."""
    provider = (provider or "").lower()
    config = _read_app_config()
    key = {"civitai": "civitai_api_key", "huggingface": "huggingface_api_key"}.get(provider)
    return str(config.get("ui", {}).get(key) or "") if key else ""


def set_provider_credential(provider: str, secret: str) -> dict[str, Any]:
    """Store a provider credential in the app config and return redacted status.

    An empty secret clears the credential.
    """
    provider = (provider or "").lower()
    if provider not in CREDENTIAL_PROVIDERS:
        return {"ok": False, "error": f"unsupported_provider: {provider}"}
    config = _read_app_config()
    ui = config.setdefault("ui", {})
    secret = str(secret or "").strip()
    key = {"civitai": "civitai_api_key", "huggingface": "huggingface_api_key"}[provider]
    ui[key] = secret
    _write_app_config(config)
    return provider_credential_status(config)


def provider_credential_status(config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Redacted status — never exposes the secret itself."""
    config = config or _read_app_config()
    ui = config.get("ui", {}) or {}
    status: dict[str, Any] = {}
    for provider, key in (("civitai", "civitai_api_key"), ("huggingface", "huggingface_api_key")):
        secret = str(ui.get(key) or "")
        status[provider] = {
            "configured": bool(secret),
            "tail": secret[-4:] if secret else "",
        }
    return {"ok": True, "status": status}


def credential_redacted_status(config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Alias returning just the status dict (used by bridge handlers)."""
    result = provider_credential_status(config)
    return result.get("status", {})
