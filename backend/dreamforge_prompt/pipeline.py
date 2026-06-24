"""Comfy-oriented prompt preparation (RuinedFooocus parity layer)."""

from __future__ import annotations

import re
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
        "ideogram4",
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

_QWEN_PERSON_EDIT_WORDS = re.compile(
    r"\b("
    r"shirt|suit|jacket|coat|blazer|clothes|clothing|outfit|dress|pants|trouser|"
    r"portrait|person|man|woman|face|hair|beard|expression|pose|hands?|body"
    r")\b",
    re.IGNORECASE,
)

_QWEN_PRESERVE_WORDS = re.compile(
    r"\b(preserve|keep|retain|unchanged|same|identity|face)\b",
    re.IGNORECASE,
)

_QWEN_SCENE_CHANGE_WORDS = (
    "studio",
    "smoke",
    "spotlight",
    "background",
    "lighting",
    "moody",
    "cinematic",
    "editorial",
    "environment",
    "scene",
)

_QWEN_OUTFIT_WORDS = (
    "suit",
    "outfit",
    "shirt",
    "trouser",
    "jacket",
    "blazer",
    "silk",
    "dress",
)

_QWEN_POSE_WORDS = (
    "hands",
    "pockets",
    "pose",
    "shoulders",
    "tilt",
    "standing",
    "stands",
)

_QWEN_PRESERVATION_TAIL = re.compile(
    r"[\.,;]+\s*(use the reference person|preserve identity|change only the requested|"
    r"keep details sharp|do not blur).*",
    re.IGNORECASE | re.DOTALL,
)


def _qwen_edit_scene_change_requested(prompt: str) -> bool:
    lower = str(prompt or "").lower()
    return any(token in lower for token in _QWEN_SCENE_CHANGE_WORDS)


def _qwen_edit_needs_quality_pass(prompt: str) -> bool:
    """Global outfit + scene + pose edits need more steps than Lightning 8-step previews."""
    lower = str(prompt or "").lower()
    scene = _qwen_edit_scene_change_requested(lower)
    outfit = any(token in lower for token in _QWEN_OUTFIT_WORDS)
    pose = any(token in lower for token in _QWEN_POSE_WORDS)
    return sum((scene, outfit, pose)) >= 2


def _qwen_edit_restructure_global_prompt(text: str) -> str:
    """Qwen Image Edit works best with short change-first, keep-identity-last instructions."""
    core = _QWEN_PRESERVATION_TAIL.sub("", text).strip()
    core = re.sub(r"\s+", " ", core)
    if not core:
        core = text.strip()
    return (
        f"Edit the reference photo: {core}. "
        "Keep the same person: preserve face, facial proportions, skin texture, hair, beard, "
        "glasses if present, and body shape. Do not blur, beautify, or replace the face."
    )


def _is_qwen_image_edit_job(job, family: str) -> bool:
    edit_type = str(getattr(job, "edit_type", "") or "").lower()
    has_input = bool(getattr(job, "input_image", None) or getattr(job, "upscale_image", None))
    return family == "qwen_image_edit" and edit_type == "qwen_edit" and has_input


def _qwen_edit_prompt_guard(job, family: str, prompt: str) -> str:
    """Bias Qwen edits toward local changes and identity preservation.
    (Disabled per user request to only use user prompt)."""
    return str(prompt or "").strip()


def _qwen_edit_negative_guard(job, family: str, negative: str) -> str:
    """Qwen Edit (DiT) degrades severely with forced negative prompts at low CFG.
    Only pass through what the user explicitly requested."""
    return str(negative or "").strip()


def default_prompt_enhancer(model_family: str | None, workflow_mode: str = "generate") -> str:
    """RuinedFooocus parity: Flufferizer/Hyperprompt apply only when explicitly selected."""
    return "none"


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


_RICH_PROMPT_MARKERS = re.compile(
    r"\b("
    r"cinematic|photoreal|8k|ultra.?detailed|high detail|sharp focus|"
    r"professional (photo|photography|lighting)|studio lighting|"
    r"preserve|unchanged|seamless blend|masked region"
    r")\b",
    re.IGNORECASE,
)


def _prompt_is_rich(text: str) -> bool:
    cleaned = str(text or "").strip()
    if len(cleaned.split()) >= 28:
        return True
    return bool(_RICH_PROMPT_MARKERS.search(cleaned))


def _append_clause(prompt: str, clause: str) -> str:
    base = str(prompt or "").strip().rstrip(".,; ")
    if not base:
        return clause
    if clause.lower() in base.lower():
        return base
    return f"{base}. {clause}"


def _modern_generate_boost(family: str, prompt: str) -> str:
    if _prompt_is_rich(prompt):
        return prompt
    fam = (family or "").lower()
    if fam.startswith("qwen"):
        return _append_clause(
            prompt,
            "High detail, natural colors, balanced lighting, sharp focus, clean composition",
        )
    if fam.startswith("hidream"):
        return _append_clause(
            prompt,
            "Expressive lighting, rich color, fine detail, artistic composition",
        )
    if "flux" in fam or fam == "sd3":
        return _append_clause(
            prompt,
            "Cinematic lighting, natural colors, high detail, sharp focus, professional composition",
        )
    return prompt


