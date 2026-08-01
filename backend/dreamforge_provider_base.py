"""Provider abstraction for DreamForge Discover & Library.

Defines the search contract every provider implements, the result envelope
(which carries per-provider errors so one failing provider never blanks the
Discover screen), and a shared JSON-over-HTTPS helper.

Design (plan §11.7 / §12):
- ``ProviderSearchParams``  : normalized search input
- ``ProviderSearchResult``  : normalized results + per-provider status
- ``DiscoveryProvider``     : abstract base every provider implements
- ``http_get_json``         : urllib wrapper with timeout + error classification
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Mapping

from dreamforge_assets import DreamForgeAsset

DEFAULT_TIMEOUT_SECONDS = 20
USER_AGENT = "DreamForge-Discover/1.0"

# Error codes surfaced to the renderer (plan §12: gated/auth failures must be
# clearly distinguished from generic failures).
ERR_NETWORK = "network_error"
ERR_TIMEOUT = "timeout"
ERR_AUTH = "auth_required"
ERR_ACCESS = "access_denied"
ERR_RATE_LIMIT = "rate_limited"
ERR_NOT_FOUND = "not_found"
ERR_PROVIDER = "provider_error"


class ProviderError(Exception):
    """Raised by providers for a classified, recoverable failure."""

    def __init__(self, code: str, message: str, status: int = 0) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "status": self.status}


def classify_http_error(exc: Exception) -> ProviderError:
    """Map an exception to a ProviderError with a renderer-friendly code."""
    if isinstance(exc, urllib.error.HTTPError):
        status = exc.code
        if status == 401:
            return ProviderError(ERR_AUTH, "Authentication required — check provider credentials", status)
        if status in (403, 404):
            if status == 403:
                return ProviderError(ERR_ACCESS, "Access denied — this model may be gated", status)
            return ProviderError(ERR_NOT_FOUND, "Not found", status)
        if status == 429:
            return ProviderError(ERR_RATE_LIMIT, "Rate limited — try again shortly", status)
        return ProviderError(ERR_PROVIDER, f"Provider HTTP {status}", status)
    if isinstance(exc, urllib.error.URLError):
        reason = str(exc.reason or "")
        if "timed out" in reason.lower() or "timeout" in reason.lower():
            return ProviderError(ERR_TIMEOUT, "Provider request timed out")
        return ProviderError(ERR_NETWORK, f"Provider unreachable: {reason}")
    if isinstance(exc, TimeoutError):
        return ProviderError(ERR_TIMEOUT, "Provider request timed out")
    return ProviderError(ERR_PROVIDER, str(exc))


def http_get_json(
    url: str,
    headers: Mapping[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> Any:
    """GET a URL and parse JSON, raising classified ProviderError on failure."""
    req_headers = {"User-Agent": USER_AGENT}
    if headers:
        req_headers.update({k: v for k, v in headers.items() if v})
    try:
        req = urllib.request.Request(url, headers=req_headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            if not body:
                raise ProviderError(ERR_PROVIDER, "Empty response from provider")
            return json.loads(body.decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise classify_http_error(exc) from exc


@dataclass(frozen=True)
class SearchFilters:
    """Filters applied across providers (safety + curation, plan §11.7)."""

    nsfw: bool = False
    min_base_model: str = ""
    max_base_model: str = ""
    sort: str = "relevance"

    def to_cache_key(self) -> str:
        return json.dumps(
            [self.nsfw, self.min_base_model, self.max_base_model, self.sort], sort_keys=True
        )


@dataclass(frozen=True)
class ProviderSearchParams:
    """Normalized search input shared by every provider."""

    query: str = ""
    kind: str = ""  # AssetKind value (checkpoint, lora, ...)
    limit: int = 20
    page: int = 1
    filters: SearchFilters = field(default_factory=SearchFilters)


@dataclass
class ProviderSearchResult:
    """Envelope returned by a single provider (plan: partial results on failure)."""

    provider: str
    assets: list[DreamForgeAsset] = field(default_factory=list)
    error: str = ""
    error_code: str = ""
    from_cache: bool = False
    total: int = 0
    page: int = 1

    @property
    def ok(self) -> bool:
        return not self.error_code

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "assets": [a.to_dict() for a in self.assets],
            "error": self.error,
            "error_code": self.error_code,
            "from_cache": self.from_cache,
            "total": self.total,
            "page": self.page,
            "ok": self.ok,
        }


class DiscoveryProvider:
    """Abstract base for a search provider (Civitai, HuggingFace, ...)."""

    id: str = ""
    display_name: str = ""
    # AssetKind values this provider can search.
    supported_kinds: tuple[str, ...] = ()
    # Whether this provider is reachable by default (network services are).
    requires_credential: bool = False
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS

    def search(self, params: ProviderSearchParams) -> ProviderSearchResult:
        """Search this provider. Subclasses must override."""
        raise NotImplementedError

    def supports_kind(self, kind: str) -> bool:
        if not kind:
            return True
        return kind in self.supported_kinds

    def _credential(self) -> str:
        from dreamforge_credentials import get_provider_credential

        return get_provider_credential(self.id)

    def info(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "display_name": self.display_name,
            "supported_kinds": list(self.supported_kinds),
            "requires_credential": self.requires_credential,
        }
