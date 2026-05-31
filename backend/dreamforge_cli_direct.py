import argparse
import json
import os
import random
import shutil
import sys
import traceback
from pathlib import Path
from types import SimpleNamespace

from PIL import Image


from _paths import BACKEND_ROOT, COMFY_ROOT, PROJECT_ROOT, REPOS_ROOT, extend_sys_path

extend_sys_path()

from dreamforge_agent_tools import (
    add_agent_arguments,
    add_creative_brief_arguments,
    apply_recipe_defaults,
    compile_creative_prompt,
    compile_negative_prompt,
    default_manifest_path,
    load_brand_kit,
    validate_image,
    write_manifest,
)
from dreamforge_cli_inventory import (
    add_inventory_arguments,
    handle_inventory_arguments,
    recommended_generation_models,
    resolve_generation_model,
)


DEFAULT_MODEL = "sd_xl_base_1.0_0.9vae.safetensors"

from modules.model_ui_defaults import (  # noqa: E402
    MODERN_FAMILIES,
    auto_generation_settings,
    hidream_is_dev_variant as _hidream_is_dev_variant,
    infer_model_family,
    performance_preset_name as _hidream_performance_preset,
)


def build_parser():
    parser = argparse.ArgumentParser(description="Smart AI Agent CLI for local DreamForge")
    parser.add_argument("--model", "--base-model", dest="model", default=None, help="Model filename, stem, or relative path")
    parser.add_argument("--prompt", type=str, default="", help="Positive prompt")
    parser.add_argument("--negative-prompt", type=str, default="", help="Negative prompt")
    parser.add_argument("--aspect-ratio", type=str, default=None, help="E.g. 1024x1024")
    parser.add_argument("--width", type=int, default=None, help="Exact output width")
    parser.add_argument("--height", type=int, default=None, help="Exact output height")
    parser.add_argument("--seed", type=int, default=-1)
    parser.add_argument("--image-number", type=int, default=1)
    parser.add_argument("--output", type=str, default=None, help="Final output file or directory")
    parser.add_argument("--performance", default="Speed", help="Speed, Quality, or Custom...")
    parser.add_argument("--steps", type=int, default=None, help="Exact sampling steps")
    parser.add_argument("--cfg-scale", type=float, default=None, help="Guidance scale")
    parser.add_argument("--sampler", default=None, help="Sampler name")
    parser.add_argument("--scheduler", default=None, help="Scheduler name")
    parser.add_argument(
        "--sdxl-styles",
        nargs="+",
        default=None,
        help="Advanced: override SDXL prompt style fragments applied after the selected style recipe",
    )
    parser.add_argument(
        "--prompt-enhancer",
        dest="prompt_enhancer",
        default=None,
        choices=["none", "flufferizer", "hyperprompt", "erniehancer"],
        help="RuinedFooocus-style prompt enhancer (Flufferizer expansion, Hyperprompt, Erniehancer)",
    )
    parser.add_argument("--lora", action="append", default=[], help='LoRA as "filename:weight"')
    parser.add_argument("--input-image", default=None, help="Input image for img2img, Flux Kontext, or Qwen-Image-Edit")
    parser.add_argument(
        "--reference-images",
        nargs="+",
        default=None,
        help="Additional Kontext/control reference images (Krita-style multi-reference)",
    )
    parser.add_argument(
        "--comfy-workflow-api",
        default=None,
        help="Path to ComfyUI Save (API Format) workflow JSON template",
    )
    parser.add_argument(
        "--use-comfy-server",
        action="store_true",
        help="Route generation through the Krita-style managed ComfyUI server",
    )
    parser.add_argument("--upscale-image", default=None, help="Image path to upscale")
    parser.add_argument("--upscale-method", default="2x", help="Upscale method passed to DreamForge")
    parser.add_argument("--edit-type", default="auto", choices=["auto", "kontext", "inpaint", "img2img", "qwen_edit", "outpaint"], help="Type of image edit to perform")
    parser.add_argument("--edit-strength", type=float, default=None, help="Image edit denoise/strength, 0.0 preserves more and 1.0 changes more")
    parser.add_argument(
        "--qwen-edit-mode",
        default="auto",
        choices=["auto", "single", "plus"],
        help="Qwen Image Edit graph: auto (plus when extra reference_images), single, or plus",
    )
    parser.add_argument(
        "--qwen-image-shift",
        type=float,
        default=None,
        help="ModelSamplingAuraFlow shift for Qwen Image / Edit (default 3.1)",
    )
    parser.add_argument(
        "--qwen-scale-megapixels",
        type=float,
        default=None,
        help="Scale edit input to this megapixel budget before VAE encode (e.g. 0.75 for 8GB VRAM)",
    )
    parser.add_argument("--inpaint-mask-path", default=None, help="Mask image path for inpaint edits")
    parser.add_argument("--cn-selection", default="None", help="ControlNet preset selection; use Custom... for direct settings")
    parser.add_argument("--cn-type", default="None", help="ControlNet type: canny, depth, pose, openpose, lineart, scribble, tile")
    parser.add_argument("--controlnet-model", default=None, help="ControlNet filename or relative path under models/controlnet")
    parser.add_argument("--cn-strength", type=float, default=None, help="ControlNet conditioning strength")
    parser.add_argument("--cn-start", type=float, default=None, help="ControlNet start percent")
    parser.add_argument("--cn-stop", type=float, default=None, help="ControlNet end percent")
    parser.add_argument("--outpaint-left", type=int, default=0, help="Pixels to extend left for outpaint")
    parser.add_argument("--outpaint-top", type=int, default=0, help="Pixels to extend top for outpaint")
    parser.add_argument("--outpaint-right", type=int, default=0, help="Pixels to extend right for outpaint")
    parser.add_argument("--outpaint-bottom", type=int, default=0, help="Pixels to extend bottom for outpaint")
    parser.add_argument("--outpaint-amount", type=int, default=256, help="Fallback pixels to extend when using --outpaint-direction")
    parser.add_argument("--outpaint-direction", default="", help="Outpaint direction: left, right, top, bottom, horizontal, vertical")
    parser.add_argument("--outpaint-feathering", type=int, default=40, help="Native ImagePadForOutpaint feathering")
    parser.add_argument("--hires", action="store_true", help="Use DreamForge two-pass hires workflow")
    parser.add_argument("--hires-first-pass-scale", type=float, default=0.5, help="First pass size scale for hires workflow")
    parser.add_argument("--hires-first-width", type=int, default=None, help="Explicit first pass width")
    parser.add_argument("--hires-first-height", type=int, default=None, help="Explicit first pass height")
    parser.add_argument("--hires-first-steps", type=int, default=None, help="First pass sampler steps")
    parser.add_argument("--hires-second-steps", type=int, default=None, help="Second pass refinement steps")
    parser.add_argument("--hires-denoise", type=float, default=0.35, help="Second pass denoise for hires workflow")
    parser.add_argument("--hires-latent-upscale-method", default="bislerp", help="Latent upscale method for hires workflow")
    parser.add_argument("--reference-mode", default="", help="Reference workflow override such as ipadapter")
    parser.add_argument("--ipadapter-model", default=None, help="IPAdapter model filename under models/ipadapter")
    parser.add_argument("--clip-vision-model", default=None, help="CLIP-Vision model filename under models/clip_vision")
    parser.add_argument("--reference-weight", type=float, default=0.65, help="Reference/IPAdapter conditioning weight")
    parser.add_argument("--region-prompt", action="append", default=[], help='Regional prompt as "x,y,width,height:prompt"; can be repeated')
    parser.add_argument("--region-prompts-json", default=None, help="JSON list of regional prompt objects for area composition")
    parser.add_argument("--vram-profile", choices=["auto", "16gb", "8gb", "5gb", "mps"], default="auto",
                        help="Auto-tune model settings for this VRAM target (16gb=RTX 5060 Ti class, 8gb/5gb=low-VRAM, mps=Apple Silicon unified memory)")
    parser.add_argument(
        "--stream-file",
        default=None,
        help="Append JSONL preview/progress events for desktop live preview (disables silent mode)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Resolve prompt/model/settings without loading GPU models")
    parser.add_argument("--brain-plan", action="store_true", help="Plan operations with the DreamForge AI Brain without executing")
    parser.add_argument("--brain-provider", default="auto", help="Brain runtime: auto, embedded, ollama, lmstudio, llama_cpp_server, openai_compatible")
    parser.add_argument("--brain-base-url", default="", help="Local brain endpoint URL for Ollama/LM Studio/llama.cpp server")
    parser.add_argument("--brain-model", default="", help="Local brain model name")
    parser.add_argument("--brain-api-key", default="", help="API key for a trusted local OpenAI-compatible endpoint, if required")
    parser.add_argument(
        "--workflow-mode",
        default=None,
        help="Comfy routing mode (face_detail, arabic_text_composite, ipadapter, hires, …)",
    )
    parser.add_argument(
        "--arabic-text",
        default=None,
        help="Arabic headline text for poster / text-integrate workflows",
    )
    parser.add_argument(
        "--execute-workflow-plan",
        action="store_true",
        help="Execute workflow_plan steps sequentially",
    )
    parser.add_argument(
        "--workflow-plan",
        default=None,
        help="JSON array of workflow_plan steps (or path to a .json file)",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    parser.add_argument("--batch", type=str, help="Path to a JSONL batch file")
    add_agent_arguments(parser)
    add_creative_brief_arguments(parser)
    add_inventory_arguments(parser)
    return parser


args = None
unknown_args = []


def parse_cli(argv=None):
    global args, unknown_args
    if argv is None:
        argv = list(sys.argv[1:])
    else:
        argv = list(argv)

    # Subcommand extraction
    subcommand = None
    if argv and argv[0] in ("generate", "edit", "remove-object", "inpaint", "upscale", "plan", "serve"):
        subcommand = argv.pop(0)

    # Handle positional prompt or images for the subcommands
    if subcommand == "generate":
        # If there is a next argument that is not a flag, treat it as --prompt
        if argv and not argv[0].startswith("-"):
            prompt_val = argv.pop(0)
            argv.extend(["--prompt", prompt_val])
    elif subcommand == "edit":
        # If there is a next argument that is not a flag, treat it as --input-image
        if argv and not argv[0].startswith("-"):
            img_val = argv.pop(0)
            argv.extend(["--input-image", img_val])
        # If prompt is also positional (like edit image.jpg "prompt"), handle that:
        if argv and not argv[0].startswith("-"):
            prompt_val = argv.pop(0)
            argv.extend(["--prompt", prompt_val])
        argv.extend(["--edit-type", "auto"])
    elif subcommand == "remove-object":
        if argv and not argv[0].startswith("-"):
            img_val = argv.pop(0)
            argv.extend(["--input-image", img_val])
        if argv and not argv[0].startswith("-"):
            prompt_val = argv.pop(0)
            argv.extend(["--prompt", prompt_val])
        argv.extend(["--edit-type", "kontext"])
    elif subcommand == "inpaint":
        if argv and not argv[0].startswith("-"):
            img_val = argv.pop(0)
            argv.extend(["--input-image", img_val])
        argv.extend(["--edit-type", "inpaint"])
    elif subcommand == "upscale":
        # If there is a next argument that is not a flag, treat it as --upscale-image
        if argv and not argv[0].startswith("-"):
            img_val = argv.pop(0)
            argv.extend(["--upscale-image", img_val])
        argv.extend(["--style", "image_edit"])
        argv.extend(["--use-comfy-server"])
    elif subcommand == "plan":
        if "--prompt" not in argv:
            value_flags = {
                "--model", "--base-model", "--negative-prompt", "--aspect-ratio",
                "--width", "--height", "--seed", "--image-number", "--output",
                "--performance", "--steps", "--cfg-scale", "--sampler", "--scheduler",
                "--brain-provider", "--brain-base-url", "--brain-model", "--brain-api-key",
            }
            for index, item in enumerate(list(argv)):
                prev = argv[index - 1] if index > 0 else ""
                if not item.startswith("-") and prev not in value_flags:
                    prompt_val = argv.pop(index)
                    argv.extend(["--prompt", prompt_val])
                    break
        argv.extend(["--brain-plan"])

    parser = build_parser()
    args, unknown_args = parser.parse_known_args(argv)
    args.styles = list(getattr(args, "sdxl_styles", None) or [])
    args.subcommand = subcommand
    return args, unknown_args


def _normalize_styles(styles):
    if not styles:
        return []
    if len(styles) == 1 and isinstance(styles[0], list):
        return styles[0]
    return list(styles)


def _default_prompt_enhancer(model_family: str) -> str:
    from dreamforge_prompt import default_prompt_enhancer

    return default_prompt_enhancer(model_family)


def _is_modern_family_for_enhancer(family: str | None) -> bool:
    fam = (family or "").lower()
    modern = ("flux", "qwen", "hidream", "sd3")
    return any(fam == item or fam.startswith(f"{item}_") for item in modern)


def _auto_detect_platform():
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
    except ImportError:
        pass
    return "cpu"

def _normalize_vram_profile(profile):
    if profile in ("5gb", "lowvram"):
        return "5gb"
    if profile in ("8gb", "midvram"):
        return "8gb"
    if profile in ("16gb", "rtx5060ti16"):
        return "16gb"
    if profile in (None, "auto", ""):
        platform = _auto_detect_platform()
        if platform == "mps":
            return "mps"
        if platform == "cuda":
            return "auto"
        return "cpu"
    return profile


def _parse_aspect_ratio(value, width=None, height=None, profile="auto"):
    profile = _normalize_vram_profile(profile)
    if width and height:
        return int(width), int(height)
    if value:
        normalized = value.lower().replace("×", "x").replace(" ", "")
        parts = normalized.split("x")
        if len(parts) == 2:
            return int(parts[0]), int(parts[1])
    if profile == "5gb":
        return 768, 768
    if profile == "8gb":
        return 896, 896
    if profile == "mps":
        return 896, 896
    return 1024, 1024


def _parse_loras(items):
    if isinstance(items, str):
        items = [items]
    loras = []
    for item in items or []:
        if not item:
            continue
        if ":" in item:
            name, weight = item.rsplit(":", 1)
        else:
            name, weight = item, "1.0"
        loras.append(["None", f"{float(weight)} - {name}"])
    return loras


def _resolve_output_paths(images, output):
    if not output:
        return images
    output_path = Path(output)
    if not output_path.is_absolute():
        output_path = PROJECT_ROOT / output_path
    copied = []
    multiple = len(images) > 1 or output_path.suffix == ""
    if output_path.suffix == "" or output_path.is_dir():
        output_path.mkdir(parents=True, exist_ok=True)
        for image in images:
            target = output_path / Path(image).name
            shutil.copy2(image, target)
            copied.append(str(target))
        return copied

    output_path.parent.mkdir(parents=True, exist_ok=True)
    for index, image in enumerate(images):
        target = output_path
        if multiple and index:
            target = output_path.with_name(f"{output_path.stem}_{index + 1}{output_path.suffix}")
        shutil.copy2(image, target)
        copied.append(str(target))
    return copied


def _job_namespace(base_args, data):
    from dreamforge_agent_tools import normalize_generation_params

    payload = vars(base_args).copy()
    for key, value in normalize_generation_params(data or {}).items():
        attr = key.replace("-", "_")
        if attr == "base_model":
            attr = "model"
        payload[attr] = value
    return SimpleNamespace(**payload)


def _resolve_model(model_name, profile, job_dict):
    from dreamforge_model_registry import required_capabilities_for_request
    from dreamforge_cli_inventory import route_best_model, get_fallback_model, check_model_dependencies
    
    capabilities = required_capabilities_for_request(job_dict)
    speed_pref = job_dict.get("performance", "Quality")
    try:
        image_count = int(job_dict.get("image_number") or 1)
    except (TypeError, ValueError):
        image_count = 1
    if image_count > 1 and str(speed_pref).lower() not in {"custom...", "custom"}:
        speed_pref = "Speed"

    if model_name:
        resolved = resolve_generation_model(model_name)
        if resolved:
            return resolved
            
        # Keep the user's explicit selection instead of silently swapping to a fallback.
        return {
            "name": model_name,
            "engine_name": model_name,
            "family": infer_model_family(Path(model_name).name),
            "category": "checkpoints",
            "size_mb": None,
        }
        
    # Auto-route best model for required capabilities and hardware
    best_model = route_best_model(capabilities, profile, speed_pref)
    if best_model:
        return best_model

    resolved = resolve_generation_model(DEFAULT_MODEL)
    if resolved:
        return resolved
    fallback = recommended_generation_models(profile=profile)
    if fallback:
        return fallback[0]
    return {
        "name": DEFAULT_MODEL,
        "engine_name": DEFAULT_MODEL,
        "family": "sdxl",
        "category": "checkpoints",
        "size_mb": None,
    }


def _compile_job(base_args, data=None):
    job = _job_namespace(base_args, data or {})
    if getattr(job, "base_model", None) and not getattr(job, "model", None):
        job.model = job.base_model
    apply_recipe_defaults(job)
    brand_kit = load_brand_kit(getattr(job, "brand_kit", None))
    prompt = compile_creative_prompt(getattr(job, "prompt", ""), job, brand_kit)
    negative = compile_negative_prompt(getattr(job, "negative_prompt", ""), job, brand_kit)
    model = _resolve_model(getattr(job, "model", None), getattr(job, "vram_profile", "auto"), vars(job))
    if getattr(job, "prompt_enhancer", None) in (None, ""):
        job.prompt_enhancer = _default_prompt_enhancer(model.get("family"))
    width, height = _parse_aspect_ratio(
        getattr(job, "aspect_ratio", None),
        getattr(job, "width", None),
        getattr(job, "height", None),
        getattr(job, "vram_profile", "auto"),
    )
    return job, model, prompt, negative, width, height, brand_kit


def _auto_settings(model, job, width, height, negative_prompt):
    family = model.get("family", "sdxl")
    styles = _normalize_styles(getattr(job, "styles", None))
    return auto_generation_settings(
        model["name"],
        family,
        vram_profile=getattr(job, "vram_profile", "auto"),
        user_steps=getattr(job, "steps", None),
        user_cfg=getattr(job, "cfg_scale", None),
        user_sampler=getattr(job, "sampler", None),
        user_scheduler=getattr(job, "scheduler", None),
        user_styles=styles,
        width=width,
        height=height,
        negative_prompt=negative_prompt,
    )


def _apply_edit_recipe_settings(settings: dict, model: dict, job) -> dict:
    """Keep dry-run plans aligned with the runtime edit recipe."""
    edit_type = str(getattr(job, "edit_type", "auto") or "auto").lower()
    has_input = bool(getattr(job, "input_image", None) or getattr(job, "upscale_image", None))
    if not has_input or edit_type not in ("kontext", "inpaint", "img2img", "qwen_edit", "outpaint"):
        return settings
    explicit_sampling = any(
        getattr(job, attr, None) is not None
        for attr in ("steps", "cfg_scale", "sampler", "scheduler")
    )
    if explicit_sampling:
        return settings
    try:
        from dreamforge_krita_recipes import edit_recipe
    except ImportError:
        return settings
    recipe = edit_recipe(str(model.get("family") or ""), edit_type)
    if not recipe:
        return settings
    out = dict(settings)
    out["steps"] = int(recipe.get("custom_steps", out.get("steps", 20)))
    out["cfg"] = float(recipe.get("cfg", out.get("cfg", 3.5)))
    out["sampler_name"] = recipe.get("sampler_name", out.get("sampler_name"))
    out["scheduler"] = recipe.get("scheduler", out.get("scheduler"))
    out["clip_skip"] = int(recipe.get("clip_skip", out.get("clip_skip", 1)))
    if str(model.get("family") or "").startswith("flux") or edit_type == "kontext":
        out["performance_selection"] = "Flux"
    return out


def _apply_generation_recipe_settings(settings: dict, model: dict, job) -> dict:
    family = str(model.get("family") or "").lower()
    has_input = bool(getattr(job, "input_image", None) or getattr(job, "upscale_image", None))
    if has_input or family != "qwen_image":
        return settings
    explicit_sampling = any(
        getattr(job, attr, None) is not None
        for attr in ("steps", "cfg_scale", "sampler", "scheduler")
    )
    if explicit_sampling:
        return settings
    try:
        from dreamforge_krita_recipes import generation_recipe
    except ImportError:
        return settings
    recipe = generation_recipe(family)
    if not recipe:
        return settings
    out = dict(settings)
    out["steps"] = int(recipe.get("custom_steps", out.get("steps", 20)))
    out["cfg"] = float(recipe.get("cfg", out.get("cfg", 2.5)))
    out["sampler_name"] = recipe.get("sampler_name", out.get("sampler_name"))
    out["scheduler"] = recipe.get("scheduler", out.get("scheduler"))
    out["clip_skip"] = int(recipe.get("clip_skip", out.get("clip_skip", 1)))
    return out


def build_plan(base_args, data=None):
    job, model, prompt, negative, width, height, brand_kit = _compile_job(base_args, data)
    settings = _apply_generation_recipe_settings(
        _apply_edit_recipe_settings(
            _auto_settings(model, job, width, height, negative),
            model,
            job,
        ),
        model,
        job,
    )
    input_path = getattr(job, "input_image", None) or getattr(job, "upscale_image", None)
    from dreamforge_cli_inventory import check_model_dependencies, model_fallback_actions, model_setup_warnings
    from dreamforge_model_registry import required_capabilities_for_request

    missing_deps = check_model_dependencies(model)
    setup_warnings = model_setup_warnings(model)
    capabilities = required_capabilities_for_request(vars(job))
    route_actions = model_fallback_actions(
        model,
        capabilities,
        getattr(job, "vram_profile", "auto"),
        getattr(job, "performance", "Quality"),
    )
    workflow_blueprint = None
    try:
        from dreamforge_workflow_planner import build_live_workflow_blueprint, resolve_operations_from_intent

        current_settings = vars(job).copy()
        has_image = bool(getattr(job, "input_image", None) or getattr(job, "upscale_image", None))
        has_mask = bool(getattr(job, "inpaint_mask_path", None))
        has_refs = bool(getattr(job, "reference_images", None) or getattr(job, "control_images", None))
        operations = resolve_operations_from_intent(
            prompt,
            has_image=has_image,
            has_mask=has_mask,
            has_references=has_refs,
        )
        workflow_mode = str(getattr(job, "workflow_mode", "") or "").lower()
        if workflow_mode in ("hires", "hires_fix", "two_pass") and "hires_fix" not in operations:
            operations.append("hires_fix")
        if workflow_mode in ("ipadapter", "reference", "reference_ipadapter") and "reference_guidance" not in operations:
            operations.append("reference_guidance")
        if workflow_mode in ("area", "area_composition", "composite", "composition") and "composite_layers" not in operations:
            operations.append("composite_layers")
        if workflow_mode == "face_detail" and "face_detail" not in operations:
            operations.append("face_detail")
        workflow_blueprint = build_live_workflow_blueprint(
            prompt,
            operations=operations,
            has_image=has_image,
            has_mask=has_mask,
            has_references=has_refs,
            current_settings=current_settings,
        )
    except Exception as exc:
        workflow_blueprint = {
            "status": "error",
            "warnings": [f"Workflow blueprint planning failed: {exc}"],
        }
    return {
        "schema_version": "1.1",
        "status": "planned",
        "prompt": prompt,
        "negative_prompt": settings["negative"],
        "model": model,
        "settings": {
            "width": settings["width"],
            "height": settings["height"],
            "steps": settings["steps"],
            "cfg": settings["cfg"],
            "sampler": settings["sampler_name"],
            "scheduler": settings["scheduler"],
            "styles": settings["styles"],
            "performance_selection": settings.get("performance_selection", "Custom..."),
            "vram_profile": getattr(job, "vram_profile", "auto"),
            "edit_strength": getattr(job, "edit_strength", None),
        },
        "input_image": input_path,
        "reference_images": getattr(job, "reference_images", None),
        "comfy_workflow_api": getattr(job, "comfy_workflow_api", None),
        "manifest_enabled": not getattr(job, "no_manifest", False),
        "brand_kit": brand_kit.get("_path") if isinstance(brand_kit, dict) else None,
        "missing_dependencies": missing_deps,
        "setup_warnings": setup_warnings,
        "recommended_actions": route_actions + list((workflow_blueprint or {}).get("readiness", {}).get("recommended_actions", [])),
        "workflow_blueprint": workflow_blueprint,
        "ready": len(missing_deps) == 0 and bool((workflow_blueprint or {}).get("readiness", {}).get("ready", True)),
    }


def _load_input_image(path):
    if not path:
        return None
    from dreamforge_paths import resolve_image_path_or_raise

    image_path = resolve_image_path_or_raise(path)
    try:
        return Image.open(image_path).convert("RGB")
    except OSError as exc:
        raise ValueError(f"Could not read input image {image_path}: {exc}") from exc


def process_single(base_args, data=None):
    import json
    from pathlib import Path

    from dreamforge_comfy_server import boot_managed_comfy_server
    from dreamforge_engine import DreamForgeEngine

    payload = dict(data or {})
    params = vars(base_args).copy()
    params.update(payload)

    raw_plan = params.get("workflow_plan")
    if raw_plan:
        if isinstance(raw_plan, str):
            plan_path = Path(raw_plan)
            if plan_path.is_file():
                params["workflow_plan"] = json.loads(plan_path.read_text(encoding="utf-8"))
            else:
                params["workflow_plan"] = json.loads(raw_plan)
        else:
            params["workflow_plan"] = raw_plan
    if getattr(base_args, "execute_workflow_plan", False):
        params["execute_workflow_plan"] = True

    os.environ.setdefault("DREAMFORGE_USE_COMFY_SERVER", "1")
    boot_managed_comfy_server()
    return DreamForgeEngine.execute_job(params, stream_sink=params.get("stream_file"))



def _is_mps():
    try:
        import torch
        return hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
    except ImportError:
        return False

def _dreamforge_argv_for_job(job):
    vram_flags = {"--gpu-only", "--highvram", "--normalvram", "--lowvram", "--novram", "--cpu"}
    extra = ["--offline"]
    profile = _normalize_vram_profile(getattr(job, "vram_profile", "auto"))
    model = _resolve_model(getattr(job, "model", None), profile, vars(job))
    family = model.get("family")
    if profile == "mps" or _is_mps():
        extra.append("--normalvram")
    elif profile in ("5gb", "8gb"):
        extra.append("--lowvram")
    elif family in ("flux", "flux2", "z_image"):
        extra.append("--normalvram")
    elif family in ("hidream", "hidream_o1", "qwen_image", "qwen_image_edit"):
        extra.append("--lowvram")
    elif profile == "16gb":
        extra.append("--normalvram")
    return extra


def main():
    global args, unknown_args
    parse_cli()
    
    # Route "serve" subcommand to REST HTTP server
    if getattr(args, "subcommand", None) == "serve":
        from dreamforge_server import run_server
        port = 7777
        for item in unknown_args:
            try:
                port = int(item)
                break
            except ValueError:
                pass
        run_server(port)
        raise SystemExit(0)

    if getattr(args, "hires", False) and not getattr(args, "workflow_mode", None):
        args.workflow_mode = "hires"
    if getattr(args, "reference_mode", "") and not getattr(args, "workflow_mode", None):
        args.workflow_mode = args.reference_mode

    if args.json and (
        args.list_models
        or args.list_fonts
        or args.list_inventory
        or args.list_styles
        or getattr(args, "recommend_models", False)
        or getattr(args, "check_model_deps", None)
        or getattr(args, "classify_models", False)
        or getattr(args, "organize", False)
        or getattr(args, "organize_apply", False)
    ):
        args.inventory_json = True
    if handle_inventory_arguments(args):
        raise SystemExit(0)

    if args.brain_plan:
        from dreamforge_engine import DreamForgeEngine

        current_settings = vars(args).copy()
        selected_image = args.input_image or args.upscale_image or ""
        payload = DreamForgeEngine.plan(
            args.prompt,
            current_settings=current_settings,
            selected_image=selected_image,
            gallery=[],
            brain_provider=args.brain_provider,
            brain_base_url=args.brain_base_url,
            brain_model=args.brain_model,
            brain_api_key=args.brain_api_key,
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2 if args.json else None))
        raise SystemExit(0)

    if args.dry_run:
        from dreamforge_engine import DreamForgeEngine

        if args.batch:
            plans = []
            with open(args.batch, "r", encoding="utf-8") as handle:
                for line in handle:
                    if line.strip():
                        plans.append(DreamForgeEngine.dry_run(json.loads(line)))
            payload = {"schema_version": "1.1", "status": "planned", "results": plans}
        else:
            params = vars(args).copy()
            payload = DreamForgeEngine.dry_run(params)
        print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json else payload)
        raise SystemExit(0)


    if args.json:
        sys.stdout = sys.stderr

    from dreamforge_comfy_server import boot_managed_comfy_server

    os.environ.setdefault("DREAMFORGE_USE_COMFY_SERVER", "1")
    boot_managed_comfy_server()

    results = []
    if args.batch:
        with open(args.batch, "r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    results.append(process_single(args, json.loads(line)))
    else:
        results.append(process_single(args))

    status = "success" if all(item.get("status") == "success" for item in results) else "error"
    payload = {
        "schema_version": "1.1",
        "status": status,
        "results": results,
        "images": [image for item in results for image in item.get("images", [])],
    }
    if args.json:
        sys.stdout = sys.__stdout__
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(payload)


if __name__ == "__main__":
    main()
else:
    # Allow importing helpers without triggering CLI parse / GPU boot.
    args = SimpleNamespace()
    unknown_args = []
