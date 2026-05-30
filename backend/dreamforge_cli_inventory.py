"""Local inventory helpers for DreamForge CLI wrappers.

This module intentionally avoids importing DreamForge internals so listing models,
styles, presets, and system fonts stays fast and does not load GPU libraries.
"""

import argparse
import csv
import json
import os
from pathlib import Path


from _paths import BACKEND_ROOT, PROJECT_ROOT, extend_sys_path

extend_sys_path()
MODELS_ROOT = BACKEND_ROOT / "models"

MODEL_EXTENSIONS = {".safetensors", ".ckpt", ".pt", ".pth", ".bin", ".gguf"}
FONT_EXTENSIONS = {".ttf", ".otf", ".ttc"}

MODEL_CATEGORIES = {
    "checkpoints": "checkpoints",
    "diffusion_models": "diffusion_models",
    "unet": "unet",
    "loras": "loras",
    "vae": "vae",
    "controlnet": "controlnet",
    "upscale_models": "upscale_models",
    "clip": "clip",
    "text_encoders": "text_encoders",
    "clip_vision": "clip_vision",
    "embeddings": "embeddings",
    "inpaint": "inpaint",
}

GENERATION_MODEL_CATEGORIES = ("checkpoints", "diffusion_models", "unet")

FONT_STYLE_ALIASES = {
    "default": ["arial", "segoeui", "tahoma"],
    "naskh": ["dtnaskh0", "dtnaskh1", "dtnaskh2", "arabtype", "arial"],
    "arabic": ["arabtype", "arabsq", "dtnaskh0", "arial"],
    "modern": ["cairo", "tajawal", "almarai", "segoe ui", "segoeui", "tahoma"],
    "heavy": ["impact", "arialbd", "tahomabd", "cairo-bold", "tajawal-bold", "segoeuib"],
    "traditional": ["andalus", "aldhabi", "trado", "tradbdo", "majalla", "arabtype"],
}

LIKELY_ARABIC_FONT_HINTS = (
    "arab",
    "naskh",
    "kufi",
    "urdu",
    "persian",
    "amiri",
    "scheherazade",
    "tahoma",
    "arial",
    "segoe",
    "trado",
    "andalus",
    "aldhabi",
    "majalla",
    "cairo",
    "tajawal",
    "almarai",
)


def _file_info(path, root):
    stat = path.stat()
    rel = path.relative_to(root).as_posix()
    return {
        "name": path.name,
        "stem": path.stem,
        "relative_path": rel,
        "path": str(path),
        "size_mb": round(stat.st_size / (1024 * 1024), 2),
    }


def _scan_files(root, extensions):
    if not root.exists():
        return []
    results = []
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in extensions:
            results.append(_file_info(path, root))
    return sorted(results, key=lambda item: item["relative_path"].lower())


def list_model_inventory():
    categories = {}
    for label, folder in MODEL_CATEGORIES.items():
        categories[label] = _scan_files(MODELS_ROOT / folder, MODEL_EXTENSIONS)

    presets = []
    presets_root = BACKEND_ROOT / "presets"
    if presets_root.exists():
        presets = sorted(path.stem for path in presets_root.glob("*") if path.is_file() and path.suffix.lower() in {".json", ".png"})

    styles = []
    styles_root = BACKEND_ROOT / "sdxl_styles"
    if styles_root.exists():
        for style_file in sorted(styles_root.glob("*.json")):
            try:
                data = json.loads(style_file.read_text(encoding="utf-8"))
            except Exception:
                continue
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and item.get("name"):
                        styles.append(item["name"])
            elif isinstance(data, dict):
                for key, value in data.items():
                    if isinstance(value, dict) and value.get("name"):
                        styles.append(value["name"])
                    else:
                        styles.append(key)
    for style_table in (BACKEND_ROOT / "settings" / "styles.csv", BACKEND_ROOT / "settings" / "styles.default"):
        if not style_table.exists():
            continue
        try:
            with style_table.open("r", encoding="utf-8", newline="") as handle:
                for row in csv.DictReader(handle):
                    name = (row.get("name") or "").strip()
                    if not name or name.startswith(">>>>>>"):
                        continue
                    styles.append(name)
        except Exception:
            continue

    return {
        "models_root": str(MODELS_ROOT),
        "categories": categories,
        "presets": presets,
        "styles": sorted(set(styles), key=str.lower),
    }


