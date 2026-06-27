"""Inpaint model detection and default selection."""

from __future__ import annotations

from typing import Any

from dreamforge_model_registry import ModelCapabilities, model_capabilities_for_model
from dreamforge_workflow_routing import checkpoint_is_flux_fill


def _blob(model: dict | None) -> str:
    if not isinstance(model, dict):
        return ""
    return " ".join(
        str(model.get(key) or "")
        for key in ("family", "caption", "engine_name", "relative_path", "name")
    ).lower()


def model_supports_flux_fill_inpaint(model: dict | None, model_family: str = "") -> bool:
    if checkpoint_is_flux_fill(model, model_family):
        return True
    caps = model_capabilities_for_model(model, model_family)
    return ModelCapabilities.FLUX_FILL_INPAINT in caps


def model_supports_native_inpaint(model: dict | None, model_family: str = "") -> bool:
    fam = (model_family or (model or {}).get("family") or "").lower()
    if fam in {"sdxl", "sd15", "sdxl_inpaint"}:
        return True
    blob = _blob(model)
    if "inpaint" in blob and "controlnet" not in blob and "control net" not in blob:
        return True
    if blob.endswith("512-inpainting-ema.safetensors") or "512-inpainting" in blob:
        return True
    caps = model_capabilities_for_model(model, model_family)
    return ModelCapabilities.INPAINT in caps and ModelCapabilities.FLUX_FILL_INPAINT not in caps


def model_supports_inpaint(model: dict | None, model_family: str = "") -> bool:
    return model_supports_flux_fill_inpaint(model, model_family) or model_supports_native_inpaint(
        model, model_family
    )


def score_inpaint_gallery_item(item: dict[str, Any]) -> int:
    if not isinstance(item, dict):
        return -1
    family = str(item.get("family") or "").lower()
    blob = _blob(item)
    if not model_supports_inpaint(item, family):
        return -1
    score = 0
    if model_supports_flux_fill_inpaint(item, family):
        score += 80
        if "fp8" in blob or "_fp8" in blob:
            score += 15
    if "inpaint" in blob:
        score += 40
    if family in {"sdxl", "sdxl_inpaint", "sd15"}:
        score += 25
    if "lightning" in blob and "inpaint" in blob:
        score += 10
    if "juggernaut" in blob and "inpaint" in blob:
        score += 8
    if "dreamshaper" in blob and "inpaint" in blob:
        score += 8
    return score


def pick_best_inpaint_model(gallery: list[Any]) -> str:
    best_score = -1
    best_engine = ""
    for item in gallery or []:
        if not isinstance(item, dict):
            continue
        score = score_inpaint_gallery_item(item)
        if score > best_score:
            best_score = score
            best_engine = str(item.get("engine_name") or item.get("relative_path") or "")
    return best_engine


def inpaint_workflow_kind(model: dict | None, model_family: str = "") -> str:
    if model_supports_flux_fill_inpaint(model, model_family):
        return "flux_fill"
    if model_supports_native_inpaint(model, model_family):
        return "native_inpaint"
    return "unsupported"
