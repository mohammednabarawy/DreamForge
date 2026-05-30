"""Model capability registry for DreamForge AI OS.

This registry defines the fundamental capabilities of different model families,
allowing the router to select the right model for the requested operation.
"""

from typing import Dict, List, Set, Any

class ModelCapabilities:
    TEXT_TO_IMAGE = "text_to_image"
    IMAGE_TO_IMAGE = "image_to_image"
    INPAINT = "inpaint"
    KONTEXT_EDIT = "kontext_edit"
    QWEN_SEMANTIC_EDIT = "qwen_semantic_edit"
    CONTROLNET_COMPATIBLE = "controlnet_compatible"
    IPADAPTER_COMPATIBLE = "ipadapter_compatible"
    HIRES_FIX_COMPATIBLE = "hires_fix_compatible"
    UPSCALE = "upscale"

# Map model families to their supported capabilities
FAMILY_CAPABILITIES: Dict[str, Set[str]] = {
    "sdxl": {
        ModelCapabilities.TEXT_TO_IMAGE,
        ModelCapabilities.IMAGE_TO_IMAGE,
        ModelCapabilities.INPAINT,
        ModelCapabilities.CONTROLNET_COMPATIBLE,
        ModelCapabilities.IPADAPTER_COMPATIBLE,
        ModelCapabilities.HIRES_FIX_COMPATIBLE,
    },
    "sd15": {
        ModelCapabilities.TEXT_TO_IMAGE,
        ModelCapabilities.IMAGE_TO_IMAGE,
        ModelCapabilities.INPAINT,
        ModelCapabilities.CONTROLNET_COMPATIBLE,
        ModelCapabilities.IPADAPTER_COMPATIBLE,
        ModelCapabilities.HIRES_FIX_COMPATIBLE,
    },
    "sd3": {
        ModelCapabilities.TEXT_TO_IMAGE,
        ModelCapabilities.IMAGE_TO_IMAGE,
    },
    "flux": {
        ModelCapabilities.TEXT_TO_IMAGE,
        ModelCapabilities.IMAGE_TO_IMAGE,
        ModelCapabilities.HIRES_FIX_COMPATIBLE,
        ModelCapabilities.CONTROLNET_COMPATIBLE,  # via Xlabs/Union
    },
    "flux_kontext": {
        ModelCapabilities.KONTEXT_EDIT,
        ModelCapabilities.IMAGE_TO_IMAGE,
        ModelCapabilities.INPAINT,
    },
    "flux_fill": {
        ModelCapabilities.INPAINT,
        ModelCapabilities.IMAGE_TO_IMAGE,
    },
    "qwen_image": {
        ModelCapabilities.TEXT_TO_IMAGE,
    },
    "qwen_image_edit": {
        ModelCapabilities.QWEN_SEMANTIC_EDIT,
        ModelCapabilities.IMAGE_TO_IMAGE,
    },
    "hidream": {
        ModelCapabilities.TEXT_TO_IMAGE,
        ModelCapabilities.IMAGE_TO_IMAGE,
    },
    "hidream_o1": {
        ModelCapabilities.TEXT_TO_IMAGE,
        ModelCapabilities.IMAGE_TO_IMAGE,
    },
}

def get_family_capabilities(family: str) -> Set[str]:
    """Return the set of capabilities for a given model family."""
    if not family:
        return set()
    return set(FAMILY_CAPABILITIES.get(family.lower(), set()))

def supports_capability(family: str, capability: str) -> bool:
    """Check if a model family supports a specific capability."""
    return capability in get_family_capabilities(family)

def get_families_for_capability(capability: str) -> List[str]:
    """Return all families that support the requested capability."""
    return [fam for fam, caps in FAMILY_CAPABILITIES.items() if capability in caps]

def required_capabilities_for_request(params: dict) -> Set[str]:
    """Analyze the request parameters to determine required model capabilities."""
    caps = set()
    mode = str(params.get("workflow_mode") or "").lower()
    edit_type = params.get("edit_type")
    has_input = bool(params.get("input_image") or params.get("inpaint_mask_path"))
    has_upscale = bool(params.get("upscale_image"))
    
    if mode in ("upscale",) or has_upscale:
        caps.add(ModelCapabilities.UPSCALE)
    elif mode in ("inpaint",) or edit_type == "inpaint" or params.get("inpaint_mask_path"):
        caps.add(ModelCapabilities.INPAINT)
    elif mode in ("edit", "face_detail") or has_input:
        if edit_type == "kontext":
            caps.add(ModelCapabilities.KONTEXT_EDIT)
        elif edit_type == "qwen_edit":
            caps.add(ModelCapabilities.QWEN_SEMANTIC_EDIT)
        else:
            caps.add(ModelCapabilities.IMAGE_TO_IMAGE)
    elif mode in ("hires", "area_composition", "composite", "composition"):
        caps.add(ModelCapabilities.TEXT_TO_IMAGE)
    else:
        caps.add(ModelCapabilities.TEXT_TO_IMAGE)

    if mode in ("hires", "hires_fix", "two_pass"):
        caps.add(ModelCapabilities.HIRES_FIX_COMPATIBLE)
    if mode in ("ipadapter", "reference", "reference_ipadapter"):
        caps.add(ModelCapabilities.IPADAPTER_COMPATIBLE)
            
    # Hires fix / controlnet requirements
    cn_type = params.get("cn_type")
    if cn_type and cn_type not in ("None", "none", "", None):
        if cn_type == "upscale":
            # If using controlnet for upscale
            pass
        elif cn_type != "inpaint":
            caps.add(ModelCapabilities.CONTROLNET_COMPATIBLE)
            
    return caps