def list_system_fonts(font_filter=None):
    font_roots = []
    windir = os.environ.get("WINDIR", r"C:\Windows")
    font_roots.append(Path(windir) / "Fonts")
    local_fonts = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Windows" / "Fonts"
    font_roots.append(local_fonts)

    seen = set()
    fonts = []
    for root in font_roots:
        if not root.exists():
            continue
        for path in root.iterdir():
            if not path.is_file() or path.suffix.lower() not in FONT_EXTENSIONS:
                continue
            key = str(path).lower()
            if key in seen:
                continue
            seen.add(key)
            alias = path.stem.lower()
            item = {
                "alias": alias,
                "name": path.name,
                "path": str(path),
                "extension": path.suffix.lower(),
                "likely_arabic": any(hint in alias for hint in LIKELY_ARABIC_FONT_HINTS),
            }
            fonts.append(item)

    fonts = sorted(fonts, key=lambda item: (not item["likely_arabic"], item["alias"]))
    if font_filter:
        f = font_filter.lower()
        fonts = [
            item for item in fonts
            if f in item["alias"] or f in item["name"].lower() or f in item["path"].lower()
        ]
    return fonts


def resolve_font_identifier(identifier):
    """Resolve a font path or exposed alias/stem to an installed font path."""
    if not identifier:
        return None
    expanded = os.path.expandvars(os.path.expanduser(identifier))
    if os.path.exists(expanded):
        return expanded

    normalized = identifier.lower().strip()
    normalized_stem = Path(normalized).stem
    for font in list_system_fonts():
        candidates = {
            font["alias"],
            font["name"].lower(),
            Path(font["name"]).stem.lower(),
        }
        if normalized in candidates or normalized_stem in candidates:
            return font["path"]
    return identifier


def resolve_model_name(category, model_name):
    """Resolve a model filename/stem/relative path inside an inventory category."""
    if not model_name:
        return None
    inventory = list_model_inventory()
    models = inventory["categories"].get(category, [])
    normalized = model_name.lower().strip()
    normalized_stem = Path(normalized).stem
    for model in models:
        candidates = {
            model["name"].lower(),
            model["stem"].lower(),
            model["relative_path"].lower(),
        }
        if normalized in candidates or normalized_stem in candidates:
            return model
    return None


def _engine_model_name(model):
    """Return a name that DreamForge can load via its checkpoints search root."""
    if not model:
        return None
    category = model.get("category")
    relative_path = model.get("relative_path") or model.get("name")
    if category == "checkpoints":
        return relative_path
    folder = MODEL_CATEGORIES.get(category)
    if folder:
        return str(Path("..") / folder / relative_path)
    return relative_path


def resolve_generation_model(model_name):
    """Resolve text/image generation models across checkpoints, diffusion_models, and unet."""
    for category in GENERATION_MODEL_CATEGORIES:
        model = resolve_model_name(category, model_name)
        if model:
            model = dict(model)
            model["category"] = category
            model["engine_name"] = _engine_model_name(model)
            model["family"] = infer_model_family(model["name"])
            return model
    return None


def infer_model_family(name):
    """Delegate to DreamForge/modules/model_ui_defaults (single source of truth)."""
    import sys

    dreamforge_path = str(BACKEND_ROOT)
    if dreamforge_path not in sys.path:
        sys.path.insert(0, dreamforge_path)
    try:
        from modules.model_ui_defaults import infer_model_family as _infer

        return _infer(name)
    except ImportError:
        lowered = (name or "").lower()
        if "qwen" in lowered:
            return "qwen_image_edit" if "edit" in lowered else "qwen_image"
        if "hidream" in lowered:
            if "o1" in lowered or "hidream_o1" in lowered:
                return "hidream_o1"
            return "hidream"
        if "flux" in lowered:
            return "flux"
        if "sd3" in lowered:
            return "sd3"
        return "sdxl"


def _family_rank_for_profile(model, profile):
    name = model["name"].lower()
    size_mb = model.get("size_mb") or 0
    score = 0
    if profile in ("5gb", "lowvram"):
        if any(token in name for token in ("q2", "q3", "q4", "fp4", "nf4", "svdq")):
            score += 40
        if "fp8" in name:
            score += 20
        score -= int(size_mb / 1024)
    elif profile in ("8gb", "midvram"):
        if any(token in name for token in ("q3", "q4", "q5", "fp4", "fp8", "mxfp8", "svdq")):
            score += 30
        if any(token in name for token in ("bf16", "full_f16")):
            score -= 15
        score -= max(0, int((size_mb - 12288) / 1024))
    elif profile in ("16gb", "rtx5060ti16"):
        if any(token in name for token in ("q4", "q5", "fp8", "mxfp8", "svdq")):
            score += 35
        if any(token in name for token in ("fp16", "bf16", "full_f16")):
            score -= 25
        score -= max(0, int((size_mb - 16384) / 1024))
    else:
        if any(token in name for token in ("fp8", "q5", "q6", "q8")):
            score += 20
    return score


