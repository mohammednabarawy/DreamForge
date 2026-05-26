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
    parser.add_argument("--styles", nargs="+", default=None, help="DreamForge style names")
    parser.add_argument("--style", dest="styles", action="append", help="DreamForge style name; can be repeated")
    parser.add_argument("--lora", action="append", default=[], help='LoRA as "filename:weight"')
    parser.add_argument("--input-image", default=None, help="Input image for img2img, Flux Kontext, or Qwen-Image-Edit")
    parser.add_argument("--upscale-image", default=None, help="Image path to upscale")
    parser.add_argument("--upscale-method", default="2x", help="Upscale method passed to DreamForge")
    parser.add_argument("--edit-type", default="auto", choices=["auto", "kontext", "inpaint", "img2img", "qwen_edit"], help="Type of image edit to perform")
    parser.add_argument("--edit-strength", type=float, default=None, help="Image edit denoise/strength, 0.0 preserves more and 1.0 changes more")
    parser.add_argument("--inpaint-mask-path", default=None, help="Mask image path for inpaint edits")
    parser.add_argument("--vram-profile", choices=["auto", "16gb", "8gb", "5gb", "mps"], default="auto",
                        help="Auto-tune model settings for this VRAM target (16gb=RTX 5060 Ti class, 8gb/5gb=low-VRAM, mps=Apple Silicon unified memory)")
    parser.add_argument(
        "--stream-file",
        default=None,
        help="Append JSONL preview/progress events for desktop live preview (disables silent mode)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Resolve prompt/model/settings without loading GPU models")
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
    parser = build_parser()
    args, unknown_args = parser.parse_known_args(argv)
    return args, unknown_args


def _normalize_styles(styles):
    if not styles:
        return ["Style: sai-enhance", "Style: sai-photographic"]
    if len(styles) == 1 and isinstance(styles[0], list):
        return styles[0]
    return styles


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


def _resolve_model(model_name, profile):
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
    model = _resolve_model(getattr(job, "model", None), getattr(job, "vram_profile", "auto"))
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


def build_plan(base_args, data=None):
    job, model, prompt, negative, width, height, brand_kit = _compile_job(base_args, data)
    settings = _auto_settings(model, job, width, height, negative)
    input_path = getattr(job, "input_image", None) or getattr(job, "upscale_image", None)
    from dreamforge_cli_inventory import check_model_dependencies, model_setup_warnings

    missing_deps = check_model_dependencies(model)
    setup_warnings = model_setup_warnings(model)
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
        "manifest_enabled": not getattr(job, "no_manifest", False),
        "brand_kit": brand_kit.get("_path") if isinstance(brand_kit, dict) else None,
        "missing_dependencies": missing_deps,
        "setup_warnings": setup_warnings,
        "ready": len(missing_deps) == 0,
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
    from dreamforge_generation import boot_headless, run_generation

    job = _job_namespace(base_args, data or {})
    stream_file = getattr(job, "stream_file", None)
    extra_argv = _dreamforge_argv_for_job(job)
    boot_headless(extra_argv)
    return run_generation(base_args, data, stream_sink=stream_file)


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
    model = _resolve_model(getattr(job, "model", None), profile)
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
    if args.json and (args.list_models or args.list_fonts or args.list_inventory or args.list_styles):
        args.inventory_json = True
    if handle_inventory_arguments(args):
        raise SystemExit(0)

    if args.dry_run:
        if args.batch:
            plans = []
            with open(args.batch, "r", encoding="utf-8") as handle:
                for line in handle:
                    if line.strip():
                        plans.append(build_plan(args, json.loads(line)))
            payload = {"schema_version": "1.1", "status": "planned", "results": plans}
        else:
            payload = build_plan(args)
        print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json else payload)
        raise SystemExit(0)

    if args.json:
        sys.stdout = sys.stderr

    from dreamforge_generation import boot_headless

    boot_headless(_dreamforge_argv_for_job(args))

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
