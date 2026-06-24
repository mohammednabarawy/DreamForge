"""Model-family UI defaults for DreamForge web UI and DreamForge CLI.

Maps checkpoint / diffusion / unet filenames to recommended Performance presets,
styles, and negative prompts. Filename heuristics match dreamforge_cli_inventory.
"""

from __future__ import annotations

from pathlib import Path

MODERN_FAMILIES = frozenset({
    "flux", "flux2", "flux_kontext", "hidream", "hidream_o1",
    "qwen_image", "qwen_image_edit", "sd3", "z_image", "ideogram4",
    "krea2",
})

GALLERY_CATEGORIES = ("checkpoints", "diffusion_models", "unet")

MODEL_FILE_EXTENSIONS = {".safetensors", ".ckpt", ".pt", ".pth", ".bin", ".gguf"}

DEFAULT_UI_PERFORMANCE = "Lightning"
UNIFIED_PERFORMANCES = ("Lightning", "Speed", "Quality", "Custom...")


def models_root() -> Path:
    from _paths import MODELS_ROOT
    return MODELS_ROOT


def scan_model_category(category: str) -> list[str]:
    """List model files under DreamForge/models/<category> (no CivitAI worker required)."""
    root = models_root() / category
    if not root.is_dir():
        return []
    names = []
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in MODEL_FILE_EXTENSIONS:
            names.append(path.relative_to(root).as_posix())
    return sorted(
        names,
        key=lambda x: (
            f"0{x.casefold()}"
            if str(Path(x).parent) not in (".", "")
            else f"1{x.casefold()}"
        ),
    )

# Legacy performance modes that should collapse into unified family profiles.
MISALIGNED_PERFORMANCE = {
    "hidream": {"Lcm", "Pony XL", "SD3", "Flux", "HiDream", "HiDream Full"},
    "hidream_o1": {"Lcm", "Pony XL", "SD3", "Flux", "HiDream", "HiDream Full"},
    "flux": {"Lcm", "Pony XL", "SD3", "HiDream", "HiDream Full", "Flux"},
    "flux2": {"Lcm", "Pony XL", "SD3", "HiDream", "HiDream Full", "Flux"},
    "flux_kontext": {"Lcm", "Pony XL", "SD3", "HiDream", "HiDream Full", "Flux"},
    "qwen_image": {"Lcm", "Pony XL", "SD3", "HiDream", "HiDream Full", "Flux"},
    "qwen_image_edit": {"Lcm", "Pony XL", "SD3", "HiDream", "HiDream Full", "Flux"},
    "krea2": {"Lcm", "Pony XL", "SD3", "HiDream", "HiDream Full", "Flux"},
    "sd3": {"Lcm", "Pony XL", "HiDream", "HiDream Full", "SD3", "Flux"},
    "ideogram4": {"Lcm", "Pony XL", "SD3", "HiDream", "HiDream Full", "Flux"},
}


def infer_model_family(name: str) -> str:
    lowered = (name or "").lower()
    if "ideogram" in lowered:
        return "ideogram4"
    if "krea2" in lowered or "krea-2" in lowered or "krea_2" in lowered:
        return "krea2"
    if "qwen" in lowered:
        return "qwen_image_edit" if "edit" in lowered else "qwen_image"
    if "hidream" in lowered:
        if "o1" in lowered or "hidream_o1" in lowered:
            return "hidream_o1"
        return "hidream"
    if "flux" in lowered:
        if "klein" in lowered or "flux-2" in lowered or "flux2" in lowered:
            return "flux2"
        if "kontext" in lowered:
            return "flux_kontext"
        if "flux1-fill" in lowered or "flux-fill" in lowered or "flux.1-fill" in lowered:
            return "flux_fill"
        return "flux"
    if "sd3" in lowered or "stable-diffusion-3" in lowered:
        return "sd3"
    if "z_image" in lowered or "z-image" in lowered:
        return "z_image"
    if "hunyuan" in lowered:
        return "hunyuan"
    if "wan" in lowered:
        return "wan"
    sd15_hints = (
        "sd1.5",
        "sd15",
        "v1-5",
        "v1_5",
        "v15",
        "dreamshaper_8",
        "dreamshaper-8",
        "majicmix",
        "deliberate",
        "realisticvision",
        "512-inpainting",
    )
    if any(token in lowered for token in sd15_hints):
        return "sd15"
    return "sdxl"