def detect_vram_profile():
    """Best-effort local hardware profile without requiring GPU libraries for import."""
    env_profile = (os.environ.get("DREAMFORGE_DESKTOP_VRAM_MODE") or os.environ.get("DREAMFORGE_VRAM_PROFILE") or "").lower()
    if env_profile and env_profile not in {"auto", "default"}:
        return env_profile
    try:
        import torch  # type: ignore

        if torch.cuda.is_available():
            props = torch.cuda.get_device_properties(0)
            total_gb = props.total_memory / (1024 ** 3)
            if total_gb >= 14:
                return "16gb"
            if total_gb >= 7:
                return "8gb"
            if total_gb >= 4:
                return "5gb"
            return "lowvram"
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
    except Exception:
        pass
    return "no_gpu"


def normalize_vram_profile(profile):
    profile = (profile or "auto").lower()
    if profile in {"auto", "default"}:
        return detect_vram_profile()
    if profile in {"low", "lowvram", "5gb"}:
        return "5gb"
    if profile in {"mid", "midvram", "8gb"}:
        return "8gb"
    if profile in {"high", "16gb", "rtx5060ti16"}:
        return "16gb"
    if profile in {"cpu", "nogpu", "no_gpu", "none"}:
        return "no_gpu"
    return profile


def _estimate_route_vram_gb(model):
    """Fast model-size estimate used by the router before preflight runs."""
    size_mb = model.get("size_mb") or 0
    try:
        size_gb = float(size_mb) / 1024.0
    except (TypeError, ValueError):
        return None
    if not size_gb:
        return None
    name = (model.get("name") or "").lower()
    family = (model.get("family") or "").lower()
    if ".gguf" in name or any(tag in name for tag in ("q2_", "q3_", "q4_", "q5_", "q6_", "q8_")):
        return round(size_gb * 1.1 + 1.5, 2)
    if any(tag in name for tag in ("fp8", "e4m3", "e5m2", "nf4", "fp4", "svdq")):
        if family.startswith("flux"):
            return round(min(size_gb * 0.75 + 2.5, 14.5), 2)
        return round(size_gb * 0.8 + 2.0, 2)
    if family.startswith("flux"):
        return 24.0 if size_gb > 18 else round(size_gb * 0.95 + 4.0, 2)
    if family == "sd15":
        return round(size_gb * 1.25, 2)
    if family == "sdxl":
        return round(size_gb * 1.45, 2)
    if family.startswith("qwen"):
        return round(size_gb * 1.55, 2)
    if family.startswith("hidream"):
        return round(size_gb * 1.6, 2)
    return round(size_gb * 1.4, 2)


def _profile_vram_budget_gb(profile):
    profile = normalize_vram_profile(profile)
    return {
        "no_gpu": 0.0,
        "mps": 8.0,
        "5gb": 5.0,
        "8gb": 8.0,
        "16gb": 16.0,
    }.get(profile)


def hidream_o1_placement_hint(model):
    """HiDream-O1 repackaged weights should load via checkpoints (aio), not raw diffusion_models."""
    if not model or model.get("family") != "hidream_o1":
        return None
    if model.get("category") == "checkpoints":
        return None
    return (
        "Place Comfy-Org repackaged HiDream-O1 checkpoints under DreamForge/models/checkpoints/ "
        "(e.g. hidream_o1_image_dev_mxfp8.safetensors). diffusion_models/ loads UNet-only and "
        "skips the built-in HiDream-O1 tokenizer unless the file is a full checkpoint."
    )


