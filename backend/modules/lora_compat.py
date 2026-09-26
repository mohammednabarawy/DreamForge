"""LoRA-to-Model architecture compatibility guard.

Detects when a user attaches LoRAs trained for one architecture (e.g. SDXL)
to a model of a different architecture (e.g. Krea 2) and strips them with a
warning, rather than letting ComfyUI silently ignore mismatched tensor keys.
"""
from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger("DreamForge")

# Which LoRA families are compatible with which model families.
# Key = LoRA family, Value = set of compatible model families.
COMPAT_MATRIX: dict[str, set[str]] = {
    "sdxl":            {"sdxl", "sd3"},
    "sd15":            {"sd15"},
    "sd3":             {"sd3", "sdxl"},
    "flux":            {"flux", "flux_kontext", "flux_fill", "flux2", "flux2_klein", "chroma"},
    "flux_kontext":    {"flux", "flux_kontext", "flux_fill", "flux2", "chroma"},
    "krea2":           {"krea2"},
    "qwen_image":      {"qwen_image", "qwen_image_edit"},
    "qwen_image_edit": {"qwen_image", "qwen_image_edit"},
    "hidream":         {"hidream", "hidream_o1"},
    "hidream_o1":      {"hidream", "hidream_o1"},
    "z_image":         {"z_image"},
    "wan":             {"wan"},
    "hunyuan":         {"hunyuan"},
    # Unknown LoRAs pass through (best effort — we can't determine their arch).
}


def check_lora_compatibility(
    lora_entries: list[dict[str, Any]],
    model_family: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Partition *lora_entries* into (compatible, incompatible).

    Each incompatible entry gets extra ``_compat_reason`` and ``_lora_family``
    keys explaining why it was flagged.

    Returns:
        ``(compatible_loras, incompatible_loras)``
    """
    from modules.model_classifier import get_lora_family

    model_fam = (model_family or "").lower()
    compatible: list[dict[str, Any]] = []
    incompatible: list[dict[str, Any]] = []

    for entry in lora_entries or []:
        name = str(entry.get("name") or "").strip()
        if not name:
            continue

        lora_fam = get_lora_family(name)

        if lora_fam == "unknown":
            # Unknown LoRAs are allowed through (best effort)
            compatible.append(entry)
            continue

        allowed_models = COMPAT_MATRIX.get(lora_fam, set())
        if not allowed_models or model_fam in allowed_models:
            compatible.append(entry)
        else:
            entry_copy = {**entry}
            entry_copy["_compat_reason"] = (
                f"LoRA '{name}' is trained for {lora_fam.upper()} architecture "
                f"but the active model is {model_fam.upper()}. "
                f"It will have no effect and has been removed from this generation."
            )
            entry_copy["_lora_family"] = lora_fam
            incompatible.append(entry_copy)
            log.warning(
                "LoRA compat: stripped '%s' (%s) — incompatible with model family '%s'",
                name, lora_fam, model_fam,
            )

    return compatible, incompatible
