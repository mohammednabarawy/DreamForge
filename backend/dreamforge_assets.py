"""Asset domain model for DreamForge Discover & Library.

Defines the normalized model of external and local assets:

- ``AssetKind``        : physical category (checkpoint, lora, vae, ...)
- ``Provenance``       : where an asset came from (provider, ids, license, sha256)
- ``AssetFile``        : one physical file (variant/precision) on disk
- ``AssetVersion``     : a logical version of an asset (one or more files)
- ``DreamForgeAsset``  : the normalized logical asset (the unit Discover returns)

Identity rule (plan §31.14): SHA256 identifies physical files; a logical asset is
identified by provider + provider asset id + provider version id. Filename alone is
never treated as identity.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Optional


class AssetKind(str, Enum):
    CHECKPOINT = "checkpoint"
    LORA = "lora"
    VAE = "vae"
    CONTROLNET = "controlnet"
    UPSCALER = "upscaler"
    TEXT_ENCODER = "text_encoder"
    CLIP = "clip"
    CLIP_VISION = "clip_vision"
    EMBEDDING = "embedding"
    INPAINT = "inpaint"
    IPADAPTER = "ipadapter"
    STYLE = "style"
    WORKFLOW = "workflow"
    UNKNOWN = "unknown"

    @classmethod
    def from_string(cls, value: str | None) -> "AssetKind":
        if not value:
            return cls.UNKNOWN
        key = value.strip().lower().replace("-", "_")
        for member in cls:
            if member.value == key or member.name == key:
                return member
        # Fallback for plural category names like "checkpoints", "loras"
        kind_from_cat = CATEGORY_TO_KIND.get(key)
        if kind_from_cat:
            return kind_from_cat
        return cls.UNKNOWN


# Map existing Comfy folder names / downloader categories to AssetKind.
CATEGORY_TO_KIND: dict[str, AssetKind] = {
    "checkpoints": AssetKind.CHECKPOINT,
    "diffusion_models": AssetKind.CHECKPOINT,
    "unet": AssetKind.CHECKPOINT,
    "loras": AssetKind.LORA,
    "vae": AssetKind.VAE,
    "controlnet": AssetKind.CONTROLNET,
    "upscale_models": AssetKind.UPSCALER,
    "clip": AssetKind.CLIP,
    "text_encoders": AssetKind.TEXT_ENCODER,
    "clip_vision": AssetKind.CLIP_VISION,
    "embeddings": AssetKind.EMBEDDING,
    "inpaint": AssetKind.INPAINT,
    "ipadapter": AssetKind.IPADAPTER,
    "style_models": AssetKind.STYLE,
}


def kind_for_category(category: str | None) -> AssetKind:
    if not category:
        return AssetKind.UNKNOWN
    return CATEGORY_TO_KIND.get(category.strip().lower(), AssetKind.UNKNOWN)


def category_for_kind(kind: AssetKind) -> str:
    """Map an AssetKind back to the downloader category folder name."""
    return {
        AssetKind.CHECKPOINT: "checkpoints",
        AssetKind.LORA: "loras",
        AssetKind.VAE: "vae",
        AssetKind.CONTROLNET: "controlnet",
        AssetKind.UPSCALER: "upscale_models",
        AssetKind.CLIP: "clip",
        AssetKind.TEXT_ENCODER: "text_encoders",
        AssetKind.CLIP_VISION: "clip_vision",
        AssetKind.EMBEDDING: "embeddings",
        AssetKind.INPAINT: "inpaint",
        AssetKind.IPADAPTER: "ipadapter",
        AssetKind.STYLE: "style_models",
        AssetKind.WORKFLOW: "workflows",
        AssetKind.UNKNOWN: "checkpoints",
    }.get(kind, "checkpoints")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class Provenance:
    """Origin record for a downloaded/imported item (plan §26)."""

    provider: str
    source_url: str = ""
    provider_asset_id: str = ""
    provider_version_id: str = ""
    author: str = ""
    license: str = ""
    downloaded_at: str = ""
    sha256: str = ""

    @property
    def license_label(self) -> str:
        """Never infer commercial permission from an absent license field."""
        license_value = (self.license or "").strip()
        if not license_value:
            return "Unknown — review source before commercial use"
        return license_value

    def to_dict(self) -> dict[str, str]:
        return {
            "provider": self.provider,
            "source_url": self.source_url,
            "provider_asset_id": self.provider_asset_id,
            "provider_version_id": self.provider_version_id,
            "author": self.author,
            "license": self.license,
            "downloaded_at": self.downloaded_at,
            "sha256": self.sha256,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "Provenance":
        data = data or {}
        return cls(
            provider=str(data.get("provider") or ""),
            source_url=str(data.get("source_url") or ""),
            provider_asset_id=str(data.get("provider_asset_id") or ""),
            provider_version_id=str(data.get("provider_version_id") or ""),
            author=str(data.get("author") or ""),
            license=str(data.get("license") or ""),
            downloaded_at=str(data.get("downloaded_at") or ""),
            sha256=str(data.get("sha256") or ""),
        )

    @classmethod
    def local(cls) -> "Provenance":
        return cls(provider="local", downloaded_at=_now_iso())


_VARIANT_HINTS: tuple[tuple[str, str], ...] = (
    ("fp8_scaled", "fp8_scaled"),
    ("fp8", "fp8"),
    ("fp16", "fp16"),
    ("bf16", "bf16"),
    ("q4_k_m", "q4_k_m"),
    ("q4_k_s", "q4_k_s"),
    ("q3_k_m", "q3_k_m"),
    ("q2_k", "q2_k"),
    ("gguf", "gguf"),
    ("mxfp8", "mxfp8"),
)


def detect_variant(filename: str) -> str:
    """Best-effort precision/format variant from a filename (plan §4 file variants)."""
    lower = (filename or "").lower()
    for hint, label in _VARIANT_HINTS:
        if hint in lower:
            return label
    return ""


def detect_architecture(filename: str, model_dict: Mapping[str, Any] | None = None) -> str:
    """Best-effort architecture/family detection for an asset file.

    Uses explicit family metadata first, then filename heuristics (plan §4:
    'unsupported architecture is clearly marked before download').
    """
    if model_dict:
        family = model_dict.get("family")
        if family:
            return str(family).lower()
        engine_name = model_dict.get("engine_name") or model_dict.get("name") or ""
        if engine_name:
            filename = str(engine_name)
    lower = (filename or "").lower()
    hints: tuple[tuple[str, str], ...] = (
        ("flux1-fill", "flux_fill"),
        ("flux-fill", "flux_fill"),
        ("flux1-kontext", "flux_kontext"),
        ("flux-kontext", "flux_kontext"),
        ("flux1-dev", "flux"),
        ("flux1-schnell", "flux"),
        ("flux.1", "flux"),
        ("qwen-image-edit", "qwen_image_edit"),
        ("qwen-image", "qwen_image"),
        ("hidream-o1", "hidream_o1"),
        ("hidream", "hidream"),
        ("ideogram4", "ideogram4"),
        ("z-image", "z_image"),
        ("krea2", "krea2"),
        ("sd3", "sd3"),
        ("sd2", "sd2"),
        ("sd1.5", "sd15"),
        ("sd15", "sd15"),
        ("sdxl", "sdxl"),
        ("xl", "sdxl"),
        ("juggernaut", "sdxl"),
        ("dreamshaper", "sd15"),
    )
    for hint, family in hints:
        if hint in lower:
            return family
    return ""


@dataclass(frozen=True)
class AssetFile:
    """One physical file belonging to an asset version."""

    filename: str
    sha256: str = ""
    size_bytes: int = 0
    variant: str = ""
    format: str = ""
    download_url: str = ""
    local_path: str = ""

    @property
    def has_identity(self) -> bool:
        return bool(self.sha256)

    def to_dict(self) -> dict[str, Any]:
        return {
            "filename": self.filename,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "variant": self.variant,
            "format": self.format,
            "download_url": self.download_url,
            "local_path": self.local_path,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "AssetFile":
        data = data or {}
        return cls(
            filename=str(data.get("filename") or ""),
            sha256=str(data.get("sha256") or ""),
            size_bytes=int(data.get("size_bytes") or 0),
            variant=str(data.get("variant") or ""),
            format=str(data.get("format") or ""),
            download_url=str(data.get("download_url") or ""),
            local_path=str(data.get("local_path") or ""),
        )


@dataclass
class AssetVersion:
    """A logical version of an asset (one or more physical files)."""

    id: str
    name: str = ""
    files: list[AssetFile] = field(default_factory=list)
    provider_version_id: str = ""
    base_model: str = ""
    published_at: str = ""
    notes: str = ""
    thumbnail_url: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "files": [f.to_dict() for f in self.files],
            "provider_version_id": self.provider_version_id,
            "base_model": self.base_model,
            "published_at": self.published_at,
            "notes": self.notes,
            "thumbnail_url": self.thumbnail_url,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "AssetVersion":
        data = data or {}
        files = [AssetFile.from_dict(f) for f in (data.get("files") or [])]
        return cls(
            id=str(data.get("id") or ""),
            name=str(data.get("name") or ""),
            files=files,
            provider_version_id=str(data.get("provider_version_id") or ""),
            base_model=str(data.get("base_model") or ""),
            published_at=str(data.get("published_at") or ""),
            notes=str(data.get("notes") or ""),
            thumbnail_url=str(data.get("thumbnail_url") or ""),
        )


@dataclass
class DreamForgeAsset:
    """The normalized logical asset returned by providers and stored in the registry."""

    id: str = ""
    name: str = ""
    kind: AssetKind = AssetKind.UNKNOWN
    architecture: str = ""
    versions: list[AssetVersion] = field(default_factory=list)
    provenance: Provenance = field(default_factory=Provenance.local)
    tags: list[str] = field(default_factory=list)
    description: str = ""
    version_id: str = ""  # active version id (mirrors provider_version_id)
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = _now_iso()
        if self.version_id and not any(
            v.id == self.version_id for v in self.versions
        ):
            self.version_id = ""

    @property
    def active_version(self) -> Optional[AssetVersion]:
        if not self.versions:
            return None
        if self.version_id:
            for version in self.versions:
                if version.id == self.version_id:
                    return version
        return self.versions[0]

    @property
    def primary_file(self) -> Optional[AssetFile]:
        version = self.active_version
        if not version or not version.files:
            return None
        # Prefer a file with a known SHA256; otherwise the first entry.
        for file_ in version.files:
            if file_.sha256:
                return file_
        return version.files[0]

    @property
    def is_local(self) -> bool:
        version = self.active_version
        if not version or not version.files:
            return False
        return any(bool(f.local_path) for f in version.files)

    @property
    def all_sha256(self) -> set[str]:
        return {
            f.sha256
            for version in self.versions
            for f in version.files
            if f.sha256
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind.value,
            "architecture": self.architecture,
            "versions": [v.to_dict() for v in self.versions],
            "provenance": self.provenance.to_dict(),
            "tags": list(self.tags),
            "description": self.description,
            "version_id": self.version_id,
            "created_at": self.created_at,
            "is_local": self.is_local,
            "license_label": self.provenance.license_label,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "DreamForgeAsset":
        data = data or {}
        versions = [AssetVersion.from_dict(v) for v in (data.get("versions") or [])]
        return cls(
            id=str(data.get("id") or ""),
            name=str(data.get("name") or ""),
            kind=AssetKind.from_string(data.get("kind")),
            architecture=str(data.get("architecture") or ""),
            versions=versions,
            provenance=Provenance.from_dict(data.get("provenance")),
            tags=[str(t) for t in (data.get("tags") or [])],
            description=str(data.get("description") or ""),
            version_id=str(data.get("version_id") or ""),
            created_at=str(data.get("created_at") or ""),
        )


def asset_id_from_provenance(provenance: Provenance) -> str:
    """Deterministic logical-asset id from provider provenance."""
    if provenance.provider and provenance.provider_asset_id:
        return f"{provenance.provider}:{provenance.provider_asset_id}"
    if provenance.provider and provenance.source_url:
        return f"{provenance.provider}:{_slug(provenance.source_url)}"
    return ""


def _slug(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", value).strip("_")[:120]
