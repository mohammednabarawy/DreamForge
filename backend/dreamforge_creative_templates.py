"""Creative template bundles."""

from __future__ import annotations

import copy
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from _paths import BACKEND_ROOT
from dreamforge_vram_profiles import normalize_vram_profile, profile_tier

TEMPLATES_PATH = BACKEND_ROOT / "settings" / "creative_templates.json"


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for key, value in overlay.items():
        if key == "extends":
            continue
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def _resolve_template_entry(entry: dict[str, Any], catalog: dict[str, Any]) -> dict[str, Any]:
    extends = entry.get("extends")
    if not extends:
        return copy.deepcopy(entry)
    parent = catalog.get(str(extends))
    if not isinstance(parent, dict):
        return copy.deepcopy(entry)
    merged = _resolve_template_entry(parent, catalog)
    return _deep_merge(merged, entry)


@lru_cache(maxsize=1)
def load_creative_templates_catalog() -> dict[str, Any]:
    if not TEMPLATES_PATH.is_file():
        return {"schema_version": 1, "templates": {}, "default_template_by_mode": {}}
    with TEMPLATES_PATH.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    if not isinstance(raw, dict):
        return {"schema_version": 1, "templates": {}, "default_template_by_mode": {}}
    templates = raw.get("templates") if isinstance(raw.get("templates"), dict) else {}
    resolved: dict[str, Any] = {}
    for template_id, entry in templates.items():
        if isinstance(entry, dict):
            resolved[str(template_id)] = _resolve_template_entry(entry, templates)
    return {
        "schema_version": raw.get("schema_version", 1),
        "templates": resolved,
        "default_template_by_mode": dict(raw.get("default_template_by_mode") or {}),
    }


def invalidate_creative_templates_cache() -> None:
    load_creative_templates_catalog.cache_clear()


def list_creative_templates(*, studio_mode: str | None = None) -> list[dict[str, Any]]:
    catalog = load_creative_templates_catalog()
    templates = catalog.get("templates") or {}
    mode = (studio_mode or "").strip().lower()
    items: list[dict[str, Any]] = []
    for template_id, entry in sorted(templates.items()):
        if not isinstance(entry, dict):
            continue
        entry_mode = str(entry.get("studio_mode") or "").lower()
        if mode and entry_mode and entry_mode != mode:
            continue
        chain = entry.get("chain") if isinstance(entry.get("chain"), dict) else {}
        items.append(
            {
                "id": template_id,
                "label": entry.get("label") or template_id,
                "studio_mode": entry_mode or None,
                "post_upscale": chain.get("post_upscale"),
                "companions": list(entry.get("companions") or []),
            }
        )

    # Programmatic Merge: Feature 4
    if not mode or mode == "generate":
        try:
            from dreamforge_workflow_templates import WORKFLOW_TEMPLATES
            for wf_id, wf_entry in WORKFLOW_TEMPLATES.items():
                items.append(
                    {
                        "id": f"workflow_{wf_id}",
                        "label": f"Create ({wf_entry.get('name')})",
                        "studio_mode": "generate",
                        "post_upscale": None,
                        "companions": [],
                    }
                )
        except ImportError:
            pass

    return items


def default_template_id_for_mode(studio_mode: str, *, post_upscale: bool = False) -> str | None:
    catalog = load_creative_templates_catalog()
    mode = (studio_mode or "generate").strip().lower()
    if mode == "agent":
        mode = "generate"
    defaults = catalog.get("default_template_by_mode") or {}
    base_id = defaults.get(mode)
    if not base_id:
        return None
    if post_upscale and mode in {"edit", "inpaint"}:
        enhanced = f"{base_id}.enhance2x"
        if enhanced in (catalog.get("templates") or {}):
            return enhanced
    return str(base_id)


def resolve_creative_template(template_id: str) -> dict[str, Any] | None:
    # Check if it's a merged workflow template
    if str(template_id).startswith("workflow_"):
        try:
            from dreamforge_workflow_templates import WORKFLOW_TEMPLATES
            wf_id = template_id[9:]
            if wf_id in WORKFLOW_TEMPLATES:
                wf = WORKFLOW_TEMPLATES[wf_id]
                return {
                    "id": template_id,
                    "studio_mode": "generate",
                    "label": f"Create ({wf.get('name')})",
                    "model_pick": {},
                    "defaults": dict(wf.get("default_params") or {}),
                    "companions": [],
                    "chain": {},
                }
        except ImportError:
            pass

    catalog = load_creative_templates_catalog()
    entry = (catalog.get("templates") or {}).get(str(template_id))
    return copy.deepcopy(entry) if isinstance(entry, dict) else None