def hidream_is_dev_variant(model_name: str) -> bool:
    name = (model_name or "").lower()
    return any(token in name for token in ("dev", "fast", "mxfp8", "fp8", "distill", "2604"))


def performance_preset_name(model_name: str, family: str) -> str:
    """Return the unified UI performance name for a model family."""
    name = (model_name or "").lower()
    if family in ("hidream", "hidream_o1") and "full" in name and "dev" not in name:
        return "Quality"
    if family in MODERN_FAMILIES:
        return DEFAULT_UI_PERFORMANCE
    return "Custom..."


def ui_performance_choices() -> list[str]:
    return list(UNIFIED_PERFORMANCES)


def engine_name_for_category(category: str, relative_name: str) -> str:
    """Path DreamForge load_base_model accepts (checkpoints root + ../sibling folders)."""
    if category == "checkpoints":
        return relative_name
    if category in GALLERY_CATEGORIES[1:]:
        return str(Path("..") / category / relative_name)
    return relative_name


def gallery_caption(category: str, relative_name: str) -> str:
    if category == "checkpoints":
        return relative_name
    return f"[{category}] {relative_name}"


def parse_gallery_caption(caption: str) -> tuple[str, str]:
    text = (caption or "").strip()
    if text.startswith("[") and "] " in text:
        tag, name = text.split("] ", 1)
        return tag.strip("["), name.strip()
    return "checkpoints", text


def gallery_model_type_label(
    category: str,
    relative_name: str,
    shared_models=None,
) -> str:
    """Civit baseModel for checkpoints; inferred family label for other folders."""
    if category == "checkpoints" and shared_models is not None:
        ready = getattr(shared_models, "ready", {})
        if ready.get("checkpoints"):
            try:
                meta = shared_models.get_models_by_path("checkpoints", relative_name)
                base = shared_models.get_model_base(meta)
                if base and base != "Unknown":
                    return base
            except (KeyError, TypeError):
                pass
    return family_display_name(infer_model_family(Path(relative_name).name))


def list_gallery_models(filter_text: str = "", shared_models=None) -> list[tuple]:
    """Build Gradio gallery rows: (thumbnail, caption).

    DreamForge model_handler only indexes checkpoints/loras/inbox; diffusion_models
    and unet are scanned from disk so the gallery works at UI build time.
    """
    from modules.util import get_checkpoint_thumbnail

    needle = (filter_text or "").lower()
    rows = []
    for category in GALLERY_CATEGORIES:
        for relative_name in scan_model_category(category):
            haystack = f"{category} {relative_name}".lower()
            if needle and needle not in haystack:
                continue
            caption = gallery_caption(category, relative_name)
            thumb_name = Path(relative_name).name
            rows.append((get_checkpoint_thumbnail(thumb_name), caption))
    return rows


def hidream_o1_placement_hint(category: str, family: str) -> str | None:
    if family != "hidream_o1" or category == "checkpoints":
        return None
    return (
        "Place repackaged HiDream-O1 checkpoints under <code>models/checkpoints/</code> "
        "(e.g. <code>hidream_o1_image_dev_mxfp8.safetensors</code>). "
        "<code>diffusion_models/</code> UNet-only files skip the built-in O1 tokenizer."
    )


def family_display_name(family: str) -> str:
    labels = {
        "hidream_o1": "HiDream O1",
        "hidream": "HiDream I1",
        "flux": "Flux",
        "flux2": "Flux 2",
        "flux_kontext": "Flux Kontext",
        "qwen_image": "Qwen Image",
        "qwen_image_edit": "Qwen Image Edit",
        "sd3": "SD3",
        "sd15": "SD 1.5",
        "sdxl": "SDXL",
        "z_image": "Z-Image",
        "hunyuan": "Hunyuan",
        "wan": "Wan",
        "ideogram4": "Ideogram 4",
        "krea2": "Krea 2",
    }
    return labels.get(family, family)


