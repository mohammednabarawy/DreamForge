"""Agent-facing recipes, manifests, and validation for the local DreamForge CLIs."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from PIL import Image, ImageStat

from dreamforge_cli_inventory import resolve_generation_model, resolve_model_name


MODEL_FAMILY_HINTS: dict[str, dict[str, Any]] = {
    "sdxl": {
        "best_for": ["product_ad", "social_post", "thumbnail", "cinematic_scene", "real_estate", "fashion_editorial", "anime_illustration", "avatar_portrait"],
        "models": [
            "epicrealismXL_VXIAbeast4SLightning.safetensors",
            "RealVisXL_V5.0_fp16.safetensors",
            "juggernautXL_v8Rundiffusion.safetensors",
        ],
        "vram_16gb": "fast, proven",
        "vram_8gb": "use Lightning/Turbo checkpoints at 768-1024",
    },
    "flux": {
        "best_for": ["product_ad", "infographic", "social_post", "app_icon", "3d_render"],
        "models": ["flux1-schnell-fp8.safetensors", "flux1-dev-fp8.safetensors"],
        "vram_16gb": "prefer schnell for speed; dev for quality",
        "vram_8gb": "flux1-schnell-fp8 at 512-768 with --lowvram; avoid full dev",
    },
    "flux_kontext": {
        "best_for": ["image_edit", "style_transfer", "object_swap", "scene_modification"],
        "models": ["flux1-dev-kontext_fp8_scaled.safetensors"],
        "requires_input_image": True,
        "notes": "Flux Kontext is an image editing model. Always requires --input-image.",
    },
    "flux2": {
        "best_for": ["fast_draft", "social_post", "thumbnail"],
        "models": ["Flux2-Klein-9B-consistency-V2.safetensors", "flux-2-klein-4b-fp8.safetensors", "flux-2-klein-9b-kv-fp8.safetensors"],
        "notes": "Flux 2 Klein models. Use consistency LoRA for best results.",
    },
    "hidream": {
        "best_for": ["cinematic_scene", "cinematic", "fashion_editorial"],
        "models": ["hidream_o1_image_dev_mxfp8.safetensors"],
        "vram_16gb": "checkpoints/ repackaged dev mxfp8; 28 steps, CFG 1.0, 1024-1344px",
        "vram_8gb": "1024px max, 28 steps minimum, --vram-profile 8gb; no DreamForge styles",
    },
    "hidream_o1": {
        "best_for": ["cinematic_scene", "cinematic", "long_text_layout", "fashion_editorial", "concept_art"],
        "models": [
            "hidream_o1_image_dev_mxfp8.safetensors",
            "hidream_o1_image_dev_fp8_scaled.safetensors",
        ],
        "vram_16gb": "28 steps, CFG 1.0, euler/normal; optional gemma4 prompt refine",
        "vram_8gb": "28 steps min; place weights under models/checkpoints/",
        "notes": "Do not use SDXL style presets. Negative prompt is cleared. Use detailed reasoning-style prompts.",
    },
    "qwen_image": {
        "best_for": ["fast_generation", "general_purpose"],
        "models": ["qwen_image_fp8_e4m3fn.safetensors"],
        "notes": "Qwen Image generation. Euler sampler, 30 steps, CFG 3.0.",
    },
    "qwen_image_edit": {
        "best_for": ["text_edits", "localized_changes", "signage_fixes", "object_removal"],
        "models": ["Qwen_Image_Edit-Q5_1.gguf", "qwen_image_edit_2509_fp8_e4m3fn.safetensors"],
        "vram_16gb": "needs clip Qwen2.5-VL-7B-Instruct-Q4_K_S.gguf in models/clip",
        "vram_8gb": "not recommended until dependencies installed",
        "requires_input_image": True,
        "stability": "experimental",
    },
    "z_image": {
        "best_for": ["fast_draft", "concept_art", "sticker_design"],
        "models": ["z_image_turbo_fp8_e4m3fn.safetensors", "z_image_turbo_bf16.safetensors"],
        "notes": "Z-Image Turbo. Very fast generation, 20 steps, euler/simple.",
    },
    "sd15": {
        "best_for": ["legacy_workflows", "controlnet_heavy", "low_vram"],
        "models": ["majicmixRealistic_v7_sd1.5.safetensors", "v1-5-pruned-emaonly-fp16.safetensors"],
        "notes": "SD 1.5 models. Best for ControlNet-heavy workflows on low VRAM.",
    },
}


from dreamforge_style_recipes import STYLE_RECIPES


CREATIVE_FIELDS = [
    ("main subject", "subject"),
    ("composition", "composition"),
    ("action", "action"),
    ("location", "location"),
    ("visual style", "visual_style"),
    ("lighting", "lighting"),
    ("camera", "camera"),
    ("mood", "mood"),
    ("brand colors", "brand_colors"),
    ("materials", "materials"),
]


def add_agent_arguments(parser) -> None:
    parser.add_argument("--style", default="none", choices=["none", *STYLE_RECIPES.keys()],
                        help="Professional style recipe to apply before generation")
    parser.add_argument("--brand-kit", default=None,
                        help="Path to brand JSON with colors, tone, typography, materials, forbidden terms, or logo path")
    parser.add_argument("--manifest-path", default=None,
                        help="Where to write generation manifest JSON")
    parser.add_argument("--no-manifest", action="store_true",
                        help="Disable generation manifest JSON")
    parser.add_argument("--validate-output", action="store_true",
                        help="Validate generated images for existence, size, nonblank pixels, and basic contrast")
    parser.add_argument("--check-fake-text", action="store_true",
                        help="With --validate-output, flag likely gibberish text/label regions (product ads, signage)")


def add_creative_brief_arguments(parser) -> None:
    parser.add_argument("--subject", default=None, help="Main subject for the compiled prompt")
    parser.add_argument("--composition", default=None, help="Composition/framing")
    parser.add_argument("--action", default=None, help="What is happening")
    parser.add_argument("--location", default=None, help="Where the scene takes place")
    parser.add_argument("--visual-style", default=None, help="Visual style")
    parser.add_argument("--lighting", default=None, help="Lighting direction and mood")
    parser.add_argument("--camera", default=None, help="Camera/lens/framing details")
    parser.add_argument("--mood", default=None, help="Emotional tone")
    parser.add_argument("--brand-colors", default=None, help="Brand color palette")
    parser.add_argument("--materials", default=None, help="Important surface/material details")


def load_brand_kit(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    brand_path = Path(path)
    if not brand_path.is_absolute():
        brand_path = Path.cwd() / brand_path
    with brand_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("--brand-kit must point to a JSON object")
    data["_path"] = str(brand_path)
    return data


def _coerce_prompt_text(prompt) -> str:
    if prompt is None:
        return ""
    if isinstance(prompt, list):
        return ", ".join(str(item).strip() for item in prompt if str(item).strip())
    return str(prompt)


AGENT_ONLY_PARAM_KEYS = frozenset(
    {
        "identity_preservation",
        "scene_prompt_en",
        "scene_prompt_ar",
        "json",
    }
)


def _sanitize_param_value(key: str, value: Any) -> Any:
    if key == "negative_prompt":
        return coerce_negative_prompt_value(value)
    if key in ("styles", "lora", "reference_images", "control_images"):
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
    if key in ("prompt_enhancer", "prompt_enhance"):
        return str(value or "none").strip().lower()
    return value


def coerce_negative_prompt_value(negative: Any) -> str:
    if negative is None:
        return ""
    if isinstance(negative, list):
        return ", ".join(
            str(item).strip() for item in negative if str(item).strip()
        )
    return str(negative)


def normalize_generation_params(raw: dict | None) -> dict:
    """Accept agent-style JSON (lists, nested scene/identity blocks) from desktop/MCP."""
    params = dict(raw or {})
    prompt = params.get("prompt")

    if isinstance(prompt, str) and prompt.strip().startswith("{"):
        try:
            parsed = json.loads(prompt)
            if isinstance(parsed, dict):
                params = _merge_agent_prompt_dict(params, parsed)
        except json.JSONDecodeError:
            pass
    elif isinstance(prompt, dict):
        params = _merge_agent_prompt_dict(params, prompt)
    elif any(
        key in params
        for key in ("identity_preservation", "scene_prompt_en", "scene_prompt_ar")
    ):
        params = _merge_agent_prompt_dict(params, params)

    params["negative_prompt"] = coerce_negative_prompt_value(
        params.get("negative_prompt")
    )

    cleaned: dict[str, Any] = {}
    for key, value in params.items():
        if key in AGENT_ONLY_PARAM_KEYS:
            continue
        cleaned[key] = _sanitize_param_value(key, value)
    return cleaned


def _merge_agent_prompt_dict(params: dict, parsed: dict) -> dict:
    merged = dict(params)
    parts: list[str] = []

    identity = parsed.get("identity_preservation")
    if isinstance(identity, dict):
        for key in ("instruction_en", "instruction_ar"):
            value = identity.get(key)
            if value:
                parts.append(str(value))

    for key in ("scene_prompt_en", "scene_prompt_ar"):
        value = parsed.get(key)
        if value:
            parts.append(str(value))

    existing = _coerce_prompt_text(merged.get("prompt")).strip()
    if parts and (not existing or existing.startswith("{")):
        merged["prompt"] = "\n\n".join(parts)

    if parsed.get("negative_prompt") is not None and not merged.get("negative_prompt"):
        merged["negative_prompt"] = coerce_negative_prompt_value(
            parsed["negative_prompt"]
        )

    for key in AGENT_ONLY_PARAM_KEYS:
        merged.pop(key, None)

    return merged


def append_unique_phrases(prompt: str | None, phrases) -> str:
    parts = [p.strip() for p in _coerce_prompt_text(prompt).split(",") if p.strip()]
    seen = {p.lower() for p in parts}
    for phrase in phrases or []:
        if phrase is None:
            continue
        text = str(phrase).strip()
        key = text.lower()
        if text and key not in seen:
            parts.append(text)
            seen.add(key)
    return ", ".join(parts)


def _brand_phrases(brand_kit: dict[str, Any]) -> list[str]:
    phrases = []
    mapping = [
        ("brand", "brand_name"),
        ("brand tone", "tone"),
        ("brand colors", "colors"),
        ("typography", "typography"),
        ("materials", "materials"),
        ("audience", "audience"),
    ]
    for label, key in mapping:
        value = brand_kit.get(key)
        if isinstance(value, list):
            value = ", ".join(str(v) for v in value)
        if value:
            phrases.append(f"{label}: {value}")
    return phrases


def _brand_negatives(brand_kit: dict[str, Any]) -> list[str]:
    value = brand_kit.get("forbidden") or brand_kit.get("avoid") or []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(v) for v in value if v]
    return []


def select_existing_model(candidates: list[str]) -> str | None:
    for candidate in candidates:
        resolved = resolve_generation_model(candidate)
        if resolved:
            return resolved["engine_name"]
    return None


def apply_recipe_defaults(args, *, text_pipeline: bool = False):
    style = getattr(args, "style", "none")
    if not style or style == "none" or style not in STYLE_RECIPES:
        return args

    recipe = STYLE_RECIPES[style]

    model_attr = "base_model" if hasattr(args, "base_model") else "model"
    if not getattr(args, model_attr, None):
        model = select_existing_model(recipe.get("models", []))
        if model:
            setattr(args, model_attr, model)

    if hasattr(args, "styles") and not args.styles:
        recipe_styles = recipe.get("styles")
        if recipe_styles:
            args.styles = list(recipe_styles)

    if hasattr(args, "performance") and getattr(args, "performance", "Speed") == "Speed":
        args.performance = recipe.get("performance", args.performance)

    if hasattr(args, "steps") and getattr(args, "steps", None) is None and recipe.get("steps"):
        args.steps = recipe["steps"]

    if hasattr(args, "prompt_profile") and getattr(args, "prompt_profile", "none") == "none":
        args.prompt_profile = recipe.get("prompt_profile", "none")

    if text_pipeline and hasattr(args, "preset") and getattr(args, "preset", "balanced") == "balanced":
        args.preset = recipe.get("preset", args.preset)

    if not text_pipeline and hasattr(args, "aspect_ratio") and getattr(args, "aspect_ratio", "1152×896") == "1152×896":
        args.aspect_ratio = recipe.get("aspect_ratio", args.aspect_ratio)

    return args


def compile_creative_prompt(base_prompt: str | None, args, brand_kit: dict[str, Any] | None = None) -> str:
    style = getattr(args, "style", "none")
    recipe = STYLE_RECIPES.get(style, {})
    phrases = []
    phrases.extend(recipe.get("positive", []))
    for label, attr in CREATIVE_FIELDS:
        value = getattr(args, attr, None)
        if value:
            phrases.append(f"{label}: {value}")
    phrases.extend(_brand_phrases(brand_kit or {}))
    return append_unique_phrases(base_prompt, phrases)


def compile_negative_prompt(base_negative: str | None, args, brand_kit: dict[str, Any] | None = None) -> str:
    style = getattr(args, "style", "none")
    recipe = STYLE_RECIPES.get(style, {})
    phrases = []
    phrases.extend(recipe.get("negative", []))
    phrases.extend(_brand_negatives(brand_kit or {}))
    return append_unique_phrases(base_negative, phrases)


def detect_possible_fake_text(path: str) -> list[str]:
    """Heuristic: flag bottom/center bands that look like gibberish labels (no OCR)."""
    warnings = []
    try:
        image = Image.open(path).convert("L")
        width, height = image.size
        bands = [
            ("bottom_label_band", 0, int(height * 0.72), width, height),
            ("center_product_band", int(width * 0.2), int(height * 0.35), int(width * 0.8), int(height * 0.75)),
        ]
        for name, x0, y0, x1, y1 in bands:
            band = image.crop((x0, y0, x1, y1))
            pixels = list(band.getdata())
            if len(pixels) < 64:
                continue
            mid_tone = sum(1 for value in pixels if 90 <= value <= 200) / len(pixels)
            extrema = ImageStat.Stat(band).extrema[0]
            contrast = extrema[1] - extrema[0]
            if mid_tone > 0.12 and contrast > 80:
                warnings.append(f"possible_fake_text:{name}")
    except Exception as exc:
        warnings.append(f"fake_text_check_error:{exc}")
    return warnings


def validate_image(
    path: str,
    expected_width: int | None = None,
    expected_height: int | None = None,
    *,
    check_fake_text: bool = False,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "path": path,
        "exists": os.path.exists(path),
        "ok": False,
        "warnings": [],
    }
    if not result["exists"]:
        result["warnings"].append("file_missing")
        return result

    try:
        image = Image.open(path).convert("RGB")
        width, height = image.size
        gray = image.convert("L")
        extrema = ImageStat.Stat(gray).extrema[0]
        contrast = extrema[1] - extrema[0]
        result.update({
            "width": width,
            "height": height,
            "nonblank": extrema[0] != extrema[1],
            "luma_extrema": extrema,
            "contrast": contrast,
        })
        if expected_width and width != expected_width:
            result["warnings"].append(f"width_expected_{expected_width}_got_{width}")
        if expected_height and height != expected_height:
            result["warnings"].append(f"height_expected_{expected_height}_got_{height}")
        if extrema[0] == extrema[1]:
            result["warnings"].append("image_appears_blank")
        if contrast < 18:
            result["warnings"].append("very_low_contrast")
        if check_fake_text:
            result["warnings"].extend(detect_possible_fake_text(path))
        result["ok"] = not result["warnings"] or all(
            w.startswith(("width_expected", "height_expected")) for w in result["warnings"]
        )
    except Exception as exc:
        result["warnings"].append(f"validation_error:{exc}")
    return result


def default_manifest_path(images: list[str], fallback_dir: str, stem: str = "generation_manifest") -> str:
    if images:
        first = Path(images[0])
        if first.suffix:
            return str(first.with_suffix(f".{stem}.json"))
        return str(first / f"{stem}.json")
    return str(Path(fallback_dir) / f"{stem}.json")


def write_manifest(path: str, payload: dict[str, Any]) -> str:
    manifest_path = Path(path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(payload)
    payload.setdefault("created_at", time.strftime("%Y-%m-%dT%H:%M:%S%z"))
    with manifest_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    return str(manifest_path)

def recommend_model_for_task(style: str, vram_profile: str = "16gb", prefer_speed: bool = False, requires_input_image: bool = False) -> list[dict]:
    """Return ranked model recommendations with reasoning for a specific task."""
    recommendations = []
    
    for family, data in MODEL_FAMILY_HINTS.items():
        if requires_input_image and not data.get("requires_input_image"):
            continue
        if not requires_input_image and data.get("requires_input_image"):
            continue
            
        score = 0
        reasons = []
        
        if style in data.get("best_for", []):
            score += 10
            reasons.append(f"Best for {style}")
            
        if prefer_speed and family in ("flux", "z_image", "qwen_image"):
            score += 5
            reasons.append("Fast generation")
            
        if vram_profile == "8gb":
            if "8gb" in data.get("vram_8gb", "") or "lowvram" in data.get("vram_8gb", ""):
                score += 3
            elif "not recommended" in data.get("vram_8gb", ""):
                score -= 10
                reasons.append("Not recommended for 8GB VRAM")
                
        if score >= 0 and data.get("models"):
            recommendations.append({
                "family": family,
                "model": data["models"][0],
                "score": score,
                "reasons": reasons,
                "notes": data.get("notes", "")
            })
            
    recommendations.sort(key=lambda x: x["score"], reverse=True)
    return recommendations
