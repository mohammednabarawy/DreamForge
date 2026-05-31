"""Comfy-oriented prompt preparation (RuinedFooocus parity layer)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from dreamforge_prompt.expansion import (
    configure_prompt_expansion_path,
    ensure_prompt_expansion_model,
    prompt_expansion_available,
)
from dreamforge_prompt.legacy import process_prompt_with_legacy_modules
from dreamforge_prompt.loras import merge_generation_loras
from dreamforge_prompt.shift_attention import shift_attention

PROMPT_ENHANCERS = frozenset(
    {
        "none",
        "off",
        "flufferizer",
        "style: flufferizer",
        "hyperprompt",
        "style: hyperprompt",
        "erniehancer",
        "style: erniehancer",
    }
)

ENHANCER_STYLE_NAMES = {
    "flufferizer": "Flufferizer",
    "hyperprompt": "Hyperprompt",
    "erniehancer": "Erniehancer",
}

MODERN_FAMILIES = frozenset(
    {
        "flux",
        "flux_kontext",
        "qwen",
        "qwen_image",
        "qwen_image_edit",
        "hidream",
        "hidream_o1",
        "sd3",
    }
)

STYLE_KEEP_PREFIXES = (
    "flufferizer",
    "hyperprompt",
    "erniehancer",
    "artify",
    "lora keywords",
    "style: pick random",
)


def default_prompt_enhancer(model_family: str | None) -> str:
    if _is_modern_family(model_family):
        return "none"
    return "flufferizer"


def _normalize_enhancer(value: Any) -> str:
    text = str(value or "none").strip().lower()
    if text in ("", "none", "off", "false", "0"):
        return "none"
    if text.startswith("style:"):
        text = text.split(":", 1)[1].strip()
    return text


def _inject_prompt_enhancer_style(styles: list[str], enhancer: str) -> list[str]:
    style_name = ENHANCER_STYLE_NAMES.get(enhancer)
    if not style_name:
        return list(styles)
    merged = list(styles)
    if style_name not in merged and f"Style: {style_name}" not in merged:
        merged.append(style_name)
    return merged


def _is_modern_family(family: str | None) -> bool:
    fam = (family or "").lower()
    return any(fam == item or fam.startswith(f"{item}_") for item in MODERN_FAMILIES)


def _filter_modern_styles(styles: list[str]) -> list[str]:
    kept: list[str] = []
    for style in styles or []:
        label = str(style or "").strip()
        if not label:
            continue
        lower = label.lower()
        if any(lower.startswith(prefix) or lower == prefix for prefix in STYLE_KEEP_PREFIXES):
            kept.append(label)
            continue
        if lower in ENHANCER_STYLE_NAMES or lower in {
            f"style: {name.lower()}" for name in ENHANCER_STYLE_NAMES.values()
        }:
            kept.append(label)
    return kept


def _build_gen_data(job, settings: dict) -> dict:
    gen_data = dict(vars(job))
    gen_data.update(
        {
            "auto_negative": bool(
                getattr(job, "auto_negative_prompt", False)
                or settings.get("auto_negative_prompt")
            ),
            "lora_keywords": getattr(job, "lora_keywords", "") or "",
        }
    )
    return gen_data


def _batch_distance(job, *, image_index: int | None = None) -> float | None:
    try:
        image_number = int(getattr(job, "image_number", 1) or 1)
    except (TypeError, ValueError):
        image_number = 1
    if image_number <= 1:
        return None
    if image_index is None:
        image_index = int(getattr(job, "_prompt_image_index", 0) or 0)
    return float(image_index) / max(float(image_number - 1), 1.0)


def prepare_generation_prompts(
    job,
    model: dict,
    prompt: str,
    negative: str,
    settings: dict,
    *,
    image_index: int | None = None,
    download_expansion: bool = True,
) -> dict[str, Any]:
    """Run RuinedFooocus-style ``process_prompt`` before Comfy graph submission."""
    family = str(model.get("family") or "").lower()
    styles = list(settings.get("styles") or getattr(job, "styles", None) or [])
    enhancer = _normalize_enhancer(
        getattr(job, "prompt_enhancer", None) or getattr(job, "prompt_enhance", None)
    )
    if enhancer in ("", "none") and getattr(job, "prompt_enhancer", None) in (None, ""):
        enhancer = default_prompt_enhancer(family)

    if enhancer != "none":
        styles = _inject_prompt_enhancer_style(styles, enhancer)
        if enhancer == "flufferizer" and download_expansion:
            ensure_prompt_expansion_model(download=True)
        configure_prompt_expansion_path()

    if _is_modern_family(family):
        styles = _filter_modern_styles(styles)
    elif not styles:
        styles = list(settings.get("styles") or [])

    gen_data = _build_gen_data(job, settings)
    positive, negative_out, parsed_loras = process_prompt_with_legacy_modules(
        styles,
        prompt,
        negative,
        gen_data,
    )

    distance = _batch_distance(job, image_index=image_index)
    if distance is not None:
        positive = shift_attention(positive, distance)
        negative_out = shift_attention(negative_out, distance)

    negative_out = negative_out.strip().strip(",").strip()
    comfy_loras = merge_generation_loras(job, parsed_loras)

    return {
        "prompt": positive.strip(),
        "negative": negative_out,
        "loras": parsed_loras,
        "comfy_loras": comfy_loras,
        "styles_applied": styles,
        "prompt_enhancer": enhancer,
        "expansion_available": prompt_expansion_available(),
        "shift_attention_distance": distance,
    }
