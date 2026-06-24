"""Explicit image-role helpers for generation routing."""

from __future__ import annotations

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

_IMAGE_PROMPT_WORKFLOW_MODES = frozenset(
    {"ipadapter", "reference", "reference_ipadapter"}
)


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def infer_reference_role(job, studio_mode: str | None = None) -> str:
    """Infer image role from explicit field or legacy routing state."""
    explicit = _norm(getattr(job, "reference_role", None))
    if explicit in VALID_REFERENCE_ROLES:
        return explicit

    workflow_mode = _norm(getattr(job, "workflow_mode", None))
    edit_type = _norm(getattr(job, "edit_type", None))
    cn_type = _norm(getattr(job, "cn_type", None))
    studio = _norm(studio_mode or getattr(job, "studio_mode", None))
    has_input = bool(getattr(job, "input_image", None))
    has_ref = bool(
        getattr(job, "reference_image", None)
        or getattr(job, "reference_images", None)
    )
    has_upscale = bool(getattr(job, "upscale_image", None))
    has_mask = bool(getattr(job, "inpaint_mask_path", None))

    if studio == "upscale" or (has_upscale and not has_input):
        return "upscale" if (has_upscale or has_input) else ""

    if (
        studio == "inpaint"
        or has_mask
        or edit_type == "inpaint"
        or cn_type == "inpaint"
    ):
        if workflow_mode == "generate":
            return "restyle" if (has_input or has_ref) else ""
        return "inpaint" if (has_input or has_mask) else ""

    if workflow_mode in _IMAGE_PROMPT_WORKFLOW_MODES:
        return "image_prompt" if (has_ref or has_input) else ""

    if workflow_mode == "generate" and (has_input or has_ref):
        return "restyle"

    if studio in ("generate", "agent"):
        return "restyle" if (has_input or has_ref) else ""

    if has_input or has_ref:
        return "source_edit"

    return ""


def is_upscale_reference_role(job, studio_mode: str | None = None) -> bool:
    """True when the job should run upscale routing, ignoring stale fields."""
    role = infer_reference_role(job, studio_mode=studio_mode)
    if role == "upscale":
        return True
    if role in {"restyle", "image_prompt", "source_edit", "inpaint", "structure"}:
        return False
    has_input = bool(getattr(job, "input_image", None))
    has_upscale = bool(getattr(job, "upscale_image", None))
    return bool(has_upscale and not has_input)


def plan_mode_from_reference_role(job) -> str | None:
    """Map explicit image role to dry-run plan mode when authoritative."""
    role = infer_reference_role(job)
    workflow_mode = _norm(getattr(job, "workflow_mode", None))
    if role == "upscale":
        return "upscale"
    if role == "inpaint":
        return "inpaint"
    if role in {"restyle", "image_prompt"} and workflow_mode == "generate":
        return "generate"
    if role == "source_edit":
        return "edit"
    return None
