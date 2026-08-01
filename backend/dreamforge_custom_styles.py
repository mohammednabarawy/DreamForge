"""Offline DreamForge style storage and Fooocus-style JSON import."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

from _paths import PROJECT_ROOT

CUSTOM_STYLES_PATH = PROJECT_ROOT / "outputs" / "dreamforge" / "library" / "custom_styles.json"
MAX_STYLE_NAME = 120
MAX_PROMPT = 4000


def _text(value: Any, limit: int = MAX_PROMPT) -> str:
    return str(value or "").strip()[:limit]


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")[:70] or "style"


def _style_id(name: str) -> str:
    digest = hashlib.sha256(name.encode("utf-8")).hexdigest()[:10]
    return f"custom_{_slug(name)}_{digest}"


def _as_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if not isinstance(value, list):
        return []
    return [_text(item, 240) for item in value if _text(item, 240)]


def normalize_style(raw: Mapping[str, Any], *, fallback_name: str = "") -> dict[str, Any]:
    name = _text(raw.get("name") or raw.get("original_name") or fallback_name, MAX_STYLE_NAME)
    if not name:
        raise ValueError("style name is required")
    prompt = _text(raw.get("prompt") or raw.get("prompt_prefix"))
    negative = _text(raw.get("negative_prompt") or raw.get("negative"))
    models = _as_list(raw.get("models") or raw.get("model"))
    styles = _as_list(raw.get("styles") or raw.get("sdxl_styles"))
    architecture = _text(raw.get("architecture") or raw.get("base_model"), 80)
    return {
        "id": _style_id(name),
        "original_name": name,
        "prompt_prefix": prompt,
        "negative_prompt": negative,
        "models": models,
        "styles": styles,
        "architecture": architecture,
        "performance": _text(raw.get("performance"), 80),
        "aspect_ratio": _text(raw.get("aspect_ratio") or raw.get("resolution"), 40),
        "thumbnail": _text(raw.get("thumbnail"), 500),
        "notes": _text(raw.get("notes"), 1000),
        "source": "fooocus_import",
        "offline": True,
    }


def _read() -> list[dict[str, Any]]:
    if not CUSTOM_STYLES_PATH.is_file():
        return []
    try:
        payload = json.loads(CUSTOM_STYLES_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return [dict(item) for item in payload if isinstance(item, dict)] if isinstance(payload, list) else []


def _write(styles: list[dict[str, Any]]) -> None:
    CUSTOM_STYLES_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp = CUSTOM_STYLES_PATH.with_suffix(".tmp")
    temp.write_text(json.dumps(styles, indent=2, ensure_ascii=False), encoding="utf-8")
    temp.replace(CUSTOM_STYLES_PATH)


def list_custom_styles() -> list[dict[str, Any]]:
    return _read()


def import_fooocus_styles(payload: Any) -> dict[str, Any]:
    if isinstance(payload, Mapping) and isinstance(payload.get("styles"), (list, dict)):
        payload = payload["styles"]
    entries: list[tuple[str, Mapping[str, Any]]] = []
    if isinstance(payload, Mapping):
        entries = [(str(name), value) for name, value in payload.items() if isinstance(value, Mapping)]
    elif isinstance(payload, list):
        entries = [("", value) for value in payload if isinstance(value, Mapping)]
    else:
        raise ValueError("Fooocus style JSON must be an object or array")
    imported = [normalize_style(value, fallback_name=name) for name, value in entries]
    if not imported:
        raise ValueError("No style entries found")
    current = {str(item.get("id")): item for item in _read() if item.get("id")}
    for style in imported:
        current[style["id"]] = style
    styles = sorted(current.values(), key=lambda item: str(item.get("original_name", "")).lower())
    _write(styles)
    return {"ok": True, "styles": imported, "count": len(imported), "path": str(CUSTOM_STYLES_PATH)}


def delete_custom_style(style_id: str) -> dict[str, Any]:
    style_id = _text(style_id, 160)
    current = _read()
    remaining = [item for item in current if item.get("id") != style_id]
    if len(remaining) == len(current):
        return {"ok": False, "error": "style_not_found"}
    _write(remaining)
    return {"ok": True, "removed": 1}
