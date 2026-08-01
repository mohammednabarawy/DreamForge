"""Civitai search provider for DreamForge Discover.

Normalizes Civitai's ``/api/v1/models`` response into ``DreamForgeAsset``
objects. Only version files of type ``Model``/``Pruned Model`` are surfaced as
downloadable files (VAE/TextEncoder "file" rows that belong to a checkpoint
version are still exposed because some checkpoints bundle them, but metadata
rows like "Preview" are skipped).

Civitai API v1:
- ``GET /api/v1/models?query=..&types=Checkpoint,LoRA&limit=..&page=..``
"""

from __future__ import annotations

import re
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

API_BASE = "https://civitai.com/api/v1/models"

# Civitai "type" string -> AssetKind value.
_CIVITAI_KIND_MAP: dict[str, str] = {
    "Checkpoint": "checkpoint",
    "Checkpoints": "checkpoint",
    "LoRA": "lora",
    "Loras": "lora",
    "TextualInversion": "embedding",
    "Hypernetwork": "embedding",
    "Controlnet": "controlnet",
    "ControlNet": "controlnet",
    "Aesthetic": "style",
    "Wildcards": "style",
    "Workflows": "workflow",
    "Upscaler": "upscaler",
    "MotionModule": "adapter",
    "Poses": "adapter",
    "VAE": "vae",
    "CLIP": "clip",
    "Other": "unknown",
}

# File metadata rows that are not actual downloadable model files.
_SKIP_FILE_TYPES = {"Preview", "Training Data", "Negative"}


def civitai_kind_to_asset_kind(type_value: str | None) -> str:
    if not type_value:
        return "unknown"
    return _CIVITAI_KIND_MAP.get(type_value.strip(), "unknown")


def _base_model(version: Mapping[str, Any]) -> str:
    return str(version.get("baseModel") or "")


def _format_from_meta(meta: Mapping[str, Any]) -> str:
    fmt = str(meta.get("format") or "")
    if fmt.lower() in {"safetensor", "safetensors"}:
        return "safetensors"
    if fmt:
        return fmt.lower()
    return ""