def should_apply_family_defaults(
    family: str,
    current_performance: str,
    lock_enabled: bool,
    preset_active: bool,
    model_name: str = "",
) -> bool:
    if preset_active:
        return False
    if not lock_enabled:
        return False
    if current_performance == "Custom...":
        return False
    if family == "sdxl":
        return False
    if family in MODERN_FAMILIES:
        return True
    recommended = performance_preset_name(model_name, family)
    if current_performance == recommended:
        return False
    misaligned = MISALIGNED_PERFORMANCE.get(family, set())
    if current_performance in misaligned:
        return True
    if current_performance == DEFAULT_UI_PERFORMANCE:
        return True
    return current_performance != recommended


def family_performance_settings(
    family: str,
    model_name: str = "",
    performance: str = DEFAULT_UI_PERFORMANCE,
) -> dict:
    """Resolve unified UI profiles into model-family sampling settings."""
    perf = performance if performance in UNIFIED_PERFORMANCES else DEFAULT_UI_PERFORMANCE
    name = (model_name or "").lower()
    dev_hidream = hidream_is_dev_variant(model_name)

    if family.startswith("flux"):
        table = {
            "Lightning": (8, 2.0, "euler", "beta"),
            "Speed": (20, 3.0, "euler", "beta"),
            "Quality": (28, 3.5, "euler", "beta"),
        }
    elif family in ("hidream", "hidream_o1"):
        table = {
            "Lightning": (16, 1.0, "euler", "normal"),
            "Speed": (28 if dev_hidream else 36, 1.0 if dev_hidream else 3.0, "euler", "normal"),
            "Quality": (50, 5.0, "euler", "normal"),
        }
    elif family.startswith("qwen"):
        table = {
            "Lightning": (8, 1.5, "euler", "sgm_uniform"),
            "Speed": (20 if "lightning" not in name else 8, 2.5, "euler", "beta"),
            "Quality": (28, 2.5, "euler", "beta"),
        }
    elif family == "ideogram4":
        table = {
            "Lightning": (12, 7.0, "euler", "simple"),
            "Speed": (20, 7.0, "euler", "simple"),
            "Quality": (48, 7.0, "euler", "simple"),
        }
    elif family == "sd3":
        table = {
            "Lightning": (12, 4.0, "dpmpp_2m", "sgm_uniform"),
            "Speed": (30, 5.0, "dpmpp_2m", "sgm_uniform"),
            "Quality": (40, 5.0, "dpmpp_2m", "sgm_uniform"),
        }
    elif family == "z_image":
        table = {
            "Lightning": (12, 2.0, "euler", "simple"),
            "Speed": (20, 3.0, "euler", "simple"),
            "Quality": (32, 3.5, "euler", "simple"),
        }
    elif family == "krea2":
        if "turbo" in name:
            # Distilled 8-step checkpoint: CFG disabled, er_sde / simple.
            table = {
                "Lightning": (8, 1.0, "er_sde", "simple"),
                "Speed": (8, 1.0, "er_sde", "simple"),
                "Quality": (12, 1.0, "er_sde", "simple"),
            }
        else:
            # RAW (undistilled) base checkpoint: needs CFG and more steps.
            table = {
                "Lightning": (28, 3.5, "euler", "simple"),
                "Speed": (36, 3.5, "euler", "simple"),
                "Quality": (52, 3.5, "euler", "simple"),
            }
    else:
        table = {
            "Lightning": (4, 2.0, "dpmpp_sde", "karras"),
            "Speed": (30, 8.0, "dpmpp_2m_sde_gpu", "karras"),
            "Quality": (60, 8.0, "dpmpp_2m_sde_gpu", "karras"),
        }

    steps, cfg, sampler, scheduler = table.get(perf, table[DEFAULT_UI_PERFORMANCE])
    return {
        "custom_steps": steps,
        "cfg": cfg,
        "sampler_name": sampler,
        "scheduler": scheduler,
        "clip_skip": 1,
    }