MODEL_DEPENDENCIES = {
    "hidream_o1": [
        {
            "id": "gemma4_prompt_refine_optional",
            "relative": "text_encoders/gemma4_e4b_it_fp8_scaled.safetensors",
            "note": "Optional: reasoning prompt agent (Comfy HiDream O1 template). Generation works without it.",
            "optional": True,
        },
    ],
    "qwen_image": [
        {
            "id": "clip_qwen25_vl_7b",
            "relative": "clip/qwen_2.5_vl_7b_fp8_scaled.safetensors",
            "note": "Required for Qwen Image generation. Placed in clip or text_encoders.",
        },
        {
            "id": "vae_qwen_image",
            "relative": "vae/qwen_image_vae.safetensors",
            "note": "Qwen image VAE.",
        },
    ],
    "qwen_image_edit": [
        {
            "id": "clip_qwen25_gguf_compatible",
            "relative": "clip/Qwen2.5-VL-7B-Instruct-Q4_K_S.gguf",
            "note": "Recommended for Qwen_Image_Edit-*.gguf.",
        },
        {
            "id": "clip_qwen25_edit_gguf",
            "relative": "clip/qwen_2.5_vl_7b_edit-q2_k.gguf",
            "note": "Legacy pathdb file; architecture 'pig' is rejected by the bundled GGUF loader.",
            "optional": True,
        },
        {
            "id": "vae_qwen_image",
            "relative": "vae/qwen_image_vae.safetensors",
            "note": "Qwen image VAE.",
        },
    ],
    "flux": [
        {
            "id": "vae_flux_ae",
            "relative": "vae/ae.safetensors",
            "note": "Flux VAE (ae.safetensors).",
        },
        {
            "id": "clip_l_flux",
            "relative": "text_encoders/clip_l.safetensors",
            "note": "Flux CLIP-L text encoder.",
        },
        {
            "id": "clip_t5_flux_fp8",
            "relative": "text_encoders/t5xxl_fp8_e4m3fn_scaled.safetensors",
            "note": "Flux T5-XXL scaled fp8 text encoder (VRAM-friendly, Kontext-compatible).",
        },
    ],
    "flux_kontext": [
        {
            "id": "vae_flux_ae",
            "relative": "vae/ae.safetensors",
            "note": "Flux VAE (ae.safetensors).",
        },
        {
            "id": "clip_l_flux",
            "relative": "text_encoders/clip_l.safetensors",
            "note": "Flux CLIP-L text encoder.",
        },
        {
            "id": "clip_t5_flux_fp8",
            "relative": "text_encoders/t5xxl_fp8_e4m3fn_scaled.safetensors",
            "note": "Flux T5-XXL scaled fp8 text encoder (VRAM-friendly, Kontext-compatible).",
        },
        {
            "id": "controlnet_flux_inpaint",
            "relative": "controlnet/FLUX.1-dev-Controlnet-Inpainting-Beta.safetensors",
            "note": "Optional for Flux Kontext inpainting workflows.",
            "optional": True,
        },
    ],
    "flux2": [
        {
            "id": "lora_klein_consistency",
            "relative": "loras/Klein-consistency.safetensors",
            "note": "Recommended LoRA for Flux 2 Klein models.",
            "optional": True,
        },
    ],
}


def _dependency_path(relative: str) -> Path:
    folder, name = relative.split("/", 1) if "/" in relative else ("", relative)
    return MODELS_ROOT / folder / name if folder else MODELS_ROOT / name


# Same weights often live under clip/ or alternate filenames from older installs.
COMPANION_ALTERNATE_PATHS: dict[str, list[str]] = {
    "clip_t5_flux_fp8": [
        "clip/t5xxl_fp8_e4m3fn_scaled.safetensors",
        "text_encoders/t5xxl_fp8_e4m3fn.safetensors",
        "clip/t5xxl_fp8_e4m3fn.safetensors",
    ],
    "clip_l_flux": [
        "clip/clip_l.safetensors",
    ],
    "vae_flux_ae": [
        "vae/flux_vae.safetensors",
    ],
}


def companion_file_present(req: dict, *, min_bytes: int = 1024 * 1024) -> bool:
    """True if a companion file exists at the canonical or known alternate path."""
    relative = req.get("relative") or ""
    if not relative:
        return False
    basename = Path(relative).name
    candidates: list[str] = [
        relative,
        f"text_encoders/{basename}",
        f"clip/{basename}",
    ]
    for alt in COMPANION_ALTERNATE_PATHS.get(req.get("id", ""), []):
        if alt not in candidates:
            candidates.append(alt)
    for rel in candidates:
        path = _dependency_path(rel)
        if path.is_file() and path.stat().st_size >= min_bytes:
            return True
    return False


def check_model_dependencies(model):
    """Return missing companion files for modern model families."""
    if not model:
        return []
    family = model.get("family")
    name = (model.get("name") or "").lower()
    if family == "qwen_image_edit" and not name.endswith(".gguf"):
        return []
    if family == "qwen_image_edit":
        compatible = _dependency_path("clip/Qwen2.5-VL-7B-Instruct-Q4_K_S.gguf")
        if compatible.exists():
            return []
    missing = []
    for req in MODEL_DEPENDENCIES.get(family, []):
        if req.get("optional"):
            continue
        if companion_file_present(req):
            continue
        path = _dependency_path(req["relative"])
        missing.append({**req, "expected_path": str(path)})
    from dreamforge_companion_download import enrich_missing_dependency

    return [enrich_missing_dependency(item) for item in missing]