def _kontext_edit_boost(job, family: str, prompt: str) -> str:
    fam = (family or "").lower()
    if "kontext" not in fam and fam != "flux_kontext":
        return prompt
    has_input = bool(getattr(job, "input_image", None) or getattr(job, "upscale_image", None))
    if not has_input:
        return prompt
    edit_type = str(getattr(job, "edit_type", "") or "auto").lower()
    if edit_type not in {"kontext", "auto", "img2img"}:
        return prompt
    text = str(prompt or "").strip()
    if not text:
        return text
    lower = text.lower()
    if "preserve" in lower and ("composition" in lower or "identity" in lower):
        return text
    if len(text) <= 160:
        return (
            f"{text.rstrip('. ')}. Preserve the subject identity, pose, and overall composition; "
            "change only what is described. Keep lighting and background consistent unless "
            "the prompt asks otherwise."
        )
    return _append_clause(
        text,
        "Preserve identity and composition; apply only the requested edit",
    )


def _identity_generate_boost(job, workflow_mode: str, prompt: str) -> str:
    mode = (workflow_mode or "generate").lower()
    if mode in {"edit", "inpaint", "upscale", "agent"}:
        return prompt
    has_ref = bool(getattr(job, "input_image", None) or getattr(job, "reference_image", None))
    if not has_ref:
        return prompt
    if not (
        getattr(job, "face_preservation", False)
        or getattr(job, "preserve_character", False)
        or str(getattr(job, "identity_mode", "") or "").lower()
        in {"face", "faceid", "face_id", "preserve_face", "ipadapter_faceid", "kontext", "qwen_edit", "auto"}
    ):
        return prompt
    text = str(prompt or "").strip()
    if not text:
        return (
            "Recreate the same person from the reference photo in a new scene. "
            "Preserve facial features and identity."
        )
    lower = text.lower()
    if "same person" in lower or ("preserve" in lower and "identity" in lower):
        return text
    return (
        f"Same person as the reference photo: {text.rstrip('. ')}. "
        "Preserve facial identity and likeness; new scene as described."
    )


def _inpaint_boost(job, studio_mode: str, prompt: str) -> str:
    if (studio_mode or "").lower() != "inpaint":
        return prompt
    if not getattr(job, "inpaint_mask_path", None):
        return prompt
    text = str(prompt or "").strip()
    if not text:
        return (
            "Fill the masked region with content that matches the surrounding image. "
            "Seamless blend, consistent lighting and perspective."
        )
    lower = text.lower()
    if "masked" in lower or "seamless" in lower:
        return text
    return (
        f"In the masked region: {text.rstrip('. ')}. Blend seamlessly with surrounding areas; "
        "preserve lighting, perspective, and unchanged regions."
    )


def _upscale_boost(studio_mode: str, prompt: str) -> str:
    if (studio_mode or "").lower() != "upscale":
        return prompt
    text = str(prompt or "").strip()
    if not text:
        return (
            "Enhance fine detail and sharpness while preserving composition, colors, and identity."
        )
    if _prompt_is_rich(text):
        return text
    return _append_clause(
        text,
        "Enhance detail and texture while preserving composition and natural appearance",
    )


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
    if family == "ideogram4":
        from dreamforge_prompt.ideogram4 import prepare_ideogram4_generation_prompts

        return prepare_ideogram4_generation_prompts(
            job,
            prompt,
            negative,
            settings,
            width=int(settings.get("width") or getattr(job, "width", None) or 1024),
            height=int(settings.get("height") or getattr(job, "height", None) or 1024),
        )
    styles = list(settings.get("styles") or getattr(job, "styles", None) or [])
    enhancer = _normalize_enhancer(
        getattr(job, "prompt_enhancer", None)
        or getattr(job, "prompt_enhance", None)
        or settings.get("prompt_enhancer")
    )
    workflow_mode = str(getattr(job, "workflow_mode", None) or getattr(job, "comfy_workflow_mode", None) or "generate").lower()

    if enhancer in ("", "none") and getattr(job, "prompt_enhancer", None) in (None, ""):
        enhancer = default_prompt_enhancer(family, workflow_mode)

    if enhancer != "none":
        styles = _inject_prompt_enhancer_style(styles, enhancer)
        if enhancer == "flufferizer" and download_expansion:
            ensure_prompt_expansion_model(download=True)
        configure_prompt_expansion_path()

    if _is_modern_family(family):
        styles = _filter_modern_styles(styles)
    elif not styles:
        styles = list(settings.get("styles") or [])

    prompt = _qwen_edit_prompt_guard(job, family, prompt)
    negative = _qwen_edit_negative_guard(job, family, negative)
    if workflow_mode == "upscale":
        prompt = _upscale_boost(workflow_mode, prompt)
    elif workflow_mode == "inpaint":
        prompt = _inpaint_boost(job, workflow_mode, prompt)
    elif workflow_mode == "edit":
        prompt = _kontext_edit_boost(job, family, prompt)
    elif workflow_mode == "generate":
        prompt = _identity_generate_boost(job, workflow_mode, prompt)
        if _is_modern_family(family):
            prompt = _modern_generate_boost(family, prompt)

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
