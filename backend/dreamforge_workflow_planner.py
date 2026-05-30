"""Intent-level workflow template planner for DreamForge.

The templates here are first-party DreamForge blueprints derived from:
- official ComfyUI examples/docs
- the local `.research/comfy_workflow_research` analyzer output
- Krita AI Diffusion-style managed Comfy routing and dependency manifests

Downloaded workflows are research inputs only. DreamForge emits its own local
Comfy API graphs/builders from these stable template categories.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


LOCAL_IMAGE_BACKEND = "local_comfy"


@dataclass(frozen=True)
class WorkflowTemplateSpec:
    id: str
    label: str
    operation: str
    mode: str
    summary: str
    builder: str
    node_pattern: list[str]
    required_inputs: list[str] = field(default_factory=list)
    optional_inputs: list[str] = field(default_factory=list)
    required_models: list[str] = field(default_factory=list)
    required_node_packs: list[str] = field(default_factory=list)
    optional_nodes: list[str] = field(default_factory=list)
    krita_alignment: str = ""
    research_basis: list[str] = field(default_factory=list)
    security_note: str = "First-party DreamForge template; do not execute downloaded workflows directly."

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


TEMPLATE_REGISTRY: dict[str, WorkflowTemplateSpec] = {
    "txt2img_basic": WorkflowTemplateSpec(
        id="txt2img_basic",
        label="Text to Image",
        operation="generate_image",
        mode="generate",
        summary="Prompt, model loader, CLIP encode, latent image, sampler, VAE decode, save.",
        builder="comfy_txt2img_basic | comfy_flux_dev_txt2img",
        node_pattern=["CheckpointLoaderSimple/UNETLoader", "CLIPTextEncode", "EmptyLatentImage/EmptySD3LatentImage", "KSampler", "VAEDecode", "SaveImage"],
        required_inputs=["prompt", "width", "height", "model"],
        required_models=["checkpoint_or_unet", "clip", "vae"],
        research_basis=["official_text_to_image", "ComfyUI_examples", "workflow_research:txt2img"],
    ),
    "img2img_restyle": WorkflowTemplateSpec(
        id="img2img_restyle",
        label="Image to Image Restyle",
        operation="edit_image",
        mode="edit",
        summary="Load source image, VAE encode, low/medium denoise sampler, decode, save.",
        builder="comfy_img2img_basic",
        node_pattern=["LoadImage", "VAEEncode", "CLIPTextEncode", "KSampler(denoise<1)", "VAEDecode", "SaveImage"],
        required_inputs=["input_image", "prompt", "model"],
        optional_inputs=["edit_strength"],
        required_models=["checkpoint_or_unet", "clip", "vae"],
        research_basis=["official_image_to_image", "workflow_research:img2img"],
    ),
    "flux_kontext_edit": WorkflowTemplateSpec(
        id="flux_kontext_edit",
        label="Contextual Image Edit",
        operation="edit_image",
        mode="edit",
        summary="Krita-style Flux Kontext edit using scaled source/reference latent conditioning.",
        builder="comfy_flux_kontext_edit",
        node_pattern=["LoadImage", "FluxKontextImageScale", "VAEEncode", "CLIPTextEncode", "FluxGuidance", "ReferenceLatent", "KSampler", "VAEDecode", "SaveImage"],
        required_inputs=["input_image", "prompt"],
        optional_inputs=["reference_images", "edit_strength"],
        required_models=["flux_kontext_unet", "clip_l", "t5", "ae_vae"],
        krita_alignment="Matches Krita AI Diffusion managed Comfy/Kontext recipe and split UNET+CLIP+VAE loading.",
        research_basis=["krita_ai_diffusion", "ComfyUI_examples:flux_kontext", "workflow_research:flux"],
    ),
    "inpaint_repair": WorkflowTemplateSpec(
        id="inpaint_repair",
        label="Inpaint / Remove Object",
        operation="inpaint",
        mode="inpaint",
        summary="Load image and mask, grow/feather mask, VAE encode for inpaint, sample, decode, composite/preserve outside mask.",
        builder="comfy_inpaint_basic + composite_inpaint_result",
        node_pattern=["LoadImage", "ImageToMask/LoadImageMask", "VAEEncodeForInpaint", "CLIPTextEncode", "KSampler", "VAEDecode", "SaveImage"],
        required_inputs=["input_image", "mask", "prompt"],
        optional_inputs=["grow_mask_by", "feather", "preserve_unmasked_pixels"],
        required_models=["inpaint_capable_checkpoint_or_flux_fill", "clip", "vae"],
        optional_nodes=["comfyui-inpaint-nodes", "comfyui_controlnet_aux"],
        krita_alignment="Uses Krita-style inpaint grow/feather defaults and optional inpaint helper resources.",
        research_basis=["official_inpaint", "ComfyUI_examples:inpaint", "workflow_research:inpaint"],
    ),
    "outpaint_canvas_extend": WorkflowTemplateSpec(
        id="outpaint_canvas_extend",
        label="Outpaint / Canvas Extend",
        operation="outpaint",
        mode="inpaint",
        summary="Pad image in requested direction, generate an expansion mask, then run inpaint/fill.",
        builder="comfy_outpaint_basic",
        node_pattern=["LoadImage", "ImagePadForOutpaint", "Mask", "VAEEncodeForInpaint", "KSampler", "VAEDecode", "ImageCompositeMasked", "SaveImage"],
        required_inputs=["input_image", "direction_or_canvas_size", "prompt"],
        optional_inputs=["feather", "grow_mask_by"],
        required_models=["checkpoint_or_unet", "clip", "vae"],
        research_basis=["official_outpaint", "ComfyUI_examples:outpaint", "workflow_research:compositing"],
    ),
    "upscale_basic": WorkflowTemplateSpec(
        id="upscale_basic",
        label="Upscale",
        operation="upscale",
        mode="upscale",
        summary="Load image, load local upscale model, upscale image, save.",
        builder="comfy_upscale_basic",
        node_pattern=["LoadImage", "UpscaleModelLoader", "ImageUpscaleWithModel", "SaveImage"],
        required_inputs=["input_image"],
        optional_inputs=["scale"],
        required_models=["upscale_model"],
        krita_alignment="Uses DreamForge/Krita-style upscaler catalog aliases and local `upscale_models` paths.",
        research_basis=["official_upscale", "workflow_research:upscale"],
    ),
    "hires_two_pass": WorkflowTemplateSpec(
        id="hires_two_pass",
        label="Two Pass / Hires Fix",
        operation="hires_fix",
        mode="generate",
        summary="Generate smaller first pass, upscale latent or pixels, then refine with low denoise.",
        builder="comfy_hires_two_pass",
        node_pattern=["FirstPassSampler", "LatentUpscale/ImageUpscaleWithModel", "VAEEncode", "SecondPassSampler(denoise<0.5)", "VAEDecode", "SaveImage"],
        required_inputs=["prompt", "model", "target_size"],
        optional_inputs=["upscale_model", "second_pass_denoise"],
        required_models=["checkpoint_or_unet", "clip", "vae"],
        research_basis=["ComfyUI_examples:2_pass_txt2img", "workflow_research:upscale"],
    ),
    "controlnet_structure": WorkflowTemplateSpec(
        id="controlnet_structure",
        label="Structure Control",
        operation="controlnet_structure",
        mode="generate",
        summary="Use pose/depth/canny/scribble/lineart control image to preserve layout or structure.",
        builder="comfy_controlnet_basic",
        node_pattern=["LoadImage", "ControlNetLoader", "ControlNetApply", "CLIPTextEncode", "KSampler", "VAEDecode", "SaveImage"],
        required_inputs=["prompt", "control_image"],
        optional_inputs=["preprocessor", "control_weight", "start_percent", "end_percent"],
        required_models=["controlnet_model", "checkpoint_or_unet"],
        optional_nodes=["comfyui_controlnet_aux"],
        research_basis=["ComfyUI_examples:controlnet", "workflow_research:controlnet"],
    ),
    "reference_ipadapter": WorkflowTemplateSpec(
        id="reference_ipadapter",
        label="Reference / IPAdapter",
        operation="reference_guidance",
        mode="edit",
        summary="Use reference image features for style, identity, product, or composition consistency.",
        builder="comfy_ipadapter_reference",
        node_pattern=["LoadImage", "CLIPVisionLoader", "IPAdapterModelLoader", "IPAdapter", "KSampler", "VAEDecode", "SaveImage"],
        required_inputs=["prompt", "reference_images"],
        optional_inputs=["reference_weight", "composition_weight"],
        required_models=["ipadapter_model", "clip_vision"],
        required_node_packs=["ComfyUI_IPAdapter_plus"],
        krita_alignment="Matches Krita dependency catalog for IPAdapter custom nodes, but remains optional.",
        research_basis=["workflow_research:reference_ipadapter", "krita_ai_diffusion"],
    ),
    "area_composition": WorkflowTemplateSpec(
        id="area_composition",
        label="Area Composition",
        operation="composite_layers",
        mode="composite",
        summary="Use masks/areas to place subjects, backgrounds, product cutouts, or regional prompts.",
        builder="comfy_area_composition",
        node_pattern=["CLIPTextEncode", "ConditioningSetArea", "ConditioningCombine", "KSampler", "VAEDecode", "SaveImage"],
        required_inputs=["prompt", "regions_or_layers"],
        optional_inputs=["masks", "layer_images", "region_prompts"],
        research_basis=["ComfyUI_examples:area_composition", "workflow_research:compositing"],
    ),
    "face_detail_optional": WorkflowTemplateSpec(
        id="face_detail_optional",
        label="Face / Detail Repair",
        operation="face_detail",
        mode="edit",
        summary="Impact Pack FaceDetailer pass for face, hand, and subject detail repair on an existing image.",
        builder="comfy_face_detail_basic",
        node_pattern=["LoadImage", "UltralyticsDetectorProvider", "SAMLoader", "FaceDetailer", "SaveImage"],
        required_inputs=["input_image", "prompt"],
        optional_inputs=["face_mask", "detail_prompt", "detail_target", "sam_model"],
        required_models=["checkpoint_or_unet", "bbox_detector"],
        required_node_packs=["ComfyUI-Impact-Pack", "ComfyUI-Impact-Subpack"],
        research_basis=["workflow_research:face_detail", "community_workflows", "ComfyUI-Impact-Pack"],
    ),
    "arabic_text_composite": WorkflowTemplateSpec(
        id="arabic_text_composite",
        label="Exact Text / Poster Composite",
        operation="text_integrate",
        mode="composite",
        summary="Render exact text deterministically, then composite/blend/integrate with local diffusion if requested.",
        builder="arabic_poster_pipeline + planned:first_party_text_integrate",
        node_pattern=["DeterministicTextRender", "Mask", "ImageCompositeMasked", "OptionalControlNet", "OptionalKontextIntegrate", "Upscale"],
        required_inputs=["text", "scene_prompt"],
        optional_inputs=["font", "position", "brand_colors", "mask"],
        required_models=["optional_local_generation_model"],
        research_basis=["DreamForge Arabic pipeline", "workflow_research:compositing"],
    ),
}


def list_workflow_templates() -> list[dict[str, Any]]:
    return [spec.to_dict() for spec in TEMPLATE_REGISTRY.values()]


def _contains_any(text: str, words: tuple[str, ...]) -> bool:
    return any(word in text for word in words)


def resolve_operations_from_intent(
    intent: str,
    *,
    has_image: bool = False,
    has_mask: bool = False,
    has_references: bool = False,
) -> list[str]:
    text = (intent or "").lower()
    operations: list[str] = []
    if _contains_any(text, ("outpaint", "expand canvas", "extend canvas", "extend background", "make wider", "make taller")):
        operations.append("outpaint")
    if _contains_any(text, ("remove", "erase", "delete", "cleanup", "clean up", "background people")):
        operations.append("remove_object")
    if has_mask or _contains_any(text, ("mask", "inpaint", "replace this area", "fix this area")):
        operations.append("inpaint")
    if _contains_any(text, ("smile", "face", "eyes", "hands", "expression", "detail", "repair")):
        operations.append("face_detail" if _contains_any(text, ("detail", "repair", "hands")) else "face_edit")
    if _contains_any(text, ("controlnet", "pose", "depth", "canny", "edge", "lineart", "scribble", "preserve layout", "same pose")):
        operations.append("controlnet_structure")
    if has_references or _contains_any(text, ("reference", "same character", "same product", "identity", "style reference", "ipadapter")):
        operations.append("reference_guidance")
    if _contains_any(text, ("composite", "layer", "product shot", "cutout", "background replacement", "replace background")):
        operations.append("composite_layers")
    if _contains_any(text, ("arabic", "exact text", "add text", "typography", "logo", "headline")):
        operations.append("text_integrate")
    if _contains_any(text, ("cinematic", "cyberpunk", "anime", "style", "rainy", "rain", "color grade", "lighting", "restyle")):
        operations.append("style_transfer")
    if _contains_any(text, ("hires fix", "two pass", "second pass", "high quality final")):
        operations.append("hires_fix")
    elif _contains_any(text, ("upscale", "4k", "8k", "high resolution", "hi-res", "hires", "print")):
        operations.append("upscale")
    if not operations:
        operations.append("edit_image" if has_image else "generate_image")
    return _dedupe(operations)


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def template_ids_for_operations(
    operations: list[str],
    *,
    has_image: bool = False,
    has_mask: bool = False,
) -> list[str]:
    ids: list[str] = []
    for op in operations:
        if op == "generate_image":
            ids.append("txt2img_basic")
        elif op in ("edit_image", "style_transfer", "face_edit"):
            ids.append("flux_kontext_edit" if has_image else "txt2img_basic")
        elif op in ("remove_object", "inpaint"):
            ids.append("inpaint_repair" if has_mask else "flux_kontext_edit")
        elif op == "outpaint":
            ids.append("outpaint_canvas_extend")
        elif op == "upscale":
            ids.append("upscale_basic")
        elif op == "hires_fix":
            ids.append("hires_two_pass")
        elif op == "controlnet_structure":
            ids.append("controlnet_structure")
        elif op == "reference_guidance":
            ids.append("reference_ipadapter" if not has_image else "flux_kontext_edit")
        elif op == "composite_layers":
            ids.append("area_composition")
        elif op == "face_detail":
            ids.append("face_detail_optional")
        elif op == "text_integrate":
            ids.append("arabic_text_composite")
    return _dedupe(ids)


def build_live_workflow_blueprint(
    intent: str,
    *,
    operations: list[str] | None = None,
    has_image: bool = False,
    has_mask: bool = False,
    has_references: bool = False,
    current_settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    settings = current_settings or {}
    ops = operations or resolve_operations_from_intent(
        intent,
        has_image=has_image,
        has_mask=has_mask,
        has_references=has_references,
    )
    template_ids = template_ids_for_operations(ops, has_image=has_image, has_mask=has_mask)
    templates = [TEMPLATE_REGISTRY[item].to_dict() for item in template_ids if item in TEMPLATE_REGISTRY]
    required_inputs = _dedupe([value for spec in templates for value in spec.get("required_inputs", [])])
    required_models = _dedupe([value for spec in templates for value in spec.get("required_models", [])])
    optional_nodes = _dedupe([value for spec in templates for value in spec.get("optional_nodes", [])])
    required_node_packs = _dedupe([value for spec in templates for value in spec.get("required_node_packs", [])])
    node_patterns = _dedupe([value for spec in templates for value in spec.get("node_pattern", [])])
    readiness = assess_workflow_readiness(
        template_ids,
        required_inputs=required_inputs,
        required_models=required_models,
        required_node_packs=required_node_packs,
        current_settings=settings,
        has_image=has_image,
        has_mask=has_mask,
        has_references=has_references,
    )
    warnings: list[str] = []
    if "mask" in required_inputs and not has_mask:
        warnings.append("A mask or region selection is required for precise inpaint/outpaint.")
    if required_node_packs:
        warnings.append("Some stages require approved custom node packs before they can run.")
    if optional_nodes:
        warnings.append("Some advanced stages require optional custom nodes and must be approved before installation/use.")
    warnings.extend(readiness["warnings"])
    return {
        "schema_version": "1.0",
        "status": "planned",
        "image_backend": LOCAL_IMAGE_BACKEND,
        "local_only": True,
        "operations": ops,
        "template_ids": template_ids,
        "templates": templates,
        "required_inputs": required_inputs,
        "required_models": required_models,
        "optional_nodes": optional_nodes,
        "required_node_packs": required_node_packs,
        "node_patterns": node_patterns,
        "readiness": readiness,
        "warnings": warnings,
        "research_basis": [
            "official ComfyUI examples/docs",
            "Krita AI Diffusion managed Comfy recipes/resources",
            ".research/comfy_workflow_research/ANALYSIS.md",
        ],
    }


def _inventory_categories() -> dict[str, list[dict[str, Any]]]:
    try:
        from dreamforge_cli_inventory import list_model_inventory

        return list_model_inventory().get("categories", {})
    except Exception:
        return {}


def _has_category_item(categories: dict[str, list[dict[str, Any]]], category: str, hints: tuple[str, ...] = ()) -> bool:
    items = categories.get(category, [])
    if not hints:
        return bool(items)
    for item in items:
        text = " ".join(str(item.get(key, "")) for key in ("name", "relative_path", "stem")).lower()
        if any(hint.lower() in text for hint in hints):
            return True
    return False


def _input_present(name: str, settings: dict[str, Any], *, has_image: bool, has_mask: bool, has_references: bool) -> bool:
    if name in {"prompt", "scene_prompt"}:
        return bool(settings.get("prompt") or settings.get("instruction"))
    if name in {"input_image", "control_image"}:
        return has_image or bool(settings.get("input_image") or settings.get("upscale_image") or settings.get("control_image"))
    if name == "mask":
        return has_mask or bool(settings.get("inpaint_mask_path") or settings.get("mask"))
    if name == "reference_images":
        return has_references or bool(settings.get("reference_images") or settings.get("control_images"))
    if name == "upscale_model":
        return True
    if name in {"width", "height", "model", "target_size", "direction_or_canvas_size"}:
        return True
    if name == "regions_or_layers":
        return bool(
            settings.get("regions_or_layers")
            or settings.get("region_prompt")
            or settings.get("region_prompts")
            or settings.get("region_prompts_json")
            or settings.get("composition_regions")
            or settings.get("layer_images")
            or settings.get("composition")
        )
    if name == "text":
        return bool(settings.get("text") or settings.get("headline") or settings.get("logo_text"))
    return True


def assess_workflow_readiness(
    template_ids: list[str],
    *,
    required_inputs: list[str],
    required_models: list[str],
    required_node_packs: list[str] | None = None,
    current_settings: dict[str, Any] | None = None,
    has_image: bool = False,
    has_mask: bool = False,
    has_references: bool = False,
) -> dict[str, Any]:
    from dreamforge_model_registry import ModelCapabilities, get_families_for_capability
    settings = current_settings or {}
    categories = _inventory_categories()
    missing_inputs = [
        item
        for item in required_inputs
        if not _input_present(item, settings, has_image=has_image, has_mask=has_mask, has_references=has_references)
    ]
    missing_models: list[str] = []
    
    def _has_capable_model(cats: tuple[str, ...], allowed_fams: list[str]) -> bool:
        try:
            from dreamforge_cli_inventory import infer_model_family
        except Exception:
            infer_model_family = None
        for cat in cats:
            for item in categories.get(cat, []):
                fam = item.get("family")
                if not fam and infer_model_family:
                    fam = infer_model_family(str(item.get("name") or item.get("relative_path") or ""))
                if fam and fam in allowed_fams:
                    return True
        return False

    if "checkpoint_or_unet" in required_models:
        fams = get_families_for_capability(ModelCapabilities.TEXT_TO_IMAGE) + get_families_for_capability(ModelCapabilities.IMAGE_TO_IMAGE)
        if not _has_capable_model(("checkpoints", "diffusion_models", "unet"), fams):
            missing_models.append("checkpoint_or_unet")
            
    if "flux_kontext_unet" in required_models:
        fams = get_families_for_capability(ModelCapabilities.KONTEXT_EDIT)
        if not _has_capable_model(("checkpoints", "diffusion_models", "unet"), fams):
            missing_models.append("flux_kontext_unet")
            
    if "inpaint_capable_checkpoint_or_flux_fill" in required_models:
        fams = get_families_for_capability(ModelCapabilities.INPAINT)
        if not _has_capable_model(("checkpoints", "diffusion_models", "unet"), fams):
            missing_models.append("inpaint_capable_checkpoint_or_flux_fill")
    if "controlnet_model" in required_models and not _has_category_item(categories, "controlnet"):
        missing_models.append("controlnet_model")
    if "upscale_model" in required_models and not _has_category_item(categories, "upscale_models"):
        missing_models.append("upscale_model")
    if "clip_l" in required_models and not (_has_category_item(categories, "clip", ("clip_l",)) or _has_category_item(categories, "text_encoders", ("clip_l",))):
        missing_models.append("clip_l")
    if "t5" in required_models and not (_has_category_item(categories, "clip", ("t5",)) or _has_category_item(categories, "text_encoders", ("t5",))):
        missing_models.append("t5")
    if "ae_vae" in required_models and not _has_category_item(categories, "vae", ("ae",)):
        missing_models.append("ae_vae")
    if "ipadapter_model" in required_models and not _has_category_item(categories, "ipadapter"):
        missing_models.append("ipadapter_model")
    if "clip_vision" in required_models and not _has_category_item(categories, "clip_vision"):
        missing_models.append("clip_vision")
    if "bbox_detector" in required_models:
        bbox_dir = _models_root_hint() / "ultralytics" / "bbox"
        if not bbox_dir.is_dir() or not any(bbox_dir.glob("*.pt")):
            missing_models.append("bbox_detector")
    optional_nodes = _dedupe(
        [
            node
            for template_id in template_ids
            for node in TEMPLATE_REGISTRY.get(template_id, WorkflowTemplateSpec("", "", "", "", "", "", [])).optional_nodes
        ]
    )
    missing_node_packs = [
        pack for pack in (required_node_packs or []) if not custom_node_pack_present(pack)
    ]
    warnings: list[str] = []
    if missing_inputs:
        warnings.append(f"Missing required workflow input(s): {', '.join(missing_inputs)}.")
    if missing_models:
        warnings.append(f"Missing local model resource(s): {', '.join(missing_models)}.")
    if optional_nodes:
        warnings.append(f"Optional custom node pack(s) require approval before use: {', '.join(optional_nodes)}.")
    if missing_node_packs:
        warnings.append(f"Required custom node pack(s) not installed: {', '.join(missing_node_packs)}.")
    recommended_actions = _recommended_actions(
        missing_models=_dedupe(missing_models),
        missing_node_packs=missing_node_packs,
        optional_nodes=optional_nodes,
        template_ids=template_ids,
        current_settings=settings,
    )
    return {
        "ready": not missing_inputs and not missing_models and not missing_node_packs,
        "missing_inputs": missing_inputs,
        "missing_models": _dedupe(missing_models),
        "missing_node_packs": missing_node_packs,
        "optional_nodes": optional_nodes,
        "recommended_actions": recommended_actions,
        "warnings": warnings,
        "checked_models_root": str(_models_root_hint()),
    }


def _recommended_actions(
    *,
    missing_models: list[str],
    missing_node_packs: list[str],
    optional_nodes: list[str],
    template_ids: list[str],
    current_settings: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    settings = current_settings or {}
    try:
        from dreamforge_krita_recipes import COMFY_INSTALL_RECIPE

        known_packs = {
            entry["id"]: entry
            for entry in COMFY_INSTALL_RECIPE.get("required_custom_nodes", [])
            + COMFY_INSTALL_RECIPE.get("optional_custom_nodes", [])
        }
    except Exception:
        known_packs = {}
    for pack in missing_node_packs:
        meta = known_packs.get(pack, {})
        actions.append(
            {
                "action": "install_custom_node_pack",
                "pack_id": pack,
                "url": meta.get("url", ""),
                "version": meta.get("version"),
                "reason": meta.get("reason", "Required for this workflow template"),
            }
        )
    companion_entries = _downloadable_resource_entries(
        missing_models=missing_models,
        template_ids=template_ids,
        current_settings=settings,
    )
    if companion_entries:
        actions.append(
            {
                "action": "download_model_companions",
                "missing": companion_entries,
                "hint": f"Download {len(companion_entries)} local workflow asset(s) after user approval.",
                "requires_approval": True,
            }
        )
    companion_resources = {entry.get("resource") for entry in companion_entries}
    model_actions = {
        "controlnet_model": {
            "action": "download_model",
            "category": "controlnet",
            "hint": "Place a ControlNet model under models/controlnet/ (see Krita/DreamForge resource catalog).",
        },
        "ipadapter_model": {
            "action": "download_model",
            "category": "ipadapter",
            "hint": "Install an IP-Adapter weight under models/ipadapter/.",
        },
        "clip_vision": {
            "action": "download_model",
            "category": "clip_vision",
            "hint": "Install a CLIP Vision model under models/clip_vision/.",
        },
        "bbox_detector": {
            "action": "download_model",
            "category": "ultralytics/bbox",
            "hint": "Install YOLO bbox weights under models/ultralytics/bbox/ (e.g. face_yolov8m.pt).",
        },
        "upscale_model": {
            "action": "download_model",
            "category": "upscale_models",
            "hint": "Install an upscaler under models/upscale_models/ or use DreamForge upscaler catalog.",
        },
        "flux_kontext_unet": {
            "action": "download_model",
            "category": "diffusion_models",
            "hint": "Install a Flux Kontext UNet/checkpoint (Krita-compatible names).",
        },
        "checkpoint_or_unet": {
            "action": "download_model",
            "category": "checkpoints",
            "hint": "Install a checkpoint or diffusion model in models/checkpoints/ or models/diffusion_models/.",
        },
    }
    for item in missing_models:
        if item in companion_resources:
            continue
        payload = dict(model_actions.get(item, {"action": "download_model", "category": item, "hint": item}))
        payload.setdefault("resource", item)
        actions.append(payload)
    if "face_detail_optional" in template_ids and optional_nodes:
        actions.append(
            {
                "action": "approve_optional_nodes",
                "nodes": optional_nodes,
                "hint": "Face/detail repair requires optional Impact Pack nodes and explicit approval.",
            }
        )
    if not actions and "arabic_text_composite" in template_ids:
        actions.append(
            {
                "action": "run_arabic_poster_pipeline",
                "hint": "Exact text workflows can use the local arabic_poster_pipeline for deterministic typography.",
            }
        )
    return actions


def _downloadable_resource_entries(
    *,
    missing_models: list[str],
    template_ids: list[str],
    current_settings: dict[str, Any],
) -> list[dict[str, Any]]:
    try:
        from dreamforge_companion_download import enrich_missing_dependency
        from dreamforge_krita_resources import MODELS_ROOT, STUDIO_RESOURCE_SOURCES, resolve_upscaler
    except Exception:
        return []

    def entry(resource_id: str, resource: str) -> dict[str, Any] | None:
        source = STUDIO_RESOURCE_SOURCES.get(resource_id)
        if not source:
            return None
        relative = source.get("relative", "")
        if not relative:
            return None
        payload = {
            "id": resource_id,
            "name": Path(relative).name,
            "relative": relative,
            "expected_path": str(MODELS_ROOT / relative),
            "url": source.get("url", ""),
            "min_bytes": source.get("min_bytes", 1024 * 1024),
            "resource": resource,
            "template_ids": list(template_ids),
        }
        return enrich_missing_dependency(payload)

    wanted: list[tuple[str, str]] = []
    missing = set(missing_models)
    if "upscale_model" in missing:
        try:
            upscaler = resolve_upscaler(current_settings.get("upscale_method"))
            filename = upscaler.get("filename", "")
        except Exception:
            filename = ""
        match = next(
            (
                resource_id
                for resource_id, source in STUDIO_RESOURCE_SOURCES.items()
                if source.get("relative", "").endswith(filename)
            ),
            "upscaler_omnisr_2x",
        )
        wanted.append((match, "upscale_model"))
    if "flux_kontext_unet" in missing:
        wanted.append(("diffusion_flux_kontext_fp8_scaled", "flux_kontext_unet"))
    if "ipadapter_model" in missing:
        wanted.append(("ipadapter_sdxl_vith", "ipadapter_model"))
    if "clip_vision" in missing:
        wanted.append(("clip_vision_ipadapter_vith", "clip_vision"))
    if "controlnet_model" in missing:
        cn_type = str(
            current_settings.get("cn_type")
            or current_settings.get("controlnet_type")
            or current_settings.get("preprocessor")
            or ""
        ).lower()
        if "pose" in cn_type or "openpose" in cn_type:
            wanted.append(("controlnet_pose_sd15", "controlnet_model"))
        elif "canny" in cn_type:
            wanted.append(("controlnet_canny_sd15", "controlnet_model"))
        elif "depth" in cn_type:
            wanted.append(("controlnet_depth_sd15", "controlnet_model"))
        else:
            wanted.append(("controlnet_sdxl_union", "controlnet_model"))

    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for resource_id, resource in wanted:
        if resource_id in seen:
            continue
        item = entry(resource_id, resource)
        if item:
            entries.append(item)
            seen.add(resource_id)
    return entries


def _models_root_hint() -> Path:
    try:
        from dreamforge_cli_inventory import MODELS_ROOT

        return Path(MODELS_ROOT)
    except Exception:
        return Path("backend/models")


def _recipe_entry_for_pack(pack_id: str) -> dict[str, Any] | None:
    try:
        from dreamforge_krita_recipes import COMFY_INSTALL_RECIPE

        for entry in COMFY_INSTALL_RECIPE.get("required_custom_nodes", []):
            if entry.get("id") == pack_id:
                return dict(entry)
        for entry in COMFY_INSTALL_RECIPE.get("optional_custom_nodes", []):
            if entry.get("id") == pack_id:
                return dict(entry)
    except Exception:
        return None
    return None


def _custom_node_directory_present(pack_id: str) -> bool:
    try:
        from _paths import COMFY_ROOT

        custom_nodes = Path(COMFY_ROOT) / "custom_nodes"
    except Exception:
        custom_nodes = Path("backend/repositories/ComfyUI/custom_nodes")
    if not custom_nodes.is_dir():
        return False
    normalized = pack_id.lower().replace("-", "").replace("_", "")
    for path in custom_nodes.iterdir():
        if not path.is_dir():
            continue
        name = path.name.lower().replace("-", "").replace("_", "")
        if normalized in name or name in normalized:
            return True
    return False


def assess_custom_node_pack(
    pack_id: str,
    *,
    object_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Directory + optional Comfy object_info node registration check (Krita-style)."""
    entry = _recipe_entry_for_pack(pack_id)
    directory_present = _custom_node_directory_present(pack_id)
    required_nodes = list(entry.get("nodes") or []) if entry else []
    missing_nodes: list[str] = []
    if object_info and required_nodes:
        available = set(object_info.keys())
        missing_nodes = [node for node in required_nodes if node not in available]
    ready = directory_present and not missing_nodes
    return {
        "pack_id": pack_id,
        "directory_present": directory_present,
        "nodes_registered": not missing_nodes if object_info else None,
        "missing_nodes": missing_nodes,
        "required_nodes": required_nodes,
        "url": (entry or {}).get("url", ""),
        "version": (entry or {}).get("version"),
        "ready": ready,
    }


def custom_node_pack_present(
    pack_id: str,
    *,
    object_info: dict[str, Any] | None = None,
) -> bool:
    if not _custom_node_directory_present(pack_id):
        return False
    if object_info is None:
        return True
    status = assess_custom_node_pack(pack_id, object_info=object_info)
    return bool(status["ready"])