def check_studio_resources(studio_mode: str, *, upscale_method: str | None = None) -> list[dict]:
    """Missing upscaler/inpaint assets for studio tabs (Krita catalog)."""
    try:
        from dreamforge_krita_resources import check_studio_resources as _check
        from dreamforge_companion_download import enrich_missing_dependency as enrich
    except ImportError:
        return []
    missing = _check(studio_mode, upscale_method=upscale_method)
    return [enrich(item) for item in missing]


def download_studio_resources(studio_mode: str, *, upscale_method: str | None = None) -> dict:
    from dreamforge_companion_download import download_missing_companions

    missing = check_studio_resources(studio_mode, upscale_method=upscale_method)
    if not missing:
        return {"status": "ok", "results": [], "errors": [], "downloaded": 0, "skipped": 0}
    return download_missing_companions(missing)


def model_setup_warnings(model):
    """Non-fatal setup notes (placement, optional enhancers)."""
    warnings = []
    placement = hidream_o1_placement_hint(model)
    if placement:
        warnings.append(placement)
    if model and model.get("family") == "hidream_o1":
        gemma = _dependency_path("text_encoders/gemma4_e4b_it_fp8_scaled.safetensors")
        if not gemma.exists():
            warnings.append(
                "Optional prompt enhancer missing: text_encoders/gemma4_e4b_it_fp8_scaled.safetensors "
                "(Comfy HiDream O1 template; improves reasoning-style prompts, not required for sampling)."
            )
    return warnings


def recommended_generation_models(profile="16gb"):
    profile = normalize_vram_profile(profile)
    inventory = list_model_inventory()
    models = []
    for category in GENERATION_MODEL_CATEGORIES:
        for item in inventory["categories"].get(category, []):
            model = dict(item)
            model["category"] = category
            model["engine_name"] = _engine_model_name(model)
            model["family"] = infer_model_family(model["name"])
            if model["family"] != "sdxl":
                model["profile_score"] = _family_rank_for_profile(model, profile)
                models.append(model)
    return sorted(models, key=lambda item: (item["profile_score"], -item["size_mb"]), reverse=True)


def route_best_model(capabilities, vram_profile="16gb", speed_preference="Quality", exclude_families=None):
    """Find the best available model for a set of capabilities, respecting VRAM and dependencies."""
    from dreamforge_model_registry import supports_capability
    
    exclude_families = exclude_families or set()
    requested_profile = vram_profile or "auto"
    effective_profile = normalize_vram_profile(requested_profile)
    vram_budget = _profile_vram_budget_gb(effective_profile)
    inventory = list_model_inventory()
    candidates = []

    def _looks_like_generation_weight(model):
        name = (model.get("name") or "").lower()
        size_mb = model.get("size_mb") or 0
        if size_mb and size_mb < 1200 and ("diffusion_pytorch_model" in name or name == "model.safetensors"):
            return False
        if size_mb and size_mb < 250:
            return False
        return True
    
    for category in GENERATION_MODEL_CATEGORIES:
        for item in inventory["categories"].get(category, []):
            model = dict(item)
            model["category"] = category
            model["engine_name"] = _engine_model_name(model)
            model["family"] = infer_model_family(model["name"])
            if not _looks_like_generation_weight(model):
                continue
            
            if model["family"] in exclude_families:
                continue
            
            valid = True
            for cap in capabilities:
                if not supports_capability(model["family"], cap):
                    valid = False
                    break
            
            if not valid:
                continue

            estimated_vram = _estimate_route_vram_gb(model)
            model["estimated_vram_gb"] = estimated_vram
            model["requested_vram_profile"] = requested_profile
            model["effective_vram_profile"] = effective_profile
            if vram_budget == 0.0:
                if model.get("family") not in {"sd15", "sdxl"} or (model.get("size_mb") or 0) > 2500:
                    continue
            elif vram_budget is not None and estimated_vram is not None:
                headroom = 1.5 if vram_budget <= 8 else 0.75
                if estimated_vram > vram_budget + headroom:
                    continue
                
            # Check dependencies, if missing, skip as a router candidate
            missing_deps = check_model_dependencies(model)
            if missing_deps:
                continue
                
            model["profile_score"] = _family_rank_for_profile(model, effective_profile)
            family_priority = {
                "flux_kontext": 70,
                "qwen_image_edit": 65,
                "flux": 60,
                "qwen_image": 55,
                "hidream_o1": 50,
                "hidream": 45,
                "sdxl": 40,
                "sd15": 20,
            }
            model["profile_score"] += family_priority.get(model["family"], 10)
            if category == "checkpoints" and (model.get("size_mb") or 0) >= 1500:
                model["profile_score"] += 10
            
            if speed_preference == "Speed":
                # Slightly favor smaller/quantized files for speed
                model["profile_score"] += min(20, max(0, (5000 - (model.get("size_mb") or 0))) / 250)
                name = (model.get("name") or "").lower()
                if any(token in name for token in ("schnell", "turbo", "lightning", "dmd2", "hyper")):
                    model["profile_score"] += 35
                if any(token in name for token in ("dev", "pro", "full_f16", "bf16")) and "schnell" not in name:
                    model["profile_score"] -= 20
            elif speed_preference == "Quality":
                name = (model.get("name") or "").lower()
                if any(token in name for token in ("dev", "juggernaut", "realvis", "epicrealism", "base")):
                    model["profile_score"] += 20
                if any(token in name for token in ("schnell", "turbo", "lightning", "hyper")):
                    model["profile_score"] -= 15
                
            candidates.append(model)
            
    if not candidates:
        return None
        
    # Sort and return best
    candidates = sorted(candidates, key=lambda item: (item["profile_score"], -item.get("estimated_vram_gb") if item.get("estimated_vram_gb") is not None else 0), reverse=True)
    return candidates[0]


