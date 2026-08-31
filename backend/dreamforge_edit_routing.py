"""Edit model detection and routing helpers."""

from __future__ import annotations

from typing import Any

from dreamforge_model_registry import ModelCapabilities, model_capabilities_for_model


def _blob(model: dict | None) -> str:
    if not isinstance(model, dict):
        return ""
    return " ".join(
        str(model.get(key) or "")
        for key in ("family", "caption", "engine_name", "relative_path", "name")
    ).lower()


def model_supports_kontext_edit(model: dict | None, model_family: str = "") -> bool:
    fam = (model_family or (model or {}).get("family") or "").lower()
    if fam == "flux_kontext":
        return True
    blob = _blob(model)
    if "fill" in blob:
        return False
    return any(
        hint in blob
        for hint in (
            "flux1-dev-kontext",
            "flux.1-kontext",
            "flux kontext",
            "kontext-dev",
            "flux_kontext",
        )
    )


def model_supports_qwen_edit(model: dict | None, model_family: str = "") -> bool:
    fam = (model_family or (model or {}).get("family") or "").lower()
    if fam == "qwen_image_edit":
        return True
    blob = _blob(model)
    return "qwen" in blob and "edit" in blob


def model_supports_img2img_edit(model: dict | None, model_family: str = "") -> bool:
    fam = (model_family or (model or {}).get("family") or "").lower()
    if fam in {
        "sdxl",
        "sd15",
        "flux",
        "flux2",
        "hidream",
        "hidream_o1",
        "ideogram4",
        "krea2",
        "z_image",
    }:
        return True
    caps = model_capabilities_for_model(model, model_family)
    return ModelCapabilities.IMAGE_TO_IMAGE in caps


def model_supports_edit(model: dict | None, model_family: str = "") -> bool:
    return (
        model_supports_kontext_edit(model, model_family)
        or model_supports_qwen_edit(model, model_family)
        or model_supports_img2img_edit(model, model_family)
    )


_SDXL_TOOLBOX_NEEDLES = ("epicrealism", "juggernaut", "realvis", "dreamshaper", "sd_xl", "sdxl")

_NON_SDXL_TOOLBOX_FAMILIES = frozenset(
    {
        "flux",
        "flux_kontext",
        "flux_fill",
        "flux2",
        "qwen_image",
        "qwen_image_edit",
        "krea2",
        "z-image",
        "z_image",
        "hidream",
        "hidream_o1",
        "sd3",
        "ideogram4",
        "kandinsky",
        "kandinsky5",
        "chroma",
    }
)


def model_supports_sdxl_union_toolbox(model: dict | None, model_family: str = "") -> bool:
    """Portrait Master / Photo Restore need SDXL checkpoints + Union ControlNet."""
    family = (model_family or (model or {}).get("family") or "").lower()
    if family in _NON_SDXL_TOOLBOX_FAMILIES:
        return False
    category = str((model or {}).get("category") or "checkpoints").lower()
    if category in {"diffusion_models", "unet"}:
        return False
    if family == "sdxl":
        return True
    if family == "sd15":
        return False
    blob = _blob(model)
    if any(needle in blob for needle in _SDXL_TOOLBOX_NEEDLES):
        return True
    return False


def pick_best_sdxl_toolbox_model(gallery_list: list[Any]) -> str:
    """Prefer SDXL realism checkpoints for toolbox ControlNet Union workflows."""
    best_name = ""
    best_score = -1
    for raw in gallery_list:
        if not isinstance(raw, dict):
            continue
        blob = _blob(raw)
        family = str(raw.get("family") or "").lower()
        score = 0
        if family == "sdxl" or "sdxl" in blob:
            score += 100
        for needle in _SDXL_TOOLBOX_NEEDLES:
            if needle in blob:
                score += 25
        if "turbo" in blob or "lightning" in blob:
            score -= 10
        if score > best_score:
            best_score = score
            best_name = str(raw.get("engine_name") or raw.get("relative_path") or "")
    return best_name


def _controlnet_blob(name: str) -> str:
    return str(name or "").replace("\\", "/").lower()


def controlnet_supports_sdxl_checkpoint(name: str) -> bool:
    """True when a controlnet filename is for SDXL (not SD 1.5 / v1.1)."""
    hay = _controlnet_blob(name)
    if any(
        token in hay
        for token in (
            "sd15",
            "sd1.5",
            "sd_15",
            "v11p_sd15",
            "control_v11p",
            "control_v11f1p",
            "/sd15/",
        )
    ):
        return False
    return any(token in hay for token in ("sdxl", "union", "xinsir"))


def pick_sdxl_union_controlnet() -> str | None:
    """Pick an installed SDXL ControlNet Union file; never fall back to SD1.5."""
    try:
        from dreamforge_cli_inventory import list_model_inventory

        items = list_model_inventory().get("categories", {}).get("controlnet", [])
    except Exception:
        items = []
    union_match: str | None = None
    sdxl_match: str | None = None
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(
            item.get("name") or item.get("relative_path") or item.get("engine_name") or ""
        ).replace("\\", "/")
        if not name or not controlnet_supports_sdxl_checkpoint(name):
            continue
        if "union" in name.lower():
            union_match = name
            break
        if sdxl_match is None:
            sdxl_match = name
    return union_match or sdxl_match


def resolve_sdxl_union_controlnet(model_name: str | None = None) -> str | None:
    """Resolve SDXL Union ControlNet for toolbox workflows (Portrait Master / Photo Restore)."""
    candidate = str(model_name or "").strip().replace("\\", "/")
    if candidate and controlnet_supports_sdxl_checkpoint(candidate) and "union" in candidate.lower():
        return candidate
    picked = pick_sdxl_union_controlnet()
    if picked:
        return picked
    if candidate and controlnet_supports_sdxl_checkpoint(candidate):
        return candidate
    return None


def edit_routing_for_model(model: dict | None, model_family: str = "") -> dict[str, Any]:
    if model_supports_qwen_edit(model, model_family):
        return {
            "edit_type": "qwen_edit",
            "edit_strength": 1.0,
            "cn_selection": "None",
            "cn_type": "None",
        }
    if model_supports_kontext_edit(model, model_family):
        return {
            "edit_type": "kontext",
            "edit_strength": 1.0,
            "cn_selection": "None",
            "cn_type": "None",
            "steps": 20,
        }
    fam = (model_family or (model or {}).get("family") or "").lower()
    if fam == "krea2":
        return {
            "edit_type": "auto",
            "edit_strength": 1.0,
            "cn_selection": "None",
            "cn_type": "None",
        }
    if fam == "ideogram4":
        return {
            "edit_type": "kontext",
            "edit_strength": 1.0,
            "cn_selection": "None",
            "cn_type": "None",
        }
    if model_supports_img2img_edit(model, model_family):
        return {
            "edit_type": "img2img",
            "edit_strength": 0.75,
            "cn_selection": "Custom...",
            "cn_type": "img2img",
        }
    return {
        "edit_type": "kontext",
        "edit_strength": 1.0,
        "cn_selection": "None",
        "cn_type": "None",
        "steps": 20,
    }


def score_edit_gallery_item(item: dict[str, Any]) -> int:
    if not isinstance(item, dict):
        return -1
    family = str(item.get("family") or "").lower()
    if not model_supports_edit(item, family):
        return -1
    if model_supports_kontext_edit(item, family):
        score = 90
        blob = _blob(item)
        if "fp8" in blob:
            score += 10
        return score
    if model_supports_qwen_edit(item, family):
        score = 85
        blob = _blob(item)
        if "q4_k_m" in blob and ".gguf" in blob:
            score += 10
        return score
    return 40
