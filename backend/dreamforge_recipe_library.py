"""Managed local storage for discovered DreamForge Recipe v2 files."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

from _paths import PROJECT_ROOT
from dreamforge_recipe import DreamForgeRecipe

RECIPE_LIBRARY_ROOT = PROJECT_ROOT / "outputs" / "dreamforge" / "library" / "recipes"


def save_recipe(recipe_data: Mapping[str, Any], recipe_id: str = "recipe") -> dict[str, Any]:
    recipe = DreamForgeRecipe.from_dict(recipe_data)
    if not recipe.model and not recipe.positive_prompt:
        return {"ok": False, "error": "empty_recipe"}
    payload = recipe.to_dict()
    payload["library_id"] = str(recipe_id or "recipe")
    raw = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    stem = re.sub(r"[^a-zA-Z0-9._-]+", "_", str(recipe_id)).strip("._") or "recipe"
    destination = RECIPE_LIBRARY_ROOT / f"{stem[:80]}-{hashlib.sha256(raw).hexdigest()[:12]}.json"
    temporary = destination.with_suffix(".json.part")
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_bytes(raw)
        temporary.replace(destination)
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        return {"ok": False, "error": f"recipe_save_failed: {exc}"}
    return {"ok": True, "path": str(destination), "filename": destination.name}
