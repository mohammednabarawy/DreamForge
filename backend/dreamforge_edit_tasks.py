"""Backend-owned edit/inpaint task presets for dry-run and generation defaults."""

from __future__ import annotations

import os
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
        "photo_restore",
        "outfit_transfer",
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
    "photo_restore": "Restore photo",
    "outfit_transfer": "Outfit transfer",
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
    "outfit_transfer": "modify_content",
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
    "photo_restore": {
        "edit_strength": 0.40,
        "requires_mask": False,
        "scope": "source_image",
        "hint": "Restore and enhance old, damaged, or low-quality photos.",
        "steps": 6,
        "cfg": 1.5,
        "sampler_name": "dpmpp_2s_ancestral_cfg_pp",
        "scheduler": "karras",
        "depth_strength": 0.15,
        "lineart_strength": 0.35,
        "face_preservation": True,
    },
    "outfit_transfer": {
        "inpaint_intent": "modify_content",
        "edit_type": "qwen_edit",
        "edit_strength": 1.0,
        "requires_mask": False,
        "scope": "source_image",
        "hint": "Transfer clothing from a reference image while preserving the person, pose, and scene.",
    },
}

OUTFIT_TRANSFER_REGION_LABELS = {
    "upper_body": "upper body clothing",
    "lower_body": "lower body clothing",
    "full_outfit": "full outfit",
    "shoes_accessories": "shoes and accessories",
}


def outfit_transfer_has_reference(job: Any) -> bool:
    source_paths = {
        _normalize_reference_path(getattr(job, "input_image", None)),
        _normalize_reference_path(getattr(job, "upscale_image", None)),
    }
    source_paths.discard("")

    def is_outfit_path(value: Any) -> bool:
        path = str(value or "").strip()
        if not path:
            return False
        normalized = _normalize_reference_path(path)
        return bool(normalized) and normalized not in source_paths

    for key in ("reference_images", "control_images"):
        value = getattr(job, key, None)
        if isinstance(value, str) and is_outfit_path(value):
            return True
        if isinstance(value, (list, tuple)) and any(is_outfit_path(item) for item in value):
            return True
    value = getattr(job, "reference_image", None)
    if is_outfit_path(value):
        return True
    raw_refs = getattr(job, "references", None)
    if isinstance(raw_refs, dict):
        return is_outfit_path(raw_refs.get("path"))
    if isinstance(raw_refs, (list, tuple)):
        return any(
            is_outfit_path(item.get("path") if isinstance(item, dict) else item)
            for item in raw_refs
        )
    return False


def _normalize_reference_path(value: Any) -> str:
    path = str(value or "").strip()
    if not path:
        return ""
    return os.path.normcase(os.path.normpath(path))


def merge_outfit_transfer_prompt(prompt: str, job: Any) -> str:
    """Add garment-region guidance for the outfit-transfer task."""
    if normalize_edit_task(getattr(job, "edit_task", None)) != "outfit_transfer":
        return prompt
    regions = getattr(job, "outfit_transfer_regions", None) or []
    if isinstance(regions, str):
        regions = [part.strip() for part in regions.split(",")]
    labels = [
        OUTFIT_TRANSFER_REGION_LABELS[key]
        for key in regions
        if key in OUTFIT_TRANSFER_REGION_LABELS
    ]
    guidance = "Preserve the face, pose, body shape, background, and lighting; only change clothing."
    if labels:
        guidance = f"Target garments: {', '.join(labels)}. {guidance}"
    return f"{prompt.strip()} {guidance}".strip()


def merge_photo_restore_task_settings(
    settings: dict[str, Any],
    job: Any,
    defaults: dict[str, Any],
) -> dict[str, Any]:
    """Apply photo-restore sampling defaults without clobbering explicit user values."""
    if defaults.get("edit_task") != "photo_restore":
        return settings
    out = dict(settings)
    mapping = (
        ("steps", "steps"),
        ("cfg", "cfg"),
        ("sampler_name", "sampler_name"),
        ("scheduler", "scheduler"),
    )
    for preset_key, settings_key in mapping:
        if preset_key not in defaults:
            continue
        job_attr = "cfg_scale" if preset_key == "cfg" else preset_key
        if getattr(job, job_attr, None) is not None:
            continue
        if out.get(settings_key) is None:
            out[settings_key] = defaults[preset_key]
    return out


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
    elif defaults.get("edit_task") == "photo_restore":
        if str(getattr(job, "edit_type", "") or "").lower() in {
            "",
            "auto",
            "kontext",
            "qwen_edit",
            "inpaint",
            "outpaint",
        }:
            setattr(job, "edit_type", "auto")
        if str(getattr(job, "cn_type", "") or "").lower() in {
            "inpaint",
            "outpaint",
            "kontext",
            "qwen_edit",
        }:
            setattr(job, "cn_type", None)
            setattr(job, "cn_selection", None)
        for key in (
            "steps",
            "cfg_scale",
            "sampler",
            "scheduler",
            "depth_strength",
            "lineart_strength",
            "face_preservation",
        ):
            if key == "cfg_scale":
                preset_key = "cfg"
            elif key == "sampler":
                preset_key = "sampler_name"
            else:
                preset_key = key
            if preset_key in defaults and getattr(job, key, None) is None:
                setattr(job, key, defaults[preset_key])
    elif defaults.get("edit_task") == "outfit_transfer":
        if getattr(job, "inpaint_mask_path", None):
            setattr(job, "edit_type", "inpaint")
            setattr(job, "cn_type", "inpaint")
            setattr(job, "cn_selection", "Custom...")
        elif str(getattr(job, "edit_type", "") or "").lower() in {"", "auto", "kontext", "img2img"}:
            setattr(job, "edit_type", "qwen_edit")
            setattr(job, "cn_type", None)
            setattr(job, "cn_selection", None)
    return defaults
