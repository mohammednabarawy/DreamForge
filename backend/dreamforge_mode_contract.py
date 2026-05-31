"""Mode contract summaries for plan-preview honesty."""

from __future__ import annotations

from typing import Any


CONTRACT_FIELDS = (
    "model",
    "style",
    "aspect_ratio",
    "performance",
    "steps",
    "cfg_scale",
    "sampler",
    "scheduler",
    "edit_type",
    "edit_strength",
    "input_image",
    "inpaint_mask_path",
    "upscale_image",
    "upscale_method",
    "cn_selection",
    "cn_type",
    "workflow_mode",
)


def build_mode_contract(
    mode: str,
    patch: dict[str, Any] | None,
    original_settings: dict[str, Any] | None = None,
    *,
    source: str = "local",
) -> dict[str, Any]:
    """Describe what a plan will preserve or change before it is applied."""
    normalized_mode = (mode or "generate").strip().lower()
    proposed = patch if isinstance(patch, dict) else {}
    original = original_settings if isinstance(original_settings, dict) else {}

    changed_fields: list[str] = []
    preserved_fields: list[str] = []
    for field in CONTRACT_FIELDS:
        if field in proposed and _meaningful(proposed.get(field)):
            if _stringify(proposed.get(field)) != _stringify(original.get(field)):
                changed_fields.append(field)
            elif field in original:
                preserved_fields.append(field)
        elif field in original and _meaningful(original.get(field)):
            preserved_fields.append(field)

    original_model = _stringify(original.get("model"))
    proposed_model = _stringify(proposed.get("model"))
    selected_model = proposed_model or original_model

    if original_model and (not proposed_model or proposed_model == original_model):
        model_policy = "preserve_user_model"
        model_source = "user_selected"
    elif normalized_mode == "generate":
        if proposed_model:
            model_policy = "suggest_model"
            model_source = source or "planner"
        else:
            model_policy = "manual_selection"
            model_source = "user_required"
    elif normalized_mode in {"edit", "inpaint", "upscale"}:
        model_policy = "route_curated_model"
        model_source = source or "router"
    else:
        model_policy = "agent_planned"
        model_source = source or "agent"

    summary = _summary(normalized_mode, model_policy, selected_model, changed_fields)
    merged = {**original, **proposed}
    return {
        "schema_version": "1.0",
        "mode": normalized_mode,
        "model_policy": model_policy,
        "model_source": model_source,
        "selected_model": selected_model,
        "changed_fields": changed_fields,
        "preserved_fields": sorted(set(preserved_fields)),
        "preservation_hints": build_preservation_hints(merged),
        "summary": summary,
    }


def _meaningful(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, dict, set)):
        return bool(value)
    return True


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value)


def _summary(mode: str, policy: str, model: str, changed_fields: list[str]) -> str:
    if policy == "preserve_user_model":
        return "Generate mode will preserve the user-selected model."
    if policy == "manual_selection":
        return "Generate mode expects the user to choose the model."
    if policy == "suggest_model":
        return f"Generate mode proposes {model}." if model else "Generate mode proposes a model."
    if policy == "route_curated_model":
        label = mode.capitalize()
        return f"{label} mode will use the routed local stack."
    return "Agent mode will plan with the selected local runtime."


def build_preservation_hints(settings: dict[str, Any] | None) -> list[str]:
    """Human-readable preservation intents from edit-family UI toggles."""
    data = settings if isinstance(settings, dict) else {}
    hints: list[str] = []
    if data.get("face_preservation"):
        hints.append("Preserve face identity")
    if data.get("preserve_character"):
        hints.append("Preserve character identity and outfit")
    if data.get("preserve_style"):
        hints.append("Preserve overall style and palette")
    if data.get("preserve_text"):
        hints.append("Preserve text, logos, and typography")
    return hints