def get_fallback_model(failed_model_name, capabilities, vram_profile="16gb", speed_preference="Quality"):
    """Find a fallback model if the requested one is missing or has missing dependencies."""
    failed_model = resolve_generation_model(failed_model_name)
    exclude = set()
    if failed_model:
        exclude.add(failed_model.get("family"))
    return route_best_model(capabilities, vram_profile, speed_preference, exclude_families=exclude)


def model_fallback_actions(model, capabilities, vram_profile="16gb", speed_preference="Quality"):
    """Return structured agent/UI actions for missing companions or unusable model routes."""
    actions = []
    missing = check_model_dependencies(model)
    if missing:
        actions.append(
            {
                "action": "download_model_companions",
                "model": model.get("name") or model.get("engine_name"),
                "family": model.get("family"),
                "missing": missing,
                "hint": "Download or place these companion files, then retry the same selected model.",
            }
        )
    fallback = get_fallback_model(
        model.get("name") or model.get("engine_name"),
        capabilities,
        vram_profile,
        speed_preference,
    )
    if fallback:
        actions.append(
            {
                "action": "switch_model",
                "model": fallback.get("engine_name") or fallback.get("name"),
                "name": fallback.get("name"),
                "family": fallback.get("family"),
                "category": fallback.get("category"),
                "estimated_vram_gb": fallback.get("estimated_vram_gb"),
                "effective_vram_profile": fallback.get("effective_vram_profile"),
                "reason": "Local fallback model is installed and ready for this request.",
            }
        )
    return actions


import random

def find_font_for_style(style="default", custom_path=None, random_choice=False):
    resolved = resolve_font_identifier(custom_path)
    if resolved and os.path.exists(resolved):
        return resolved

    fonts = list_system_fonts()
    by_alias = {font["alias"]: font["path"] for font in fonts}
    
    # Collect all available fonts for the requested style
    available_for_style = []
    for alias in FONT_STYLE_ALIASES.get(style, []):
        if alias in by_alias:
            available_for_style.append(by_alias[alias])
            
    if available_for_style:
        if random_choice:
            return random.choice(available_for_style)
        return available_for_style[0]

    # Fallback to any likely Arabic font
    arabic_fonts = [font["path"] for font in fonts if font["likely_arabic"]]
    if arabic_fonts:
        if random_choice:
            return random.choice(arabic_fonts)
        return arabic_fonts[0]
        
    if fonts:
        if random_choice:
            return random.choice(fonts)["path"]
        return fonts[0]["path"]
        
    raise FileNotFoundError("No usable system font found.")


def print_model_inventory(as_json=False, limit=None):
    inventory = list_model_inventory()
    if as_json:
        print(json.dumps(inventory, ensure_ascii=False, indent=2))
        return

    print(f"Models root: {inventory['models_root']}")
    for category, items in inventory["categories"].items():
        shown = items[:limit] if limit else items
        print(f"\n[{category}] {len(items)} file(s)")
        for item in shown:
            print(f"  {item['name']}  ({item['size_mb']} MB)")
        if limit and len(items) > limit:
            print(f"  ... {len(items) - limit} more")

    print(f"\n[presets] {len(inventory['presets'])}")
    for item in inventory["presets"]:
        print(f"  {item}")

    print(f"\n[styles] {len(inventory['styles'])}")
    for item in inventory["styles"][:limit or len(inventory["styles"])]:
        print(f"  {item}")
    if limit and len(inventory["styles"]) > limit:
        print(f"  ... {len(inventory['styles']) - limit} more")


