"""Ideogram 4 Comfy workflow routing (txt2img, img2img, inpaint)."""

from __future__ import annotations

from typing import Any

IDEOGRAM4_WORKFLOW_TXT2IMG = "txt2img"
IDEOGRAM4_WORKFLOW_IMG2IMG = "img2img"
IDEOGRAM4_WORKFLOW_INPAINT = "inpaint"

_PLANNED_WORKFLOWS = frozenset(
    {
        IDEOGRAM4_WORKFLOW_TXT2IMG,
        IDEOGRAM4_WORKFLOW_IMG2IMG,
        IDEOGRAM4_WORKFLOW_INPAINT,
    }
)
_IMPLEMENTED_WORKFLOWS = _PLANNED_WORKFLOWS
_EDIT_WORKFLOWS = frozenset({IDEOGRAM4_WORKFLOW_IMG2IMG, IDEOGRAM4_WORKFLOW_INPAINT})


def resolve_ideogram4_workflow_kind(
    *,
    workflow_mode: str | None,
    input_filename: str | None,
    mask_filename: str | None,
    edit_type: str | None = None,
) -> str:
    """Map studio job parameters to an Ideogram 4 workflow kind."""
    mode = str(workflow_mode or "generate").strip().lower()
    edit = str(edit_type or "").strip().lower()
    has_image = bool(input_filename)
    has_mask = bool(mask_filename)

    if mode == "inpaint" or edit == "inpaint" or (has_mask and has_image):
        return IDEOGRAM4_WORKFLOW_INPAINT
    if has_image and mode in {"edit", "img2img", "qwen_edit", "kontext", "face_detail", "controlnet", "outpaint"}:
        return IDEOGRAM4_WORKFLOW_IMG2IMG
    if has_image:
        return IDEOGRAM4_WORKFLOW_IMG2IMG
    return IDEOGRAM4_WORKFLOW_TXT2IMG


def ideogram4_workflow_supported(kind: str, *, object_info: dict[str, Any] | None = None) -> bool:
    if kind not in _IMPLEMENTED_WORKFLOWS:
        return False
    if kind in _EDIT_WORKFLOWS:
        from dreamforge_comfy_ideogram4 import ideogram4_comfy_ready, ideogram4_edit_disabled

        if ideogram4_edit_disabled():
            return False
    if object_info:
        from dreamforge_comfy_ideogram4 import ideogram4_comfy_ready

        return ideogram4_comfy_ready(object_info, kind)
    return True


def ideogram4_workflow_planned(kind: str) -> bool:
    return kind in _PLANNED_WORKFLOWS


def ideogram4_workflow_unsupported_error(
    kind: str,
    *,
    job_id: str | None = None,
    missing_nodes: list[str] | None = None,
) -> dict[str, Any]:
    from dreamforge_comfy_ideogram4 import ideogram4_edit_disabled
    from dreamforge_errors import missing_custom_node_pack, unsupported_workflow_class

    if missing_nodes:
        return missing_custom_node_pack(
            "ComfyUI (v0.24.1+ Ideogram nodes)",
            job_id=job_id,
            nodes=tuple(missing_nodes),
        )

    labels = {
        IDEOGRAM4_WORKFLOW_INPAINT: "inpaint",
        IDEOGRAM4_WORKFLOW_IMG2IMG: "image edit",
    }
    label = labels.get(kind, kind)
    if kind in _EDIT_WORKFLOWS and ideogram4_edit_disabled():
        detail = (
            f"Ideogram 4 {label} is disabled (DREAMFORGE_DISABLE_IDEOGRAM4_EDIT=1). "
            "Remove that variable to enable image edit and inpaint workflows."
        )
        return unsupported_workflow_class(f"ideogram4_{kind}", detail, job_id=job_id)

    detail = f"Ideogram 4 {label} is not available in this DreamForge install."
    return unsupported_workflow_class(f"ideogram4_{kind}", detail, job_id=job_id)


def build_ideogram4_comfy_graph(kind: str, args: dict[str, Any]) -> dict[str, Any]:
    """Build Comfy API graph for the requested Ideogram 4 workflow kind."""
    if kind == IDEOGRAM4_WORKFLOW_TXT2IMG:
        from dreamforge_comfy_workflows import comfy_ideogram4_txt2img

        return comfy_ideogram4_txt2img(args)
    if kind == IDEOGRAM4_WORKFLOW_IMG2IMG:
        from dreamforge_comfy_workflows import comfy_ideogram4_img2img

        return comfy_ideogram4_img2img(args)
    if kind == IDEOGRAM4_WORKFLOW_INPAINT:
        from dreamforge_comfy_workflows import comfy_ideogram4_inpaint

        return comfy_ideogram4_inpaint(args)
    raise ValueError(f"Unknown Ideogram 4 workflow kind: {kind}")


def resolve_ideogram4_uncond_unet(*, vram_tier: str | None = None) -> str:
    """Prefer NVFP4 unconditional UNet on tight VRAM when the file is installed."""
    from pathlib import Path

    from _paths import PROJECT_ROOT

    tier = (vram_tier or "16gb").lower()
    candidates: list[str] = []
    if tier in {"16gb", "8gb", "5gb"}:
        candidates.append("ideogram4_unconditional_nvfp4_mixed.safetensors")
    candidates.append("ideogram4_unconditional_fp8_scaled.safetensors")

    roots = (
        PROJECT_ROOT / "models" / "unet",
        PROJECT_ROOT / "models" / "diffusion_models",
    )
    for name in candidates:
        for root in roots:
            if (root / name).is_file():
                return name

    try:
        from dreamforge_cli_inventory import list_model_inventory

        for item in list_model_inventory().get("categories", {}).get("unet", []):
            rel = str(item.get("relative_path") or item.get("name") or "").replace("\\", "/")
            base = Path(rel).name
            if base in candidates:
                return base
        for item in list_model_inventory().get("categories", {}).get("diffusion_models", []):
            rel = str(item.get("relative_path") or item.get("name") or "").replace("\\", "/")
            base = Path(rel).name
            if base in candidates:
                return base
    except Exception:
        pass
    return "ideogram4_unconditional_fp8_scaled.safetensors"
