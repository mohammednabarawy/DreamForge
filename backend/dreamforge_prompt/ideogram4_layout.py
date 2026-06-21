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