def _parse_size_kb(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _asset_url(model: Mapping[str, Any]) -> str:
    model_id = model.get("id")
    return f"https://civitai.com/models/{model_id}" if model_id else ""


def normalize_civitai_models(items: list[Mapping[str, Any]] | None) -> list[DreamForgeAsset]:
    """Convert Civitai model items into normalized DreamForge assets."""
    assets: list[DreamForgeAsset] = []
    for raw in items or []:
        asset = _normalize_one(raw)
        if asset:
            assets.append(asset)
    return assets


def _version_thumbnail(version: Mapping[str, Any]) -> str:
    """First non-nsfw (or fallback first) image URL for a version's card."""
    images = version.get("images") or []
    for img in images:
        if not img.get("nsfw"):
            url = str(img.get("url") or "")
            if url:
                return url
    for img in images:
        url = str(img.get("url") or "")
        if url:
            return url
    return ""


def _normalize_one(raw: Mapping[str, Any]) -> DreamForgeAsset | None:
    model_id = raw.get("id")
    name = str(raw.get("name") or "")
    if not model_id or not name:
        return None

    kind_value = civitai_kind_to_asset_kind(raw.get("type"))
    kind = AssetKind.from_string(kind_value)

    creator = raw.get("creator") or {}
    author = str(creator.get("username") or "")

    versions: list[AssetVersion] = []
    raw_versions = raw.get("modelVersions") or []
    active_version_id = ""

    for idx, version in enumerate(raw_versions):
        version_id = version.get("id")
        version_name = str(version.get("name") or "")
        published = str(version.get("publishedAt") or "")
        base_model = _base_model(version)

        files: list[AssetFile] = []
        for file_row in version.get("files") or []:
            file_type = str(file_row.get("type") or "Model")
            if file_type in _SKIP_FILE_TYPES:
                continue
            meta = file_row.get("metadata") or {}
            filename = str(file_row.get("name") or "")
            if not filename:
                continue
            hashes = file_row.get("hashes") or {}
            sha256 = str(hashes.get("SHA256") or "").lower()
            variant = detect_variant(filename)
            if not variant:
                variant = str(meta.get("fp") or "").lower()
            format_ = _format_from_meta(meta)
            size_kb = _parse_size_kb(file_row.get("sizeKB"))
            download_url = str(file_row.get("downloadUrl") or "")
            files.append(
                AssetFile(
                    filename=filename,
                    sha256=sha256,
                    size_bytes=size_kb * 1024,
                    variant=variant,
                    format=format_,
                    download_url=download_url,
                )
            )

        if not files:
            continue

        version_obj = AssetVersion(
            id=f"v{version_id}",
            name=version_name,
            files=files,
            provider_version_id=str(version_id),
            base_model=base_model,
            published_at=published,
            thumbnail_url=_version_thumbnail(version),
        )
        versions.append(version_obj)
        if idx == 0:
            active_version_id = version_obj.id

    if not versions:
        return None

    architecture = detect_architecture(name, {"family": ""})
    base_models = {v.base_model for v in versions}
    base_models.discard("")
    if not architecture and base_models:
        architecture = _arch_from_base_model(" ".join(sorted(base_models)))

    provenance = Provenance(
        provider="civitai",
        source_url=_asset_url(raw),
        provider_asset_id=str(model_id),
        provider_version_id=str(versions[0].provider_version_id),
        author=author,
        license="",
    )
    tags = [str(t) for t in (raw.get("tags") or []) if t]
    description = re.sub(r"<[^>]+>", "", str(raw.get("description") or "")).strip()

    return DreamForgeAsset(
        id=f"civitai:{model_id}",
        name=name,
        kind=kind,
        architecture=architecture,
        versions=versions,
        provenance=provenance,
        tags=tags[:12],
        description=description[:400],
        version_id=active_version_id,
    )


def _arch_from_base_model(base_model: str) -> str:
    lower = base_model.lower()
    for hint, family in (
        ("flux1", "flux"),
        ("flux.1", "flux"),
        ("sd3", "sd3"),
        ("sdxl", "sdxl"),
        ("sd 1.5", "sd15"),
        ("sd1.5", "sd15"),
        ("sd2", "sd2"),
        ("pony", "sdxl"),
    ):
        if hint in lower:
            return family
    return ""


class CivitaiProvider(DiscoveryProvider):
    """Civitai search provider (plan §13: Civitai is a first-class source)."""

    id = "civitai"
    display_name = "Civitai"
    supported_kinds = (
        "checkpoint",
        "lora",
        "vae",
        "controlnet",
        "embedding",
        "upscaler",
        "style",
        "workflow",
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

        items = data.get("items") or []
        metadata = data.get("metadata") or {}
        result.total = int(metadata.get("totalItems") or len(items))
        result.assets = normalize_civitai_models(items)
        return result

    def _build_url(self, params: ProviderSearchParams) -> str:
        import urllib.parse

        query_args: list[tuple[str, str]] = []
        if params.query:
            query_args.append(("query", params.query))
        if params.kind and params.kind != "unknown":
            types = self._civitai_types(params.kind)
            if types:
                query_args.append(("types", ",".join(types)))
        query_args.append(("limit", str(max(1, min(params.limit, 100)))))
        query_args.append(("page", str(max(1, params.page))))
        if not params.filters.nsfw:
            query_args.append(("nsfw", "false"))
        if params.filters.sort:
            sort_key = {"relevance": "Most Downloaded", "downloads": "Most Downloaded"}.get(
                params.filters.sort, params.filters.sort
            )
            query_args.append(("sort", sort_key))
        return f"{API_BASE}?{urllib.parse.urlencode(query_args)}"

    @staticmethod
    def _civitai_types(kind: str) -> list[str]:
        return {
            "checkpoint": ["Checkpoint"],
            "lora": ["LoRA"],
            "vae": ["VAE"],
            "controlnet": ["Controlnet"],
            "embedding": ["TextualInversion"],
            "upscaler": ["Upscaler"],
            "style": ["Aesthetic"],
            "workflow": ["Workflows"],
        }.get(kind, [])
