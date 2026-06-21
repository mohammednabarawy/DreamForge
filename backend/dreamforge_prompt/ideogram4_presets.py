"""Ideogram 4 aspect-ratio presets (sync width/height with JSON aspect_ratio)."""

from __future__ import annotations

from typing import Any

def _snap_dim(value: int) -> int:
    return max(((int(value) + 15) // 16) * 16, 256)


IDEOGRAM4_ASPECT_PRESETS: dict[str, dict[str, Any]] = {
    "1:1": {"label": "Square", "ratio": "1:1", "width": 768, "height": 768},
    "4:5": {"label": "Portrait", "ratio": "4:5", "width": 704, "height": 880},
    "9:16": {"label": "Story", "ratio": "9:16", "width": 576, "height": 1024},
    "16:9": {"label": "Landscape", "ratio": "16:9", "width": 1024, "height": 576},
    "2:3": {"label": "Poster", "ratio": "2:3", "width": 704, "height": 1056},
    "custom": {"label": "Custom", "ratio": "", "width": 0, "height": 0},
}

_ASPECT_RATIO_TO_PRESET: dict[str, str] = {
    "768x768": "1:1",
    "1024x1024": "1:1",
    "704x880": "4:5",
    "896x1120": "4:5",
    "576x1024": "9:16",
    "768x1344": "9:16",
    "1024x576": "16:9",
    "1344x768": "16:9",
    "704x1056": "2:3",
    "896x1344": "2:3",
}


def _normalize_aspect_ratio_key(value: str) -> str:
    return str(value or "").strip().lower().replace("×", "x").replace(" ", "")


def _parse_aspect_dimensions(value: str) -> tuple[int, int] | None:
    key = _normalize_aspect_ratio_key(value)
    if "x" not in key:
        return None
    left, right = key.split("x", 1)
    try:
        width = int(left)
        height = int(right)
    except ValueError:
        return None
    if width <= 0 or height <= 0:
        return None
    return width, height

# Re-export for UI/docs; canonical definition lives in ideogram4.py
IDEOGRAM4_PROMPT_MODES = frozenset({"natural", "structured", "auto"})


def resolve_ideogram4_aspect_preset(
    settings: dict[str, Any] | None,
    job: Any = None,
) -> str:
    aspect_key = ""
    if settings:
        aspect_key = _normalize_aspect_ratio_key(str(settings.get("aspect_ratio") or ""))
    if not aspect_key and job is not None:
        aspect_key = _normalize_aspect_ratio_key(str(getattr(job, "aspect_ratio", None) or ""))
    if aspect_key in _ASPECT_RATIO_TO_PRESET:
        return _ASPECT_RATIO_TO_PRESET[aspect_key]
    if aspect_key and "x" in aspect_key:
        return "custom"

    raw = ""
    if job is not None:
        raw = str(getattr(job, "ideogram4_aspect_preset", None) or "")
    if not raw and settings:
        raw = str(settings.get("ideogram4_aspect_preset") or "")
    key = raw.strip().lower() or "1:1"
    if key not in IDEOGRAM4_ASPECT_PRESETS:
        return "1:1"
    return key


def apply_ideogram4_aspect_preset(
    settings: dict[str, Any] | None,
    *,
    job: Any = None,
    vram_tier: str = "16gb",
) -> dict[str, int | str]:
    """Return width/height/ratio for preset; custom uses existing settings dimensions."""
    from dreamforge_prompt.ideogram4 import apply_ideogram4_vram_caps

    preset_key = resolve_ideogram4_aspect_preset(settings, job)
    preset = IDEOGRAM4_ASPECT_PRESETS[preset_key]
    if preset_key == "custom":
        aspect = str((settings or {}).get("aspect_ratio") or getattr(job, "aspect_ratio", None) or "")
        parsed = _parse_aspect_dimensions(aspect)
        width = int((settings or {}).get("width") or getattr(job, "width", None) or (parsed[0] if parsed else 768))
        height = int((settings or {}).get("height") or getattr(job, "height", None) or (parsed[1] if parsed else 768))
        ratio = f"{width}:{height}"
    else:
        width = int(preset["width"])
        height = int(preset["height"])
        ratio = str(preset["ratio"])
    capped = apply_ideogram4_vram_caps(
        {"width": width, "height": height, "mode": "default", "steps": 20, "mu": 0.0, "std": 1.75},
        vram_tier=vram_tier,
    )
    return {
        "ideogram4_aspect_preset": preset_key,
        "width": int(capped["width"]),
        "height": int(capped["height"]),
        "aspect_ratio": ratio,
    }