def print_font_inventory(as_json=False, font_filter=None, limit=None):
    fonts = list_system_fonts(font_filter=font_filter)
    if as_json:
        print(json.dumps(fonts, ensure_ascii=False, indent=2))
        return

    print(f"System fonts: {len(fonts)}")
    shown = fonts[:limit] if limit else fonts
    for font in shown:
        marker = " Arabic-ready" if font["likely_arabic"] else ""
        print(f"  {font['alias']} -> {font['path']}{marker}")
    if limit and len(fonts) > limit:
        print(f"  ... {len(fonts) - limit} more")


def add_inventory_arguments(parser):
    parser.add_argument("--list-models", action="store_true",
                        help="List local DreamForge checkpoints, LoRAs, VAEs, ControlNets, presets, and styles")
    parser.add_argument("--list-fonts", action="store_true",
                        help="List installed system fonts usable with --font")
    parser.add_argument("--list-inventory", action="store_true",
                        help="List both local models/styles and system fonts")
    parser.add_argument("--list-styles", action="store_true",
                        help="List available DreamForge styles only")
    parser.add_argument("--font-filter", default=None,
                        help="Filter --list-fonts output by alias, filename, or path")
    parser.add_argument("--inventory-json", action="store_true",
                        help="Print inventory as JSON")
    parser.add_argument("--inventory-limit", type=int, default=None,
                        help="Limit displayed inventory items per section")
    parser.add_argument("--organize", action="store_true",
                        help="Plan automatic model organization by architecture (dry-run)")
    parser.add_argument("--organize-apply", action="store_true",
                        help="Execute the organization plan (move files into canonical folders)")
    parser.add_argument("--organize-include-low-confidence", action="store_true",
                        help="Include low-confidence (filename-only) verdicts when planning moves")
    parser.add_argument("--recommend-models", action="store_true",
                        help="Rank local generation models for a VRAM profile")
    parser.add_argument("--check-model-deps", metavar="MODEL",
                        help="Check companion files required by a model name or path")
    parser.add_argument("--classify-models", action="store_true",
                        help="Classify every file under the models directory by architecture/role")
    parser.add_argument("--profile", default="16gb",
                        help="VRAM profile for --recommend-models (16gb, 8gb, 5gb, mps, auto)")


def _inventory_wants_json(args) -> bool:
    return bool(getattr(args, "inventory_json", False) or getattr(args, "json", False))


def handle_inventory_arguments(args):
    if getattr(args, "recommend_models", False):
        profile = getattr(args, "profile", None) or getattr(args, "vram_profile", "16gb") or "16gb"
        models = recommended_generation_models(profile=profile)
        payload = {
            "status": "success",
            "profile": profile,
            "models": models,
        }
        if _inventory_wants_json(args):
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(f"Recommended models for {profile}:")
            for item in models[: getattr(args, "inventory_limit", None) or len(models)]:
                print(
                    f"  {item.get('name')}  "
                    f"[{item.get('family')}]  "
                    f"{item.get('size_mb', 0):.0f} MB"
                )
        return True

    if getattr(args, "check_model_deps", None):
        model = resolve_generation_model(args.check_model_deps)
        if not model:
            payload = {
                "status": "error",
                "message": f"Model not found: {args.check_model_deps}",
            }
        else:
            missing = check_model_dependencies(model)
            payload = {
                "status": "success",
                "model": model,
                "ready": len(missing) == 0,
                "missing_dependencies": missing,
                "setup_warnings": model_setup_warnings(model),
            }
        if _inventory_wants_json(args):
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            if payload.get("status") != "success":
                print(payload.get("message", "Model not found"))
            else:
                model_name = payload["model"].get("name", args.check_model_deps)
                if payload["ready"]:
                    print(f"{model_name}: ready")
                else:
                    print(f"{model_name}: missing {len(payload['missing_dependencies'])} companion file(s)")
                    for dep in payload["missing_dependencies"]:
                        print(f"  - {dep.get('relative') or dep.get('label') or dep}")
                for warning in payload.get("setup_warnings") or []:
                    print(f"  note: {warning}")
        return True

    if getattr(args, "classify_models", False):
        payload = {
            "status": "success",
            **_classify_models_payload(
                include_low_confidence=bool(getattr(args, "organize_include_low_confidence", False)),
            ),
        }
        if _inventory_wants_json(args):
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            totals = payload.get("totals", {})
            print(f"Models root: {payload.get('models_root', MODELS_ROOT)}")
            print(f"Files: {totals.get('files', 0)}")
            for family, count in sorted((totals.get("families") or {}).items()):
                print(f"  {family}: {count}")
        return True

    if getattr(args, "organize", False) or getattr(args, "organize_apply", False):
        payload = _organize_payload(
            apply=bool(args.organize_apply),
            include_low_confidence=bool(getattr(args, "organize_include_low_confidence", False)),
        )
        if _inventory_wants_json(args):
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            _print_organize_summary(payload)
        return True

    if not (args.list_models or args.list_fonts or args.list_inventory or args.list_styles):
        return False

    if _inventory_wants_json(args):
        payload = {}
        if args.list_models or args.list_inventory:
            payload["models"] = list_model_inventory()
        if args.list_fonts or args.list_inventory:
            payload["fonts"] = list_system_fonts(font_filter=args.font_filter)
        if args.list_styles:
            payload["styles"] = list_model_inventory()["styles"]
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return True

    if args.list_styles:
        for style in list_model_inventory()["styles"][:args.inventory_limit or None]:
            print(style)
        return True

    if args.list_models or args.list_inventory:
        print_model_inventory(as_json=False, limit=args.inventory_limit)
    if args.list_fonts or args.list_inventory:
        if args.list_models or args.list_inventory:
            print()
        print_font_inventory(as_json=False, font_filter=args.font_filter, limit=args.inventory_limit)
    return True


