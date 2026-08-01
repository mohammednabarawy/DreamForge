"""HuggingFace search provider for DreamForge Discover.

Normalizes HuggingFace's ``/api/models`` response into ``DreamForgeAsset``
objects. Repos may contain multiple files (``siblings``); the provider surfaces
model-weight files as downloadable candidates and marks gated/private repos so
the renderer can fail with a clear auth/access message (plan §12).

HuggingFace API:
- ``GET /api/models?search=..&limit=..&page=..&filter=..``
"""

from __future__ import annotations

import os
from typing import Any, Mapping

from dreamforge_assets import (
    AssetFile,
    AssetKind,
    AssetVersion,
    DreamForgeAsset,
    Provenance,
    detect_architecture,
    detect_variant,
)
from dreamforge_provider_base import (
    DiscoveryProvider,
    ProviderSearchParams,
    ProviderSearchResult,
    http_get_json,
)

API_BASE = "https://huggingface.co/api/models"

# File extensions that are plausible downloadable model weights.
_WEIGHT_EXTENSIONS = {".safetensors", ".ckpt", ".pt", ".pth", ".bin", ".gguf", ".patch"}
# Extensions that are always config/aux and never treated as a model file.
_SKIP_EXTENSIONS = {".json", ".txt", ".md", ".py", ".yaml", ".yml", ".gitattributes", ".gitignore"}


def _is_weight_file(filename: str) -> bool:
    lower = filename.lower()
    for ext in _WEIGHT_EXTENSIONS:
        if lower.endswith(ext):
            return True
    return False


def _repo_id_from_model(raw: Mapping[str, Any]) -> str:
    return str(raw.get("id") or "")


def _repo_url(repo_id: str) -> str:
    return f"https://huggingface.co/{repo_id}" if repo_id else ""


def _gated_state(raw: Mapping[str, Any]) -> str:
    gated = raw.get("gated")
    if gated is True:
        return "gated"
    if isinstance(gated, str) and gated not in ("auto", "False", "false"):
        return "gated"
    if raw.get("private") is True:
        return "private"
    return ""


def normalize_hf_models(items: list[Mapping[str, Any]] | None) -> list[DreamForgeAsset]:
    """Convert HuggingFace model items into normalized DreamForge assets."""
    assets: list[DreamForgeAsset] = []
    for raw in items or []:
        asset = _normalize_one(raw)
        if asset:
            assets.append(asset)
    return assets


def _kind_from_tags(tags: list[str]) -> str:
    tag_str = " ".join(t.lower() for t in tags)
    if "loras" in tag_str or "text-embeddings" in tag_str and "embedding" in tag_str:
        return "lora"
    if "controlnet" in tag_str:
        return "controlnet"
    if "text-to-image" in tag_str:
        return "checkpoint"
    return "checkpoint"


def _normalize_one(raw: Mapping[str, Any]) -> DreamForgeAsset | None:
    repo_id = _repo_id_from_model(raw)
    if not repo_id:
        return None

    name = repo_id.split("/")[-1]
    author = repo_id.split("/")[0] if "/" in repo_id else ""
    gated = _gated_state(raw)
    tags = [str(t) for t in (raw.get("tags") or []) if t]

    siblings = raw.get("siblings") or []
    files: list[AssetFile] = []
    for sibling in siblings:
        filename = str(sibling.get("rfilename") or "")
        if not filename or not _is_weight_file(filename):
            continue
        if any(part.startswith(".") for part in filename.split("/")):
            continue
        variant = detect_variant(filename)
        sha256 = ""
        files.append(
            AssetFile(
                filename=os.path.basename(filename),
                sha256=sha256,
                size_bytes=0,
                variant=variant,
                format=filename.rsplit(".", 1)[-1].lower(),
                download_url=f"https://huggingface.co/{repo_id}/resolve/main/{filename}",
            )
        )

    if not files:
        return None

    kind_value = _kind_from_tags(tags)
    kind = AssetKind.from_string(kind_value)
    architecture = detect_architecture(name)

    version = AssetVersion(
        id="v1",
        name=name,
        files=files,
        provider_version_id="main",
        base_model="",
        published_at=str(raw.get("lastModified") or ""),
    )

    pipeline = str(raw.get("pipeline_tag") or "")
    description = pipeline or ""
    if gated:
        description = f"{description} [gated]".strip()

    provenance = Provenance(
        provider="huggingface",
        source_url=_repo_url(repo_id),
        provider_asset_id=repo_id,
        provider_version_id="main",
        author=author,
        license=str(raw.get("library_name") or ""),
    )

    return DreamForgeAsset(
        id=f"huggingface:{repo_id}",
        name=name,
        kind=kind,
        architecture=architecture,
        versions=[version],
        provenance=provenance,
        tags=tags[:12],
        description=description[:400],
        version_id="v1",
    )


class HuggingFaceProvider(DiscoveryProvider):
    """HuggingFace search provider."""

    id = "huggingface"
    display_name = "Hugging Face"
    supported_kinds = (
        "checkpoint",
        "lora",
        "controlnet",
        "vae",
        "text_encoder",
        "upscaler",
    )
    requires_credential = False
    timeout_seconds = 25

    def search(self, params: ProviderSearchParams) -> ProviderSearchResult:
        result = ProviderSearchResult(provider=self.id, page=params.page)
        url = self._build_url(params)
        try:
            data = http_get_json(url, timeout=self.timeout_seconds)
        except Exception as exc:
            from dreamforge_provider_base import ProviderError, classify_http_error

            if isinstance(exc, ProviderError):
                result.error_code = exc.code
                result.error = exc.message
            else:
                classified = classify_http_error(exc)
                result.error_code = classified.code
                result.error = classified.message
            return result

        items = data if isinstance(data, list) else data.get("models") or []
        result.total = len(items)
        result.assets = normalize_hf_models(items)
        return result

    def _build_url(self, params: ProviderSearchParams) -> str:
        import urllib.parse

        query_args: list[tuple[str, str]] = []
        if params.query:
            query_args.append(("search", params.query))
        if params.kind and params.kind != "unknown":
            query_args.append(("filter", f"text-to-image:{params.kind}"))
        query_args.append(("limit", str(max(1, min(params.limit, 100)))))
        query_args.append(("page", str(max(1, params.page))))
        return f"{API_BASE}?{urllib.parse.urlencode(query_args)}"