def resolve_ui_profile(
    model_name: str,
    *,
    category: str = "checkpoints",
    current_performance: str = DEFAULT_UI_PERFORMANCE,
    lock_enabled: bool = True,
    preset_active: bool = False,
) -> dict:
    """Resolve recommended UI values when the user selects a model in the gallery."""
    family = infer_model_family(Path(model_name).name)
    perf = performance_preset_name(model_name, family)
    apply = should_apply_family_defaults(
        family, current_performance, lock_enabled, preset_active, model_name
    )

    styles_clear = family in MODERN_FAMILIES
    negative_clear = (
        family in ("hidream", "hidream_o1", "ideogram4")
        or family.startswith(("flux", "qwen"))
    )

    custom = None
    if apply and family in MODERN_FAMILIES:
        custom = family_performance_settings(family, model_name, perf)

    hints = []
    if apply:
        hints.append(f"Applied <b>{perf}</b> family profile for {family_display_name(family)}.")
    elif family != "sdxl":
        hints.append(
            f"Recommended: <b>{perf}</b> for {family_display_name(family)} "
            "(Custom performance keeps your manual sampling settings)."
        )

    placement = hidream_o1_placement_hint(category, family)
    if placement:
        hints.append(placement)

    if family in ("hidream", "hidream_o1") and hidream_is_dev_variant(model_name):
        hints.append("HiDream Dev Speed: 28 steps, CFG 1.0, no negative prompt, no SDXL styles.")
    elif family in ("hidream", "hidream_o1"):
        hints.append("HiDream Full Quality: 50 steps, CFG 5.0, no SDXL styles.")

    if family.startswith("flux"):
        hints.append("Flux profiles use Euler/beta with low CFG; avoid SDXL style packs.")
    elif family == "ideogram4":
        hints.append(
            "Ideogram 4: use Enhance to build structured JSON from your idea; no negative prompt."
        )

    return {
        "family": family,
        "category": category,
        "engine_name": engine_name_for_category(category, model_name),
        "performance_selection": perf,
        "apply_performance": apply,
        "clear_styles": styles_clear and apply,
        "clear_negative": negative_clear and apply,
        "custom_sampling": custom,
        "hints": hints,
    }


def _custom_sampling_for_family(family: str, model_name: str) -> dict:
    name = (model_name or "").lower()
    if family.startswith("qwen"):
        return {
            "custom_steps": 20 if "lightning" in name else 20,
            "cfg": 2.5,
            "sampler_name": "euler",
            "scheduler": "beta",
            "clip_skip": 1,
        }
    if family == "ideogram4":
        return {
            "custom_steps": 20,
            "cfg": 7.0,
            "sampler_name": "euler",
            "scheduler": "simple",
            "clip_skip": 1,
        }
    if family == "z_image":
        return {
            "custom_steps": 20,
            "cfg": 3.0,
            "sampler_name": "euler",
            "scheduler": "simple",
            "clip_skip": 1,
        }
    if family == "krea2":
        turbo = "turbo" in name
        return {
            "custom_steps": 8 if turbo else 28,
            "cfg": 1.0 if turbo else 3.5,
            "sampler_name": "er_sde" if turbo else "euler",
            "scheduler": "simple",
            "clip_skip": 1,
        }
    return {
        "custom_steps": 30,
        "cfg": 7.0,
        "sampler_name": "dpmpp_2m_sde_gpu",
        "scheduler": "karras",
        "clip_skip": 1,
    }


