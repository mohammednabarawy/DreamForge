"""Secure provider credentials for DreamForge Discover & Library.

Secrets live only in the existing app config file (``ui.civitai_api_key``) and
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

    return load_app_config()


def _write_app_config(config: dict[str, Any]) -> None:
    from dreamforge_app_config import save_app_config

    save_app_config(config)


def get_provider_credential(provider: str) -> str:
    """Return the stored credential for a provider (raw secret, backend only)."""
    provider = (provider or "").lower()
    config = _read_app_config()
    if provider == "civitai":
        return str(config.get("ui", {}).get("civitai_api_key") or "")
    return ""


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
    if secret:
        ui["civitai_api_key"] = secret
    else:
        ui.pop("civitai_api_key", None)
    _write_app_config(config)
    return provider_credential_status(config)


def provider_credential_status(config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Redacted status — never exposes the secret itself."""
    config = config or _read_app_config()
    ui = config.get("ui", {}) or {}
    civitai_key = str(ui.get("civitai_api_key") or "")
    status: dict[str, Any] = {"civitai": {"configured": bool(civitai_key), "tail": ""}}
    if civitai_key:
        status["civitai"]["tail"] = civitai_key[-4:] if len(civitai_key) >= 4 else civitai_key
    return {"ok": True, "status": status}


def credential_redacted_status(config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Alias returning just the status dict (used by bridge handlers)."""
    result = provider_credential_status(config)
    return result.get("status", {})
