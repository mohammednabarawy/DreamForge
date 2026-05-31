"""Persistent cache for model inventory + gallery payloads (desktop startup)."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Callable

from _paths import BACKEND_ROOT

CACHE_DIR = BACKEND_ROOT / "cache" / "model_library"
MANIFEST_PATH = CACHE_DIR / "manifest.json"
INVENTORY_PATH = CACHE_DIR / "inventory.json"
MODEL_GALLERY_PATH = CACHE_DIR / "model_gallery.json"
LORA_GALLERY_PATH = CACHE_DIR / "lora_gallery.json"

_MODEL_WATCH_DIRS = (
    "checkpoints",
    "diffusion_models",
    "unet",
    "loras",
    "vae",
    "controlnet",
    "upscale_models",
    "clip",
    "text_encoders",
    "clip_vision",
    "embeddings",
    "inpaint",
)
_THUMBNAIL_WATCH_DIRS = ("checkpoints", "loras")


def _read_json(path: Path) -> Any | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def _dir_fingerprint(
    root: Path,
    *,
    extensions: set[str] | None = None,
) -> dict[str, int]:
    if not root.is_dir():
        return {"count": 0, "max_mtime_ns": 0, "bytes": 0}
    count = 0
    max_mtime_ns = 0
    total_bytes = 0
    for dirpath, _dirnames, filenames in os.walk(root):
        base = Path(dirpath)
        for name in filenames:
            path = base / name
            if extensions is not None and path.suffix.lower() not in extensions:
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            count += 1
            max_mtime_ns = max(max_mtime_ns, stat.st_mtime_ns)
            total_bytes += stat.st_size
    return {"count": count, "max_mtime_ns": max_mtime_ns, "bytes": total_bytes}


def _file_fingerprint(path: Path) -> dict[str, int]:
    if not path.is_file():
        return {"count": 0, "max_mtime_ns": 0, "bytes": 0}
    stat = path.stat()
    return {"count": 1, "max_mtime_ns": stat.st_mtime_ns, "bytes": stat.st_size}


def compute_library_fingerprint() -> dict[str, Any]:
    from dreamforge_cli_inventory import MODEL_EXTENSIONS, MODELS_ROOT

    models_root = Path(MODELS_ROOT).resolve()
    fingerprint: dict[str, Any] = {
        "version": 1,
        "models_root": str(models_root),
        "categories": {},
        "thumbnails": {},
        "meta": {},
    }

    for label in _MODEL_WATCH_DIRS:
        fingerprint["categories"][label] = _dir_fingerprint(
            models_root / label,
            extensions=MODEL_EXTENSIONS,
        )

    cache_root = BACKEND_ROOT / "cache"
    for label in _THUMBNAIL_WATCH_DIRS:
        fingerprint["thumbnails"][label] = _dir_fingerprint(cache_root / label)

    fingerprint["meta"]["presets"] = _dir_fingerprint(BACKEND_ROOT / "presets")
    fingerprint["meta"]["style_recipes"] = _file_fingerprint(
        BACKEND_ROOT / "dreamforge_style_recipes.py"
    )
    fingerprint["meta"]["style_thumbnails"] = _dir_fingerprint(
        BACKEND_ROOT / "assets" / "style_thumbnails",
        extensions={".jpg", ".jpeg", ".png", ".webp"},
    )
    return fingerprint


def invalidate_model_library_cache() -> None:
    for path in (MANIFEST_PATH, INVENTORY_PATH, MODEL_GALLERY_PATH, LORA_GALLERY_PATH):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


def _manifest_is_current(manifest: dict[str, Any] | None) -> bool:
    if not manifest:
        return False
    cached_fp = manifest.get("fingerprint")
    if not isinstance(cached_fp, dict):
        return False
    try:
        return cached_fp == compute_library_fingerprint()
    except OSError:
        return False


def _load_manifest() -> dict[str, Any] | None:
    data = _read_json(MANIFEST_PATH)
    return data if isinstance(data, dict) else None


def _persist_cache(
    *,
    fingerprint: dict[str, Any],
    inventory: dict[str, Any],
    model_gallery: list[dict[str, Any]],
    lora_gallery: list[dict[str, Any]],
) -> None:
    _write_json(INVENTORY_PATH, inventory)
    _write_json(MODEL_GALLERY_PATH, model_gallery)
    _write_json(LORA_GALLERY_PATH, lora_gallery)
    _write_json(
        MANIFEST_PATH,
        {
            "fingerprint": fingerprint,
            "built_at": time.time(),
            "counts": {
                "model_gallery": len(model_gallery),
                "lora_gallery": len(lora_gallery),
                "inventory_categories": len(inventory.get("categories") or {}),
            },
        },
    )


def _resolve_cached_thumbnail(cache_subdir: str, model_filename: str, fallback: Path) -> str:
    cache_base = BACKEND_ROOT / "cache" / cache_subdir / Path(model_filename).name
    for suffix in (".jpeg", ".jpg", ".png", ".gif"):
        candidate = cache_base.with_suffix(suffix)
        if candidate.is_file():
            return str(candidate.resolve())
    if fallback.is_file():
        return str(fallback.resolve())
    return str(fallback)


def build_model_gallery_items() -> list[dict[str, Any]]:
    from modules.model_ui_defaults import (
        GALLERY_CATEGORIES,
        engine_name_for_category,
        gallery_caption,
        infer_model_family,
        scan_model_category,
    )

    items: list[dict[str, Any]] = []
    for category in GALLERY_CATEGORIES:
        for relative_name in scan_model_category(category):
            filename = Path(relative_name).name
            if filename.endswith(".merge"):
                fallback = BACKEND_ROOT / "html" / "merge.jpeg"
            else:
                fallback = BACKEND_ROOT / "html" / "warning.jpeg"
            items.append(
                {
                    "category": category,
                    "relative_path": relative_name,
                    "caption": gallery_caption(category, relative_name),
                    "engine_name": engine_name_for_category(category, relative_name),
                    "family": infer_model_family(filename),
                    "thumbnail_path": _resolve_cached_thumbnail(
                        "checkpoints", filename, fallback
                    ),
                }
            )
    return items


def build_lora_gallery_items() -> list[dict[str, Any]]:
    from dreamforge_cli_inventory import list_model_inventory

    inv = list_model_inventory()
    loras = inv.get("categories", {}).get("loras", [])
    fallback = BACKEND_ROOT / "html" / "warning.png"
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in loras:
        name = entry.get("name") or ""
        relative_path = entry.get("relative_path") or name
        if not name or relative_path in seen:
            continue
        seen.add(relative_path)
        items.append(
            {
                "name": name,
                "stem": entry.get("stem") or Path(name).stem,
                "relative_path": relative_path,
                "thumbnail_path": _resolve_cached_thumbnail("loras", name, fallback),
            }
        )
    return items


def build_inventory_payload() -> dict[str, Any]:
    from dreamforge_cli_inventory import list_model_inventory

    inv = list_model_inventory()
    from dreamforge_desktop_bridge import _group_styles

    style_data = _group_styles(inv.get("styles", []))
    return {
        "ok": True,
        "models_root": inv.get("models_root"),
        "categories": inv.get("categories", {}),
        "presets": inv.get("presets", []),
        "styles": style_data["selectable"],
        "style_groups": style_data["groups"],
    }


def rebuild_model_library_cache() -> dict[str, Any]:
    fingerprint = compute_library_fingerprint()
    inventory = build_inventory_payload()
    model_gallery = build_model_gallery_items()
    lora_gallery = build_lora_gallery_items()
    _persist_cache(
        fingerprint=fingerprint,
        inventory=inventory,
        model_gallery=model_gallery,
        lora_gallery=lora_gallery,
    )
    return {
        "rebuilt": True,
        "model_gallery": len(model_gallery),
        "lora_gallery": len(lora_gallery),
        "built_at": time.time(),
    }


def _get_cached_payload(
    path: Path,
    *,
    force_refresh: bool,
    rebuild: Callable[[], Any],
) -> tuple[Any, bool]:
    if force_refresh:
        invalidate_model_library_cache()
    manifest = _load_manifest()
    if _manifest_is_current(manifest):
        cached = _read_json(path)
        if cached is not None:
            return cached, True
    rebuild_model_library_cache()
    return _read_json(path) if path.is_file() else rebuild(), False


def get_cached_inventory(*, force_refresh: bool = False) -> tuple[dict[str, Any], bool]:
    def _fallback() -> dict[str, Any]:
        return build_inventory_payload()

    payload, from_cache = _get_cached_payload(
        INVENTORY_PATH,
        force_refresh=force_refresh,
        rebuild=_fallback,
    )
    if isinstance(payload, dict):
        payload.setdefault("ok", True)
        return payload, from_cache
    return _fallback(), False


def get_cached_model_gallery(*, force_refresh: bool = False) -> tuple[list[dict[str, Any]], bool]:
    payload, from_cache = _get_cached_payload(
        MODEL_GALLERY_PATH,
        force_refresh=force_refresh,
        rebuild=build_model_gallery_items,
    )
    if isinstance(payload, list):
        return payload, from_cache
    return build_model_gallery_items(), False


def get_cached_lora_gallery(*, force_refresh: bool = False) -> tuple[list[dict[str, Any]], bool]:
    payload, from_cache = _get_cached_payload(
        LORA_GALLERY_PATH,
        force_refresh=force_refresh,
        rebuild=build_lora_gallery_items,
    )
    if isinstance(payload, list):
        return payload, from_cache
    return build_lora_gallery_items(), False
