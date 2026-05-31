#!/usr/bin/env python3
"""Convert legacy SDXL styles + hand-authored presets into ``dreamforge_style_recipes.py``."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from dreamforge_use_case_recipes import USE_CASE_RECIPES  # noqa: E402

DEFAULT_STYLES_PATH = BACKEND / "settings" / "styles.default"
RECIPES_PATH = BACKEND / "dreamforge_style_recipes.py"
THUMB_PREFIX = "assets/style_thumbnails"


def _recipe_key(name: str) -> str:
    clean = name.lower()
    if clean.startswith("style:"):
        clean = clean.replace("style:", "", 1).strip()
    elif clean.startswith("artify:"):
        clean = clean.replace("artify:", "", 1).strip()
    return clean.replace(" ", "_").replace("-", "_").replace("'", "")


def _thumbnail_name(display_name: str) -> str:
    from dreamforge_style_assets import fooocus_sample_filename

    return f"{THUMB_PREFIX}/{fooocus_sample_filename(display_name)}"


def convert_styles() -> None:
    recipes: dict[str, dict] = {}

    for key, val in USE_CASE_RECIPES.items():
        payload = dict(val)
        payload["thumbnail"] = f"{THUMB_PREFIX}/{key}.jpg"
        recipes[key] = payload

    with DEFAULT_STYLES_PATH.open("r", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        for row in reader:
            if not row or len(row) < 3:
                continue
            name = row[0].strip()
            if not name or name.startswith("name") or name.startswith(">>>>>>"):
                continue
            prompt = row[1]
            negative = row[2]
            key = _recipe_key(name)
            if key in recipes:
                continue
            recipes[key] = {
                "positive": [prompt] if prompt else [],
                "negative": [negative] if negative else [],
                "thumbnail": _thumbnail_name(name),
                "original_name": name,
            }

    RECIPES_PATH.write_text(
        "from __future__ import annotations\n\n"
        "from typing import Any\n\n"
        f"STYLE_RECIPES: dict[str, dict[str, Any]] = {json.dumps(recipes, indent=4, ensure_ascii=False)}\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(recipes)} style recipes to {RECIPES_PATH}")


if __name__ == "__main__":
    convert_styles()
