"""Deterministic presets from user intent and local style memory."""

from __future__ import annotations

from typing import Any

from dreamforge_user_style_profile import apply_planning_hints, load_profile

_UNSET = frozenset({None, "", "none"})

INTENT_USE_CASE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "product_ad": ("product ad", "product shot", "commercial", "advertisement", "brand campaign"),
    "cinematic_scene": ("cinematic", "movie still", "film still", "dramatic lighting"),
    "social_post": ("social post", "instagram", "tiktok", "thumbnail"),
    "arabic_poster": ("arabic poster", "arabic text", "poster with arabic"),
    "fast_draft": ("fast draft", "quick sketch", "rough draft", "iterate quickly"),
    "image_edit": ("edit this", "change her", "remove background", "inpaint", "retouch"),
    "book_cover": ("book cover", "novel cover"),
    "avatar_portrait": ("avatar", "profile picture", "headshot", "portrait"),
    "fashion_editorial": ("fashion", "editorial", "vogue"),
    "real_estate": ("real estate", "interior design", "architecture photo"),
}


def infer_use_case_from_intent(intent: str) -> str | None:
    text = (intent or "").lower()
    if not text.strip():
        return None
    for use_case, keywords in INTENT_USE_CASE_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return use_case
    return None


def _is_unset(key: str, settings: dict[str, Any]) -> bool:
    value = settings.get(key)
    if value in _UNSET:
        return True
    if key in ("styles", "lora") and value == []:
        return True
    if key == "model" and not str(value or "").strip():
        return True
    return False


def apply_dynamic_preset(
    intent: str,
    current_settings: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Merge intent + UserStyleProfile + use-case recipe defaults into settings.

    Only fills fields the caller has not already set. Returns (settings, preset_meta).
    """
    settings = apply_planning_hints(dict(current_settings or {}))
    profile = load_profile()
    meta: dict[str, Any] = {
        "schema_version": "1.0",
        "source": [],
        "applied": {},
    }

    if profile.enabled and profile.generation_count:
        meta["source"].append("user_style_profile")

    use_case = settings.get("use_case")
    if _is_unset("use_case", settings):
        inferred = infer_use_case_from_intent(intent)
        if inferred:
            settings["use_case"] = inferred
            use_case = inferred
            meta["source"].append("intent")
            meta["applied"]["use_case"] = inferred

    if use_case and use_case != "none":
        from dreamforge_use_case_recipes import USE_CASE_RECIPES

        if use_case in USE_CASE_RECIPES:
            recipe = USE_CASE_RECIPES[use_case]
            if _is_unset("model", settings) and recipe.get("models"):
                model = str(recipe["models"][0])
                settings["model"] = model
                meta["applied"]["model"] = model
                meta["source"].append("use_case_recipe")
            for key in ("styles", "performance", "aspect_ratio"):
                if _is_unset(key, settings) and recipe.get(key):
                    settings[key] = recipe[key]
                    meta["applied"][key] = recipe[key]
                    meta["source"].append("use_case_recipe")
            prefix = recipe.get("prompt_prefix")
            if prefix and _is_unset("prompt", settings):
                existing = str(settings.get("prompt") or intent or "").strip()
                if not existing or existing == intent:
                    settings["prompt"] = f"{prefix}, {intent}".strip(", ").strip()
                    meta["applied"]["prompt_prefix"] = prefix
                    meta["source"].append("use_case_recipe")

    meta["source"] = sorted(set(meta["source"]))
    return settings, meta


def suggest_dynamic_preset(
    intent: str,
    current_settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Bridge/MCP-friendly wrapper."""
    settings, meta = apply_dynamic_preset(intent, current_settings)
    return {
        "status": "success",
        "settings": settings,
        "dynamic_preset": meta,
    }