def get_creative_template(template_id: str | None) -> dict[str, Any] | None:
    if not template_id:
        return None
    return resolve_creative_template(template_id)


def template_companion_ids(template_id: str | None) -> list[str]:
    entry = get_creative_template(template_id)
    if not entry:
        return []
    companions = entry.get("companions")
    if not isinstance(companions, list):
        return []
    return [str(item) for item in companions if item]


def template_post_upscale_method(template_id: str | None) -> str | None:
    entry = get_creative_template(template_id)
    if not entry:
        return None
    chain = entry.get("chain")
    if not isinstance(chain, dict):
        return None
    method = chain.get("post_upscale")
    return str(method).strip() if method else None


def _apply_vram_template_overrides(
    patch: dict[str, Any],
    entry: dict[str, Any],
    *,
    vram_profile: str | None,
) -> dict[str, Any]:
    overrides = entry.get("vram_overrides")
    if not isinstance(overrides, dict):
        return patch
    tier = profile_tier(normalize_vram_profile(vram_profile))
    tier_patch = overrides.get(tier)
    if isinstance(tier_patch, dict):
        patch.update(copy.deepcopy(tier_patch))
    return patch


def _apply_krita_recipe_defaults(patch: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any]:
    recipe_key = entry.get("krita_recipe")
    if not recipe_key:
        return patch
    try:
        from dreamforge_krita_resources import inpaint_mask_recipe_values

        values = inpaint_mask_recipe_values(str(recipe_key))
        for key, value in values.items():
            patch.setdefault(key, value)
    except ImportError:
        pass
    return patch


def resolve_template_patch(
    template_id: str | None,
    *,
    base: dict[str, Any] | None = None,
    vram_profile: str | None = None,
    post_upscale_enabled: bool = False,
) -> dict[str, Any]:
    """Merge template defaults into a settings dict; returns metadata + patch."""
    entry = get_creative_template(template_id)
    if not entry:
        return {
            "template_id": template_id,
            "patch": dict(base or {}),
            "companions": [],
            "post_upscale": None,
        }

    patch = dict(base or {})
    defaults = entry.get("defaults")
    if isinstance(defaults, dict):
        for key, value in defaults.items():
            patch.setdefault(key, copy.deepcopy(value))

    patch = _apply_vram_template_overrides(patch, entry, vram_profile=vram_profile)
    patch = _apply_krita_recipe_defaults(patch, entry)

    chain = entry.get("chain") if isinstance(entry.get("chain"), dict) else {}
    post_upscale = chain.get("post_upscale")
    if post_upscale_enabled and not post_upscale:
        post_upscale = "ultimate_sd_upscale"
    if post_upscale:
        patch["post_upscale"] = str(post_upscale)
    elif "post_upscale" in patch and not post_upscale_enabled:
        patch.pop("post_upscale", None)

    return {
        "template_id": template_id,
        "studio_mode": entry.get("studio_mode"),
        "patch": patch,
        "companions": template_companion_ids(template_id),
        "post_upscale": str(post_upscale) if post_upscale else patch.get("post_upscale"),
        "model_pick": entry.get("model_pick"),
    }


def companion_entries_for_template(template_id: str | None) -> list[dict]:
    """Return missing template companion entries for prefetch."""
    from dreamforge_cli_inventory import companion_file_present
    from dreamforge_krita_resources import _resource_entry

    missing: list[dict] = []
    for resource_id in template_companion_ids(template_id):
        try:
            entry = _resource_entry(resource_id)
        except KeyError:
            continue
        if entry.get("optional"):
            continue
        req = {"id": entry["id"], "relative": entry["relative"]}
        if companion_file_present(req, min_bytes=int(entry.get("min_bytes", 1024 * 1024))):
            continue
        missing.append(entry)
    return missing