def format_model_current_html(
    caption: str,
    civit_base: str,
    profile: dict,
    translate_fn=None,
) -> str:
    t = translate_fn or (lambda x, **_: x)
    family = profile.get("family", "sdxl")
    lines = [
        f"<b>{caption}</b>",
        f"{t('Model type')}: {civit_base}",
        f"<span style='color:#8ab4f8'>Family: {family_display_name(family)}</span>",
    ]
    perf = profile.get("performance_selection", "")
    if perf:
        lines.append(f"Performance: <b>{perf}</b>")
    for hint in profile.get("hints", []):
        lines.append(f"<small>{hint}</small>")
    return "<br>".join(lines)


def auto_generation_settings(
    model_name: str,
    family: str | None = None,
    *,
    vram_profile: str = "auto",
    user_steps: int | None = None,
    user_cfg: float | None = None,
    user_sampler: str | None = None,
    user_scheduler: str | None = None,
    user_styles: list | None = None,
    width: int = 768,
    height: int = 768,
    negative_prompt: str = "",
) -> dict:
    """CLI-oriented auto settings (same rules as web UI family profiles)."""
    family = family or infer_model_family(model_name)
    profile = _normalize_vram_profile(vram_profile)

    cfg = 7.0
    steps = 30
    sampler_name = "dpmpp_2m_sde_gpu"
    scheduler = "karras"
    clip_skip = 2
    styles = list(user_styles) if user_styles is not None else []
    negative = negative_prompt

    if family.startswith("flux"):
        cfg, steps = 3.0, 20
        sampler_name, scheduler, clip_skip = "euler", "beta", 1
        styles = []
    elif family in ("hidream", "hidream_o1"):
        dev = hidream_is_dev_variant(model_name)
        cfg = 1.0 if dev else 5.0
        steps = 28 if dev else 50
        sampler_name, scheduler, clip_skip = "euler", "normal", 1
        styles = []
    elif family.startswith("qwen"):
        cfg, steps = 2.5, (20 if "lightning" in model_name.lower() else 20)
        sampler_name, scheduler, clip_skip = "euler", "beta", 1
        styles = []
    elif family == "sd3":
        cfg, steps = 4.5, 28
        sampler_name, scheduler, clip_skip = "dpmpp_2m", "sgm_uniform", 1
        styles = []
    elif family == "ideogram4":
        cfg, steps = 7.0, 20
        sampler_name, scheduler, clip_skip = "euler", "simple", 1
        styles = []
        negative = ""
    elif family == "krea2":
        turbo = "turbo" in model_name.lower()
        cfg = 1.0 if turbo else 3.5
        steps = 8 if turbo else 28
        sampler_name = "er_sde" if turbo else "euler"
        scheduler, clip_skip = "simple", 1
        styles = []
        negative = ""
    elif family == "sd15":
        width, height = min(width, 768), min(height, 768)

    if profile == "5gb":
        width, height = min(width, 896), min(height, 896)
        if family not in ("hidream", "hidream_o1"):
            steps = min(steps, 16)
    elif profile == "8gb":
        width, height = min(width, 1024), min(height, 1024)
        if family not in ("hidream", "hidream_o1"):
            steps = min(steps, 20)
    elif profile == "16gb":
        if family == "ideogram4":
            width, height = min(width, 768), min(height, 768)
        else:
            width, height = min(width, 1344), min(height, 1344)

    if family == "ideogram4":
        if profile in {"8gb", "5gb"}:
            cap = 768 if profile == "8gb" else 512
            width, height = min(width, cap), min(height, cap)

    final_steps = int(user_steps) if user_steps is not None else steps
    if family in ("hidream", "hidream_o1"):
        min_steps = 28 if hidream_is_dev_variant(model_name) else 50
        final_steps = max(final_steps, min_steps)

    return {
        "cfg": user_cfg if user_cfg is not None else cfg,
        "steps": final_steps,
        "performance_selection": performance_preset_name(model_name, family),
        "sampler_name": user_sampler or sampler_name,
        "scheduler": user_scheduler or scheduler,
        "clip_skip": clip_skip,
        "styles": styles,
        "negative": negative,
        "width": width,
        "height": height,
    }


def _normalize_vram_profile(profile: str) -> str:
    from dreamforge_vram_profiles import profile_tier

    return profile_tier(profile or "auto")
