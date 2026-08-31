"""Central workflow routing: studio mode, image role, and Comfy graph selection."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from dreamforge_reference_role import (
    VALID_REFERENCE_ROLES,
    infer_reference_role,
    is_upscale_reference_role,
)

_ROUTE_LABELS: dict[str, str] = {
    "image_prompt": "Creating with image prompt",
    "restyle": "Restyling source image",
    "source_edit": "Editing source image",
    "inpaint": "Inpainting region",
    "upscale": "Upscaling target image",
    "structure": "Structure guidance",
}

_FAMILY_ROUTE_LABELS: dict[str, dict[str, str]] = {
    "krea2": {
        "source_edit": "Editing with Krea 2 Identity Edit",
    },
    "flux_kontext": {
        "source_edit": "Editing with Flux Kontext",
    },
    "qwen_image_edit": {
        "source_edit": "Editing with Qwen Edit",
    },
}


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def _routing_model_blob(model: dict | None) -> str:
    if not model:
        return ""
    parts = (
        model.get("engine_name"),
        model.get("name"),
        model.get("relative_path"),
        model.get("caption"),
    )
    return " ".join(str(p) for p in parts if p).lower()


def checkpoint_is_flux_kontext(model: dict | None, model_family: str) -> bool:
    """True when weights are Flux.1 Kontext edit models (not base Flux img2img)."""
    fam = (model_family or "").lower()
    if fam == "flux_kontext":
        return True
    blob = _routing_model_blob(model)
    if fam == "flux" and "kontext" in blob:
        return True
    hints = (
        "flux-kontext",
        "flux_kontext",
        "flux1-kontext",
        "flux.1-kontext",
        "kontext-dev",
        "flux.1 kontext",
    )
    return fam.startswith("flux") and any(h in blob for h in hints)


def checkpoint_is_flux_fill(model: dict | None, model_family: str) -> bool:
    """True when weights are Flux.1 Fill / inpaint checkpoints."""
    fam = (model_family or "").lower()
    if fam == "flux_fill":
        return True
    blob = _routing_model_blob(model)
    fill_hints = (
        "flux1-fill",
        "flux-fill",
        "flux.1-fill",
        "flux fill",
    )
    return any(h in blob for h in fill_hints)


@dataclass
class WorkflowRoute:
    plan_mode: str
    reference_role: str
    is_upscale_job: bool
    is_inpaint_job: bool
    input_path: str | None
    cn_selection: str
    cn_type: str
    edit_type: str
    workflow_mode: str | None
    route_label: str
    warnings: list[str] = field(default_factory=list)
    comfy_mode: str | None = None
    edit_task: str | None = None
    custom_tool_id: str | None = None
    outfit_auto_mask: bool = False


def _reference_role(job, studio_mode: str | None = None) -> str:
    explicit = _norm(getattr(job, "reference_role", None))
    if explicit in VALID_REFERENCE_ROLES:
        return explicit
    return infer_reference_role(job, studio_mode=studio_mode)


def route_label(reference_role: str, model_family: str = "") -> str:
    role = _norm(reference_role)
    family = (model_family or "").lower()
    family_labels = _FAMILY_ROUTE_LABELS.get(family, {})
    if role in family_labels:
        return family_labels[role]
    return _ROUTE_LABELS.get(role, "")


def plan_mode_for_job(job, studio_mode: str | None = None) -> str:
    """Resolve dry-run / studio plan mode from image role and legacy fields."""
    role = _reference_role(job, studio_mode=studio_mode)
    workflow_mode = _norm(getattr(job, "workflow_mode", None))
    edit_type = _norm(getattr(job, "edit_type", None))

    if role == "upscale":
        return "upscale"
    if role == "inpaint":
        return "inpaint"
    if role == "structure":
        return "generate"
    if role in {"restyle", "image_prompt"}:
        return "generate"
    if edit_type == "outpaint" or _norm(getattr(job, "edit_task", None)) == "extend":
        if workflow_mode != "generate":
            return "inpaint"
    if role == "source_edit":
        return "edit"

    if getattr(job, "inpaint_mask_path", None) or edit_type == "inpaint":
        if workflow_mode != "generate":
            return "inpaint"
    if workflow_mode == "generate" and getattr(job, "input_image", None):
        return "generate"
    if getattr(job, "input_image", None):
        return "edit"
    if getattr(job, "upscale_image", None):
        return "upscale"
    return "generate"


def plan_clear_fields_for_mode(mode: str) -> set[str]:
    """Settings fields to clear in dry-run proposed_patch per plan mode."""
    clear_fields: set[str] = set()
    if mode == "edit":
        clear_fields.update({"upscale_image", "upscale_method", "inpaint_mask_path"})
    elif mode == "inpaint":
        clear_fields.update({"upscale_image", "upscale_method"})
    elif mode == "upscale":
        clear_fields.update({"input_image", "inpaint_mask_path"})
    elif mode == "generate":
        clear_fields.update({"upscale_image", "upscale_method", "inpaint_mask_path"})
    return clear_fields


def resolve_input_routing(
    job,
    *,
    model: dict | None = None,
    model_family: str = "",
    studio_mode: str | None = None,
) -> WorkflowRoute:
    """Normalize cn_selection/cn_type/edit_type and input path from job state."""
    reference_role = _reference_role(job, studio_mode=studio_mode)
    explicit_input_path = getattr(job, "input_image", None)
    reference_image_path = getattr(job, "reference_image", None)
    upscale_input_path = getattr(job, "upscale_image", None)
    cn_selection = getattr(job, "cn_selection", None) or "None"
    cn_type = getattr(job, "cn_type", None) or "None"
    edit_type = getattr(job, "edit_type", "auto") or "auto"
    workflow_mode = getattr(job, "workflow_mode", None) or getattr(
        job, "comfy_workflow_mode", None
    )
    inpaint_mask_path = getattr(job, "inpaint_mask_path", None)
    wm = _norm(workflow_mode)
    is_outpaint_job = (
        _norm(edit_type) == "outpaint"
        or _norm(cn_type) == "outpaint"
        or wm == "outpaint"
        or _norm(getattr(job, "edit_task", None)) == "extend"
    )

    from dreamforge_auto_enhance import is_auto_enhance_job

    is_upscale_job = is_upscale_reference_role(job, studio_mode=studio_mode) and not is_auto_enhance_job(
        job
    )
    is_inpaint_job = (not is_outpaint_job) and (reference_role == "inpaint" or (
        reference_role not in {"restyle", "image_prompt", "upscale", "structure"}
        and (
            _norm(edit_type) == "inpaint"
            or _norm(cn_type) == "inpaint"
            or bool(inpaint_mask_path)
        )
        and wm != "generate"
    ))

    if is_outpaint_job:
        edit_type = "outpaint"
        cn_selection = "Custom..."
        cn_type = "outpaint"
        if not workflow_mode:
            workflow_mode = "outpaint"
            wm = "outpaint"
    elif is_inpaint_job:
        edit_type = "inpaint"
        cn_selection = "Custom..."
        cn_type = "inpaint"

    if reference_role == "image_prompt":
        input_path = explicit_input_path or reference_image_path or upscale_input_path
        if not wm:
            workflow_mode = "ipadapter"
            wm = "ipadapter"
    elif reference_role == "structure":
        input_path = reference_image_path or explicit_input_path
        cn_selection = "Custom..."
        structure_kind = _norm(
            getattr(job, "structure_type", None)
            or getattr(job, "cn_type", None)
            or "canny"
        )
        if structure_kind in {"", "none", "img2img", "upscale", "inpaint", "auto"}:
            structure_kind = "canny"
        cn_type = structure_kind
        if not wm:
            workflow_mode = "controlnet"
            wm = "controlnet"
        if _norm(edit_type) in {"", "none", "auto"}:
            edit_type = "auto"
    else:
        input_path = explicit_input_path or upscale_input_path
    warnings: list[str] = []

    if not input_path:
        if cn_selection == "Custom...":
            cn_selection = "None"
            cn_type = "None"
        if edit_type in ("kontext", "inpaint", "img2img", "qwen_edit", "outpaint"):
            edit_type = "auto"
    elif cn_selection == "None" and is_upscale_job:
        cn_selection = "Custom..."
        cn_type = "upscale"
    elif cn_selection == "None" and input_path:
        if reference_role == "restyle":
            cn_selection = "Custom..."
            cn_type = "img2img"
            if _norm(edit_type) in ("kontext", "qwen_edit"):
                edit_type = "auto"
        elif reference_role == "image_prompt":
            cn_selection = "None"
            cn_type = "None"
        elif reference_role == "source_edit" and (
            checkpoint_is_flux_kontext(model, model_family)
            or (model_family or "").lower() in {"qwen_image_edit", "krea2"}
        ):
            cn_selection = "None"
            cn_type = "None"
        elif (
            checkpoint_is_flux_kontext(model, model_family)
            or (wm == "generate" and _norm(edit_type) == "kontext")
        ):
            cn_selection = "None"
            cn_type = "None"
        elif (
            (model_family or "").lower() == "qwen_image_edit"
            or _norm(edit_type) == "qwen_edit"
        ) and not is_inpaint_job:
            cn_selection = "None"
            cn_type = "None"
        else:
            cn_selection = "Custom..."
            if edit_type not in ("auto", "kontext", "None", None, ""):
                cn_type = edit_type
            else:
                cn_type = "img2img"
    elif input_path and cn_selection == "Custom...":
        if is_upscale_job:
            cn_type = "upscale"
        elif reference_role == "restyle":
            cn_type = "img2img"
        elif reference_role == "structure":
            pass
        elif checkpoint_is_flux_kontext(model, model_family) and reference_role != "restyle":
            cn_selection = "None"
            cn_type = "None"
        elif _norm(cn_type) == "reference":
            if wm not in ("ipadapter", "reference_ipadapter"):
                cn_type = "img2img"
        elif edit_type not in ("auto", "None", None, ""):
            cn_type = edit_type

    plan_mode = plan_mode_for_job(job, studio_mode=studio_mode)
    custom_tool_id = str(getattr(job, "custom_tool_id", None) or "").strip()
    if studio_mode and _norm(studio_mode) != "toolbox":
        custom_tool_id = ""
    label = route_label(reference_role, model_family) or route_label(plan_mode, model_family)
    if _norm(getattr(job, "edit_task", None)) == "photo_restore":
        label = "Restoring photo"
    elif _norm(getattr(job, "edit_task", None)) == "outfit_transfer":
        label = "Transferring outfit"
    elif _norm(getattr(job, "edit_task", None)) == "cutout_compose":
        label = "Composing cutout"
    elif _norm(getattr(job, "edit_task", None)) == "portrait_master":
        label = "Portrait Master"

    return WorkflowRoute(
        plan_mode=plan_mode,
        reference_role=reference_role,
        is_upscale_job=is_upscale_job,
        is_inpaint_job=is_inpaint_job,
        input_path=input_path,
        cn_selection=cn_selection,
        cn_type=cn_type,
        edit_type=edit_type,
        workflow_mode=workflow_mode,
        route_label=label,
        warnings=warnings,
        edit_task=_norm(getattr(job, "edit_task", None)) or None,
        custom_tool_id=custom_tool_id or None,
        outfit_auto_mask=bool(getattr(job, "outfit_auto_mask", False)),
    )


IMAGE_PROMPT_FALLBACK_WARNING = (
    "IP-Adapter assets missing; using restyle (img2img) instead"
)


def should_coerce_image_prompt_to_restyle(
    route: WorkflowRoute,
    job,
    *,
    studio_mode: str | None = None,
) -> bool:
    """True when IP-Adapter cannot run and a safe img2img fallback is allowed."""
    role = _norm(route.reference_role)
    if role == "image_prompt":
        return True
    wm = _norm(route.workflow_mode)
    if wm in {"ipadapter", "reference_ipadapter"}:
        return True
    return False


def coerce_image_prompt_to_restyle_route(
    route: WorkflowRoute,
    job,
) -> WorkflowRoute:
    """Safe fallback when image_prompt cannot run IP-Adapter."""
    ref_path = (
        getattr(job, "reference_image", None)
        or getattr(job, "input_image", None)
        or route.input_path
    )
    warnings = list(route.warnings)
    if IMAGE_PROMPT_FALLBACK_WARNING not in warnings:
        warnings.append(IMAGE_PROMPT_FALLBACK_WARNING)
    return WorkflowRoute(
        plan_mode="generate",
        reference_role="restyle",
        is_upscale_job=False,
        is_inpaint_job=False,
        input_path=ref_path,
        cn_selection="Custom...",
        cn_type="img2img",
        edit_type="auto",
        workflow_mode="generate",
        route_label=route_label("restyle", ""),
        warnings=warnings,
        edit_task=route.edit_task,
    )


def resolve_comfy_workflow_mode(
    route: WorkflowRoute,
    *,
    model: dict,
    model_family: str,
    input_filename: str | None,
) -> str:
    if getattr(route, "edit_task", None) == "photo_restore":
        return "photo_restore"
    if getattr(route, "edit_task", None) == "portrait_master":
        return "portrait_master"
    if getattr(route, "edit_task", None) == "cutout_compose":
        return "cutout_compose"
    if (
        getattr(route, "edit_task", None) == "outfit_transfer"
        and bool(getattr(route, "outfit_auto_mask", False))
    ):
        return "outfit_transfer"
    if str(getattr(route, "custom_tool_id", None) or "").strip():
        return "custom_tool"

    from dreamforge_comfy_workflow_import import comfy_workflow_mode

    return comfy_workflow_mode(
        input_filename=input_filename,
        cn_type=str(route.cn_type or ""),
        model=model,
        model_family=model_family,
        checkpoint_is_flux_kontext=checkpoint_is_flux_kontext,
        workflow_mode=str(route.workflow_mode or "") or None,
        edit_type=str(route.edit_type or "") or None,
    )
