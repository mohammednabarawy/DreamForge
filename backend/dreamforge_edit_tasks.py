"""Backend-owned edit/inpaint task presets for dry-run and generation defaults."""

from __future__ import annotations

from typing import Any

VALID_EDIT_TASKS = frozenset(
    {
        "remove",
        "replace",
        "add",
        "repair",
        "refine",
        "recolor",
        "relight",
        "restyle",
        "extend",
        "global_edit",
    }
)

EDIT_TASK_LABELS: dict[str, str] = {
    "remove": "Remove",
    "replace": "Replace",
    "add": "Add",
    "repair": "Repair",
    "refine": "Refine",
    "recolor": "Recolor",
    "relight": "Relight",
    "restyle": "Restyle",
    "extend": "Extend",
    "global_edit": "Global edit",
}

# Maps high-level tasks onto existing inpaint intent presets where applicable.
EDIT_TASK_INPAINT_INTENT: dict[str, str] = {
    "remove": "modify_content",
    "replace": "modify_content",
    "add": "modify_content",
    "repair": "improve_detail",
    "refine": "improve_detail",
    "recolor": "default",
    "relight": "default",
    "restyle": "default",
}

EDIT_TASK_PRESETS: dict[str, dict[str, Any]] = {
    "remove": {
        "inpaint_intent": "modify_content",
        "edit_strength": 1.0,
        "requires_mask": True,
        "scope": "masked_region",
        "hint": "Remove the masked object and continue the background naturally.",
    },
    "replace": {
        "inpaint_intent": "modify_content",
        "edit_strength": 1.0,
        "requires_mask": True,
        "scope": "masked_region",
        "hint": "Replace masked content with the described subject.",
    },
    "add": {
        "inpaint_intent": "modify_content",
        "edit_strength": 0.92,
        "requires_mask": True,
        "scope": "masked_region",
        "hint": "Add new content inside the masked region.",
    },
    "repair": {
        "inpaint_intent": "improve_detail",
        "edit_strength": 0.52,
        "requires_mask": True,
        "scope": "masked_region",
        "hint": "Repair masked details while preserving identity and surroundings.",
    },
    "refine": {
        "inpaint_intent": "improve_detail",
        "edit_strength": 0.45,
        "requires_mask": True,
        "scope": "masked_region",
        "hint": "Refine masked details with minimal context bleed.",
    },
    "recolor": {
        "inpaint_intent": "default",
        "edit_strength": 0.72,
        "requires_mask": True,
        "scope": "masked_region",
        "hint": "Change color or material inside the masked region.",
    },
    "relight": {
        "inpaint_intent": "default",
        "edit_strength": 0.65,
        "requires_mask": False,
        "scope": "source_image",
        "hint": "Adjust lighting across the image.",
    },
    "restyle": {
        "inpaint_intent": "default",
        "edit_strength": 0.78,
        "requires_mask": False,
        "scope": "source_image",
        "hint": "Restyle the image while preserving composition when possible.",
    },
    "extend": {
        "inpaint_intent": "default",
        "edit_strength": 0.85,
        "requires_mask": False,
        "scope": "canvas_extend",
        "hint": "Extend the canvas in the requested direction.",
    },
    "global_edit": {
        "edit_type": "kontext",
        "edit_strength": 0.72,
        "requires_mask": False,
        "scope": "source_image",
        "hint": "Apply a global instruction edit to the source image.",
    },
}


def normalize_edit_task(value: Any) -> str | None:
    task = str(value or "").strip().lower()
    if not task:
        return None
    if task in VALID_EDIT_TASKS:
        return task
    aliases = {
        "modify_content": "replace",
        "improve_detail": "repair",
        "default": None,
    }
    return aliases.get(task)


def resolve_edit_task_defaults(
    task: str | None,
    *,
    mode: str = "inpaint",
    settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return canonical defaults for a task; caller/job values still win at apply time."""
    data = dict(settings or {})
    normalized = normalize_edit_task(task) or normalize_edit_task(data.get("edit_task"))
    if not normalized:
        if mode == "edit":
            normalized = "global_edit"
        elif mode == "inpaint":
            intent = str(data.get("inpaint_intent") or "default").strip().lower()
            if intent == "improve_detail":
                normalized = "repair"
            elif intent == "modify_content":
                normalized = "replace"
            else:
                normalized = "replace"
        else:
            return {"edit_task": None}

    preset = dict(EDIT_TASK_PRESETS.get(normalized, {}))
    out: dict[str, Any] = {
        "edit_task": normalized,
        "label": EDIT_TASK_LABELS.get(normalized, normalized),
        "hint": preset.pop("hint", ""),
        "scope": preset.pop("scope", "masked_region" if mode == "inpaint" else "source_image"),
        "requires_mask": bool(preset.pop("requires_mask", mode == "inpaint")),
    }
    for key, default in preset.items():
        value = data.get(key)
        if normalized == "global_edit" and key == "edit_type":
            if str(value or "").lower() in {"", "auto", "inpaint", "outpaint"}:
                value = None
        out[key] = value if value is not None else default
    if mode == "inpaint" and "inpaint_intent" not in out:
        mapped = EDIT_TASK_INPAINT_INTENT.get(normalized)
        if mapped:
            out["inpaint_intent"] = mapped
    return out


def apply_edit_task_defaults_to_job(
    job: Any,
    *,
    mode: str = "inpaint",
) -> dict[str, Any]:
    """Apply backend-owned task defaults without overwriting explicit job values."""
    defaults = resolve_edit_task_defaults(
        getattr(job, "edit_task", None),
        mode=mode,
        settings=vars(job) if hasattr(job, "__dict__") else {},
    )
    for key in ("inpaint_intent", "edit_type", "edit_strength"):
        if key in defaults and getattr(job, key, None) is None:
            setattr(job, key, defaults[key])
    if defaults.get("edit_task") == "global_edit":
        if str(getattr(job, "edit_type", "") or "").lower() in {"", "auto", "inpaint", "outpaint"}:
            setattr(job, "edit_type", EDIT_TASK_PRESETS["global_edit"]["edit_type"])
        if str(getattr(job, "cn_type", "") or "").lower() in {"inpaint", "outpaint"}:
            setattr(job, "cn_type", None)
            setattr(job, "cn_selection", None)
    return defaults
