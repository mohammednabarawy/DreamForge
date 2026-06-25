"""Named inpaint intents (Fooocus-style) mapped to concrete generation parameters."""

from __future__ import annotations

from typing import Any

VALID_INPAINT_INTENTS = frozenset({"default", "improve_detail", "modify_content"})

INPAINT_INTENT_LABELS: dict[str, str] = {
    "default": "Default",
    "improve_detail": "Improve detail",
    "modify_content": "Modify content",
}

INPAINT_INTENT_PRESETS: dict[str, dict[str, Any]] = {
    "default": {
        "edit_strength": 0.88,
        "inpaint_grow": 4,
        "inpaint_feather": 4,
        "inpaint_mask_grow_by": 20,
        "requires_fill_engine": True,
        "hint": "Balanced Flux Fill inpaint with surrounding context.",
    },
    "improve_detail": {
        "edit_strength": 0.52,
        "inpaint_grow": 2,
        "inpaint_feather": 2,
        "inpaint_mask_grow_by": 6,
        "requires_fill_engine": True,
        "hint": "Refine masked details only — lower strength, minimal context bleed.",
    },
    "modify_content": {
        "edit_strength": 1.0,
        "inpaint_grow": 8,
        "inpaint_feather": 8,
        "inpaint_mask_grow_by": 16,
        "requires_fill_engine": True,
        "hint": "Replace masked content — full strength with blended edges.",
    },
}


def normalize_inpaint_intent(value: Any) -> str:
    intent = str(value or "default").strip().lower()
    return intent if intent in VALID_INPAINT_INTENTS else "default"


def inpaint_intent_requires_fill_engine(intent: str) -> bool:
    preset = INPAINT_INTENT_PRESETS.get(normalize_inpaint_intent(intent), {})
    return bool(preset.get("requires_fill_engine", True))


def resolve_inpaint_intent_params(job) -> dict[str, Any]:
    """Return preset tuning for the active inpaint intent (job overrides win)."""
    intent = normalize_inpaint_intent(getattr(job, "inpaint_intent", None))
    preset = dict(INPAINT_INTENT_PRESETS[intent])
    out: dict[str, Any] = {
        "inpaint_intent": intent,
        "requires_fill_engine": bool(preset.pop("requires_fill_engine", True)),
        "hint": preset.pop("hint", ""),
    }

    for key, default in preset.items():
        value = getattr(job, key, None)
        out[key] = default if value is None else value
    return out


def merge_inpaint_additional_prompt(prompt: str, job) -> str:
    """Append optional detail/content prompt for improve_detail / modify_content."""
    intent = normalize_inpaint_intent(getattr(job, "inpaint_intent", None))
    if intent not in {"improve_detail", "modify_content"}:
        return prompt
    extra = str(getattr(job, "inpaint_additional_prompt", "") or "").strip()
    if not extra:
        return prompt
    base = str(prompt or "").strip()
    return f"{base}. {extra}" if base else extra


def pick_inpaint_base_model(gallery: list[dict], *, current: str | None = None) -> str | None:
    """Prefer Flux dev FP8 for improve-detail passes when Fill is not required."""
    if current and current.strip():
        hay = current.lower()
        if "fill" not in hay and "kontext" not in hay:
            return current.strip()
    needles = (
        "flux1-dev-fp8",
        "flux1-dev",
        "flux-dev",
        "flux_dev",
    )
    for item in gallery or []:
        blob = " ".join(
            str(item.get(key) or "")
            for key in ("engine_name", "relative_path", "name", "caption", "family")
        ).lower()
        if any(n in blob for n in needles) and "fill" not in blob and "kontext" not in blob:
            return str(item.get("engine_name") or item.get("name") or "").strip() or None
    return None
