"""Starter Ideogram 4 structured caption templates."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_TEMPLATES_PATH = Path(__file__).with_name("ideogram4_caption_templates.json")


def _load_templates_doc() -> dict[str, Any]:
    if not _TEMPLATES_PATH.is_file():
        return {"templates": []}
    return json.loads(_TEMPLATES_PATH.read_text(encoding="utf-8"))


def list_ideogram4_caption_templates() -> list[dict[str, Any]]:
    """Return template metadata (id, label, description, aspect_ratio)."""
    out: list[dict[str, Any]] = []
    for item in _load_templates_doc().get("templates") or []:
        if not isinstance(item, dict):
            continue
        tid = str(item.get("id") or "").strip()
        if not tid:
            continue
        out.append(
            {
                "id": tid,
                "label": str(item.get("label") or tid),
                "description": str(item.get("description") or ""),
                "aspect_ratio": str(item.get("aspect_ratio") or "1:1"),
            }
        )
    return out


def get_ideogram4_caption_template(template_id: str) -> dict[str, Any] | None:
    key = str(template_id or "").strip()
    if not key:
        return None
    for item in _load_templates_doc().get("templates") or []:
        if isinstance(item, dict) and str(item.get("id") or "") == key:
            return dict(item)
    return None


def render_ideogram4_caption_template(
    template_id: str,
    *,
    aspect_ratio: str | None = None,
) -> dict[str, Any]:
    """Return {ok, caption, errors, template}."""
    tpl = get_ideogram4_caption_template(template_id)
    if not tpl:
        return {"ok": False, "errors": [f"unknown template: {template_id}"], "caption": None}
    caption_obj = tpl.get("caption")
    if not isinstance(caption_obj, dict):
        return {"ok": False, "errors": ["template caption missing"], "caption": None}
    merged = json.loads(json.dumps(caption_obj))
    ratio = str(aspect_ratio or tpl.get("aspect_ratio") or merged.get("aspect_ratio") or "1:1")
    merged["aspect_ratio"] = ratio
    from dreamforge_prompt.ideogram4 import validate_ideogram_caption

    normalized = validate_ideogram_caption(json.dumps(merged, ensure_ascii=False))
    if not normalized.get("ok"):
        return {
            "ok": False,
            "errors": normalized.get("errors") or ["invalid template caption"],
            "caption": None,
            "template": {"id": tpl.get("id"), "label": tpl.get("label")},
        }
    return {
        "ok": True,
        "errors": [],
        "caption": normalized.get("normalized"),
        "template": {
            "id": tpl.get("id"),
            "label": tpl.get("label"),
            "aspect_ratio": ratio,
        },
    }
