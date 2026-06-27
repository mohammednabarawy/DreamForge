"""Multi-slot reference images (Fooocus-style image prompt slots)."""

from __future__ import annotations

import json
from typing import Any

VALID_REFERENCE_ROLES = frozenset(
    {
        "image_prompt",
        "restyle",
        "source_edit",
        "inpaint",
        "upscale",
        "structure",
    }
)

MAX_REFERENCE_SLOTS = 4
DEFAULT_SLOT_WEIGHT = 0.75
DEFAULT_SLOT_STOP_AT = 1.0


def _clamp_float(value: Any, default: float, lo: float, hi: float) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, out))


def normalize_reference_slot(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    path = str(raw.get("path") or "").strip()
    if not path:
        return None
    role = str(raw.get("role") or "image_prompt").strip().lower()
    if role not in VALID_REFERENCE_ROLES:
        role = "image_prompt"
    weight = _clamp_float(raw.get("weight"), DEFAULT_SLOT_WEIGHT, 0.0, 2.0)
    stop_at = _clamp_float(raw.get("stop_at"), DEFAULT_SLOT_STOP_AT, 0.0, 1.0)
    structure_type = str(raw.get("structure_type") or raw.get("cn_type") or "").strip().lower()
    slot: dict[str, Any] = {
        "path": path,
        "role": role,
        "weight": weight,
        "stop_at": stop_at,
    }
    if role == "structure" and structure_type:
        slot["structure_type"] = structure_type
    return slot


def coerce_reference_slots(job) -> list[dict[str, Any]]:
    """Read references[] or project legacy single-image fields into slots."""
    raw = getattr(job, "references", None)
    if isinstance(raw, str):
        text = raw.strip()
        if text.startswith("["):
            try:
                raw = json.loads(text)
            except json.JSONDecodeError:
                raw = None
    if isinstance(raw, list) and raw:
        slots: list[dict[str, Any]] = []
        for item in raw[:MAX_REFERENCE_SLOTS]:
            norm = normalize_reference_slot(item)
            if norm:
                slots.append(norm)
        if slots:
            return slots

    slots = []
    role = str(getattr(job, "reference_role", "") or "").strip().lower()
    ref_path = str(
        getattr(job, "reference_image", None)
        or getattr(job, "input_image", None)
        or getattr(job, "upscale_image", None)
        or ""
    ).strip()
    if not ref_path:
        return slots

    if role not in VALID_REFERENCE_ROLES:
        wm = str(getattr(job, "workflow_mode", "") or "").lower()
        if wm in {"ipadapter", "reference_ipadapter"}:
            role = "image_prompt"
        elif str(getattr(job, "cn_type", "") or "").lower() in {
            "canny",
            "depth",
            "pose",
            "lineart",
            "scribble",
        }:
            role = "structure"
        elif str(getattr(job, "cn_type", "") or "").lower() == "upscale":
            role = "upscale"
        elif getattr(job, "inpaint_mask_path", None):
            role = "inpaint"
        else:
            role = "restyle"

    weight = _clamp_float(
        getattr(job, "reference_weight", None),
        DEFAULT_SLOT_WEIGHT,
        0.0,
        2.0,
    )
    stop_at = _clamp_float(
        getattr(job, "cn_stop", None),
        DEFAULT_SLOT_STOP_AT,
        0.0,
        1.0,
    )
    slot: dict[str, Any] = {
        "path": ref_path,
        "role": role,
        "weight": weight,
        "stop_at": stop_at,
    }
    if role == "structure":
        st = str(
            getattr(job, "structure_type", None)
            or getattr(job, "cn_type", None)
            or "canny"
        ).strip().lower()
        if st and st not in {"none", "auto", "img2img", "upscale", "inpaint"}:
            slot["structure_type"] = st
    slots.append(slot)
    return slots


def resolve_reference_composition(slots: list[dict[str, Any]]) -> dict[str, Any]:
    if not slots:
        return {"mode": "none"}
    ipa = [s for s in slots if s.get("role") == "image_prompt"]
    structure = [s for s in slots if s.get("role") == "structure"]
    # restyle (img2img) and source_edit (Kontext/Qwen) are both single base
    # images that anchor the workflow; extra image-prompt slots ride along.
    base = [s for s in slots if s.get("role") in ("restyle", "source_edit")]
    if len(base) > 1:
        return {
            "mode": "invalid",
            "reason": "Only one source / base image is supported.",
        }
    if len(structure) > 1:
        return {
            "mode": "invalid",
            "reason": "Only one structure slot is supported.",
        }
    if base and structure:
        return {
            "mode": "invalid",
            "reason": "Source / base cannot combine with a structure slot.",
        }
    # A restyle/source base may carry extra image-prompt references; they ride
    # along as Kontext reference latents / img2img stitch handled per-model.
    if base:
        return {
            "mode": str(base[0].get("role") or "restyle"),
            "base_slot": base[0],
            "restyle_slot": base[0],
            "ipadapter_slots": ipa,
        }
    if ipa and structure:
        return {
            "mode": "ipadapter_controlnet",
            "ipadapter_slots": ipa,
            "structure_slot": structure[0],
        }
    if len(ipa) > 1:
        return {"mode": "ipadapter_multi", "ipadapter_slots": ipa}
    if len(ipa) == 1:
        return {"mode": "ipadapter", "ipadapter_slots": ipa}
    if structure:
        return {"mode": "controlnet", "structure_slot": structure[0]}
    primary = slots[0]
    return {"mode": primary.get("role") or "restyle", "primary_slot": primary}


# Families that have no native reference conditioning (no ReferenceLatent,
# IP-Adapter, or ControlNet). Extra references for these are folded into a single
# stitched img2img init image instead of being dropped.
NON_REFERENCE_FAMILIES = frozenset(
    {
        "krea2",
        "z-image",
        "z_image",
        "zimage",
        "z-image-turbo",
    }
)


def family_reference_mechanism(
    model_family: Any,
    *,
    mode: Any = "",
    is_kontext: bool = False,
) -> str:
    """How a model family ingests multiple reference images.

    Returns one of: ``kontext`` (ReferenceLatent stitch/chain), ``qwen_plus``
    (multi-image edit node), ``ipadapter`` (chained IP-Adapter), or
    ``img2img_init`` (stitch references into a single init image) for families
    without native reference conditioning.
    """
    family = str(model_family or "").strip().lower()
    m = str(mode or "").strip().lower()
    if is_kontext or m == "kontext" or "kontext" in family:
        return "kontext"
    if m == "qwen_edit" or family.startswith("qwen"):
        return "qwen_plus"
    if m in {"ipadapter", "ipadapter_faceid", "ipadapter_controlnet", "controlnet"}:
        return "ipadapter"
    return "img2img_init"


def apply_reference_slots_to_job(job) -> dict[str, Any]:
    """Project slots onto legacy job fields used by routing/graph builders."""
    slots = coerce_reference_slots(job)
    if not slots:
        return {}
    composition = resolve_reference_composition(slots)
    if composition.get("mode") == "invalid":
        return {"references": slots, "reference_composition_error": composition.get("reason")}

    job.references = slots
    primary = slots[0]
    role = str(primary.get("role") or "restyle")
    path = str(primary.get("path") or "")
    out: dict[str, Any] = {"references": slots, "reference_role": role}

    if role == "image_prompt":
        out.update(
            {
                "reference_image": path,
                "input_image": None,
                "reference_weight": primary.get("weight", DEFAULT_SLOT_WEIGHT),
            }
        )
    elif role == "restyle":
        out.update(
            {
                "input_image": path,
                "reference_image": path,
            }
        )
        if getattr(job, "edit_strength", None) is None:
            out["edit_strength"] = primary.get("weight", DEFAULT_SLOT_WEIGHT)
    elif role == "structure":
        st = str(primary.get("structure_type") or "canny")
        out.update(
            {
                "reference_image": path,
                "input_image": None,
                "cn_selection": "Custom...",
                "cn_type": st,
                "cn_strength": primary.get("weight", 1.0),
                "cn_stop": primary.get("stop_at", DEFAULT_SLOT_STOP_AT),
                "structure_type": st,
            }
        )

    mode = composition.get("mode")
    if mode == "ipadapter_controlnet":
        out["workflow_mode"] = "ipadapter_controlnet"
        struct = composition.get("structure_slot") or {}
        out["structure_type"] = struct.get("structure_type") or "canny"
        out["cn_selection"] = "Custom..."
        out["cn_type"] = out["structure_type"]
        out["cn_strength"] = struct.get("weight", 1.0)
        out["cn_stop"] = struct.get("stop_at", DEFAULT_SLOT_STOP_AT)
    elif mode in {"ipadapter", "ipadapter_multi"}:
        out["workflow_mode"] = "ipadapter"
    elif mode == "controlnet":
        out["workflow_mode"] = "controlnet"

    for key, value in out.items():
        setattr(job, key, value)
    return out
