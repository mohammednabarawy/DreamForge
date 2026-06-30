"""Merge visual layout data into Ideogram 4 structured captions."""

from __future__ import annotations

import json
from typing import Any


def ui_rect_to_bbox(x: float, y: float, w: float, h: float) -> list[int]:
    """Convert 0–1 UI rect (top-left origin) to Ideogram bbox [y1,x1,y2,x2] in 0–1000."""
    x1 = max(0, min(1000, int(round(x * 1000))))
    y1 = max(0, min(1000, int(round(y * 1000))))
    x2 = max(0, min(1000, int(round((x + w) * 1000))))
    y2 = max(0, min(1000, int(round((y + h) * 1000))))
    if y2 <= y1:
        y2 = min(1000, y1 + 1)
    if x2 <= x1:
        x2 = min(1000, x1 + 1)
    return [y1, x1, y2, x2]


def merge_ideogram_caption(
    base: dict[str, Any],
    *,
    layout_elements: list[dict[str, Any]] | None = None,
    background: str | None = None,
    style_description: dict[str, Any] | None = None,
    high_level_description: str | None = None,
    aspect_ratio: str | None = None,
) -> dict[str, Any]:
    """Overlay layout builder fields onto an existing caption dict."""
    out = dict(base)
    if aspect_ratio:
        out["aspect_ratio"] = aspect_ratio
    if high_level_description:
        out["high_level_description"] = high_level_description
    if style_description:
        out["style_description"] = style_description
    comp = dict(out.get("compositional_deconstruction") or {})
    if background:
        comp["background"] = background
    if layout_elements is not None:
        comp["elements"] = layout_elements
    if comp:
        out["compositional_deconstruction"] = comp
    return out


def caption_from_layout(
    *,
    aspect_ratio: str,
    high_level_description: str,
    background: str,
    elements: list[dict[str, Any]],
    style_description: dict[str, Any] | None = None,
) -> str:
    import re

    # 1. Strict required fields validation
    if not aspect_ratio.strip():
        raise ValueError("aspect_ratio is required for layout builder")
    if not re.fullmatch(r"\d+:\d+", aspect_ratio.strip()):
        raise ValueError(f"aspect_ratio must be in W:H format (e.g. '1:1', '16:9'), got: {aspect_ratio!r}")
    if not high_level_description.strip():
        raise ValueError("high_level_description is required for layout builder")
    if not background.strip():
        raise ValueError("background is required for layout builder")
        
    # 2. Strict bbox coordinate check
    for index, el in enumerate(elements):
        bbox = el.get("bbox")
        if bbox is not None:
            if not isinstance(bbox, list) or len(bbox) != 4:
                raise ValueError(f"Element {index + 1}: bbox must be an array of 4 integers")
            try:
                y1, x1, y2, x2 = [int(v) for v in bbox]
            except (TypeError, ValueError):
                raise ValueError(f"Element {index + 1}: bbox coordinates must be integers")
            if not all(0 <= v <= 1000 for v in [y1, x1, y2, x2]):
                raise ValueError(f"Element {index + 1}: bbox coordinates must be between 0 and 1000")
            if y1 >= y2:
                raise ValueError(f"Element {index + 1}: y1 ({y1}) must be less than y2 ({y2})")
            if x1 >= x2:
                raise ValueError(f"Element {index + 1}: x1 ({x1}) must be less than x2 ({x2})")

    # 3. Strict style description hex color check
    if style_description:
        palette = style_description.get("color_palette")
        if palette is not None:
            if not isinstance(palette, list):
                raise ValueError("color_palette must be an array")
            for color in palette:
                color_str = str(color).strip()
                if not re.fullmatch(r"^#[0-9A-Fa-f]{6}$", color_str):
                    raise ValueError(f"Invalid hex color: {color_str}")

    from dreamforge_prompt.ideogram4 import normalize_ideogram_caption_obj

    obj = merge_ideogram_caption(
        {},
        layout_elements=elements,
        background=background,
        style_description=style_description,
        high_level_description=high_level_description,
        aspect_ratio=aspect_ratio,
    )
    return normalize_ideogram_caption_obj(obj)
