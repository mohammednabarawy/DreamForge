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
    fingerprint = {key: value for key, value in payload.items() if key not in {"created_at", "completeness"}}
    stem = re.sub(r"[^a-zA-Z0-9._-]+", "_", str(recipe_id)).strip("._") or "recipe"
    digest = hashlib.sha256(json.dumps(fingerprint, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:12]
    destination = RECIPE_LIBRARY_ROOT / f"{stem[:80]}-{digest}.json"
    temporary = destination.with_suffix(".json.part")
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_bytes(raw)
        temporary.replace(destination)
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        return {"ok": False, "error": f"recipe_save_failed: {exc}"}
    return {"ok": True, "path": str(destination), "filename": destination.name}


def list_recipes() -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    try:
        paths = sorted(RECIPE_LIBRARY_ROOT.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    except OSError as exc:
        return {"ok": False, "error": f"recipe_list_failed: {exc}", "items": []}
    for path in paths:
        try:
            recipe = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(recipe, dict):
                continue
            items.append({
                "filename": path.name,
                "path": str(path),
                "modified_at": path.stat().st_mtime,
                "recipe": recipe,
            })
        except (OSError, json.JSONDecodeError):
            continue
    return {"ok": True, "root": str(RECIPE_LIBRARY_ROOT), "items": items}


def delete_recipe(filename: str) -> dict[str, Any]:
    name = Path(str(filename or "")).name
    if not name.endswith(".json") or name != str(filename):
        return {"ok": False, "error": "invalid_recipe_filename"}
    target = RECIPE_LIBRARY_ROOT / name
    try:
        target.unlink()
    except FileNotFoundError:
        return {"ok": False, "error": "recipe_not_found"}
    except OSError as exc:
        return {"ok": False, "error": f"recipe_delete_failed: {exc}"}
    return {"ok": True, "filename": name}