def _classify_models_payload(include_low_confidence: bool = False):
    """Return a dict-friendly classifier verdict for every model under MODELS_ROOT."""
    from modules.model_classifier import classify_directory  # local import (no GPU)

    classifications = classify_directory(MODELS_ROOT)
    items = [c.as_dict() for c in classifications]
    families: dict[str, int] = {}
    roles: dict[str, int] = {}
    for item in items:
        families[item["family"]] = families.get(item["family"], 0) + 1
        roles[item["role"]] = roles.get(item["role"], 0) + 1
    return {
        "models_root": str(MODELS_ROOT),
        "totals": {"files": len(items), "families": families, "roles": roles},
        "files": items,
    }


def _organize_payload(apply: bool, include_low_confidence: bool) -> dict:
    """Build (and optionally apply) the auto-organization plan."""
    from modules.model_organizer import organize_models  # local import (no GPU)

    return organize_models(
        MODELS_ROOT,
        apply=apply,
        include_low_confidence=include_low_confidence,
    )


def _print_organize_summary(payload: dict) -> None:
    summary = payload.get("summary", {})
    print(f"Models root: {payload.get('models_root', MODELS_ROOT)}")
    print(
        f"Plan: {summary.get('to_move', 0)} to move / "
        f"{summary.get('skipped', 0)} already canonical / "
        f"{summary.get('ambiguous', 0)} ambiguous / "
        f"{summary.get('total', 0)} total"
    )
    if not payload.get("actions"):
        print("(no model files found)")
        return
    for action in payload["actions"]:
        if not action["will_move"]:
            continue
        classification = action["classification"]
        print(
            f"  MOVE {classification['family']:<16} "
            f"{classification['role']:<16} "
            f"{action['source']}\n"
            f"       -> {action['destination']}  "
            f"({classification['confidence']})"
        )
        for sidecar in action.get("sidecars", []):
            print(f"       + sidecar {sidecar['source']} -> {sidecar['destination']}")
    if payload.get("ambiguous"):
        print(f"\nAmbiguous ({len(payload['ambiguous'])}): need manual review")
        for entry in payload["ambiguous"]:
            print(
                f"  ? {entry['family']:<16} {entry['role']:<16} "
                f"{entry['path']} ({entry['confidence']})"
            )
    if payload.get("errors"):
        print("\nErrors:")
        for err in payload["errors"]:
            print(f"  ! {err}")
    if payload.get("applied"):
        result = payload.get("result", {})
        print(
            f"\nApplied: moved={len(result.get('moved', []))} "
            f"failed={len(result.get('failed', []))} "
            f"skipped={len(result.get('skipped', []))}"
        )
        for failure in result.get("failed", []):
            print(f"  FAIL {failure['source']} -> {failure['destination']}: {failure['error']}")


def main():
    parser = argparse.ArgumentParser(description="Inspect local DreamForge models, styles, and fonts.")
    add_inventory_arguments(parser)
    args = parser.parse_args()
    if not handle_inventory_arguments(args):
        parser.print_help()


if __name__ == "__main__":
    main()
