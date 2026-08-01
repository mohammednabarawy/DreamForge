"""Read ComfyUI workflow JSON embedded in PNG text metadata."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_png_workflow(path: str | Path) -> dict[str, Any]:
    from PIL import Image

    with Image.open(path) as image:
        metadata = dict(getattr(image, "text", {}) or {})
    for key in ("workflow", "comfy_workflow", "prompt"):
        raw = metadata.get(key)
        if not isinstance(raw, str) or not raw.strip():
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and payload:
            return payload
    raise ValueError("PNG does not contain a ComfyUI workflow JSON payload")
