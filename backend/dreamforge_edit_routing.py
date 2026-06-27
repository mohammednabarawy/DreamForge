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
