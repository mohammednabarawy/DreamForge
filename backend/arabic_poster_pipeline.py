"""
Arabic Poster Pipeline - End-to-end orchestrator for generating images with
correct Arabic text using DreamForge.

THE FUNDAMENTAL TRUTH: SDXL cannot natively generate correct Arabic text.
The model lacks Arabic glyph understanding in its weights. This pipeline
solves the problem with a 3-step process:

  1. GENERATE: DreamForge creates the artistic scene/background (no text)
  2. COMPOSITE: PIL renders pixel-perfect Arabic text onto the scene
  3. HARMONIZE: DreamForge img2img at low denoise blends the text into
     the scene's style/lighting/texture — making it look PAINTED IN,
     not pasted on top.

Usage:
    python arabic_poster_pipeline.py \\
        --arabic-text "مرحبا بالعالم" \\
        --scene-prompt "A beautiful luxury hotel lobby, marble floors, golden lighting" \\
        --output final_poster.png

    python arabic_poster_pipeline.py \\
        --arabic-text "بسم الله الرحمن الرحيم" \\
        --scene-prompt "elegant Islamic geometric pattern background, dark blue and gold" \\
        --text-position bottom --text-effect shadow --darken 0.4 \\
        --harmonize 0.35 --output islamic_art.png
"""

import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import argparse
import subprocess
import time
import json
import glob
import shutil
from PIL import Image

from _paths import BACKEND_ROOT, PROJECT_ROOT, PYTHON_EXE, extend_sys_path

extend_sys_path()

from dreamforge_cli_inventory import (
    add_inventory_arguments,
    handle_inventory_arguments,
    resolve_font_identifier,
    resolve_model_name,
)
from dreamforge_agent_tools import (
    add_agent_arguments,
    apply_recipe_defaults,
    append_unique_phrases,
    compile_creative_prompt,
    compile_negative_prompt,
    default_manifest_path,
    load_brand_kit,
    validate_image,
    write_manifest,
)


PROMPT_PROFILES = {
    "nano_banana_pro": [
        "studio-quality commercial design",
        "precise visual hierarchy",
        "controlled typography area",
        "premium editorial composition",
        "high-fidelity materials and lighting",
    ],
    "image2": [
        "clean high-end generative image aesthetic",
        "strong subject clarity",
        "natural light behavior",
        "polished production-ready advertising layout",
        "minimal visual clutter",
    ],
    "product_ad": [
        "premium product advertising",
        "clear focal subject",
        "negative space reserved for headline text",
        "brand campaign quality",
        "sharp realistic details",
    ],
    "infographic": [
        "organized infographic-style layout",
        "clear sections with generous spacing",
        "simple readable visual hierarchy",
        "clean background",
        "balanced graphic composition",
    ],
    "cinematic": [
        "cinematic art direction",
        "dramatic but controlled lighting",
        "film still composition",
        "rich atmosphere",
        "professional color grading",
    ],
    "signage": [
        "realistic sign surface",
        "text area integrated into the physical material",
        "believable shadows and reflections",
        "clear foreground placement",
        "high contrast lettering zone",
    ],
}


def _run_dreamforge_cmd(cmd, label="DreamForge"):
    """Run a DreamForge CLI command and parse output paths."""
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT_ROOT)

    if result.returncode != 0:
        print(f"[PIPELINE] {label} FAILED!")
        print(f"  STDERR: {result.stderr[-500:]}")
        print(f"  STDOUT: {result.stdout[-500:]}")
        return []

    # Parse output paths from JSON marker
    paths = []
    for line in result.stdout.splitlines():
        if "__OUTPUT_JSON__=" in line:
            json_str = line.split("__OUTPUT_JSON__=", 1)[1]
            paths = json.loads(json_str)
            break

    return paths


def _append_unique_phrases(prompt, phrases):
    """Append prompt phrases without repeating phrases already present."""
    parts = [prompt.strip()] if prompt and prompt.strip() else []
    seen = {part.lower() for part in parts if part}
    for phrase in phrases:
        key = phrase.lower() if phrase else ""
        if phrase and key not in seen:
            parts.append(phrase)
            seen.add(key)
    return ", ".join(parts)


def build_scene_prompt(args):
    """
    Build a more explicit scene prompt from optional creative-brief fields.

    Newer image systems respond well to clear subject/composition/location/style
    instructions. This compiler gives the local DreamForge path the same kind of
    structured brief without needing an external LLM.
    """
    prompt = getattr(args, "scene_prompt", "")

    profile = getattr(args, "prompt_profile", "none")
    if profile != "none":
        prompt = _append_unique_phrases(prompt, PROMPT_PROFILES.get(profile, []))

    prompt = compile_creative_prompt(prompt, args, getattr(args, "_brand_kit", {}))

    return prompt


def build_harmonize_prompt(args, scene_prompt):
    text_role = getattr(args, "text_role", None) or "headline"
    typography = getattr(args, "typography", None) or "legible Arabic typography"
    placement = getattr(args, "text_position", "center")

    phrases = [
        scene_prompt,
        f"integrated {text_role} text",
        typography,
        f"text placement: {placement}",
        "preserve exact letter shapes",
        "natural shadows and reflections around the lettering",
        "text belongs to the scene rather than pasted on top",
    ]
    return _append_unique_phrases("", phrases)


def export_high_res_with_optional_text(final_path, args, temp_dir, actual_font_size=None, actual_font_path=None, index=0):
    """
    Resize final output for 2K/4K-style delivery and optionally repaint crisp text.

    Diffusion stays at the requested generation size for speed/VRAM; export scaling
    is a cheap finishing step that keeps CLI outputs closer to modern generators.
    """
    export_scale = getattr(args, "export_scale", 1.0) or 1.0
    export_width = getattr(args, "export_width", None)
    export_height = getattr(args, "export_height", None)
    export_max_side = getattr(args, "export_max_side", 4096) or 4096

    if export_scale == 1.0 and not export_width and not export_height and not getattr(args, "crisp_export_text", False):
        return final_path

    image = Image.open(final_path).convert("RGB")
    src_w, src_h = image.size

    if export_width and export_height:
        target_w, target_h = export_width, export_height
    elif export_width:
        target_w = export_width
        target_h = round(src_h * (target_w / src_w))
    elif export_height:
        target_h = export_height
        target_w = round(src_w * (target_h / src_h))
    else:
        target_w = round(src_w * export_scale)
        target_h = round(src_h * export_scale)

    scale = min(export_max_side / max(target_w, target_h), 1.0)
    target_w = max(1, round(target_w * scale))
    target_h = max(1, round(target_h * scale))

    if target_w != src_w or target_h != src_h:
        print(f"\n[PIPELINE] Export resize: {src_w}x{src_h} -> {target_w}x{target_h}")
        image = image.resize((target_w, target_h), Image.Resampling.LANCZOS)
        image.save(final_path, quality=95)

    if getattr(args, "crisp_export_text", False):
        scaled_padding = round(args.padding * (target_w / src_w))
        scaled_font_size = round(actual_font_size * (target_w / src_w)) if actual_font_size else None
        repair_path = os.path.join(temp_dir, f"crisp_export_text_{int(time.time())}_{index}.png")
        print("[PIPELINE] Final crisp text pass")
        run_text_compositing(
            arabic_text=args.arabic_text,
            background_path=final_path,
            output_path=repair_path,
            font_style=args.font_style,
            font_path=actual_font_path if actual_font_path else args.font,
            random_font=False,  # Locked to actual_font_path
            effect="none",  # Prevent double shadows/duplicate layers
            position=args.text_position,
            font_size=scaled_font_size,
            opacity=getattr(args, "export_text_opacity", 1.0),
            darken=0.0,
            padding=scaled_padding,
            text_color=args.text_color,
            line_spacing=args.line_spacing,
            wrap=not getattr(args, "no_wrap", False),
            max_lines=args.max_lines,
        )
        shutil.copy2(repair_path, final_path)

    return final_path


def run_dreamforge_generation(
    prompt,
    output_dir,
    width=1152,
    height=896,
    negative_prompt="",
    seed=-1,
    performance="Speed",
    steps=None,
    styles=None,
    base_model=None,
    cfg_scale=7.0,
    sampler="dpmpp_2m_sde_gpu",
    scheduler="karras",
    image_number=1,
    loras=None,
    cn_cpds=None,
    cn_cpds_weight=0.7,
    cn_cpds_stop=0.75,
):
    """
    Run DreamForge image generation via the CLI.
    Returns list of generated image paths.
    """
    python_exe = str(PYTHON_EXE)
    cli_script = os.path.join(BACKEND_ROOT, "dreamforge_cli_direct.py")

    cmd = [
        python_exe, cli_script,
        "--prompt", prompt,
        "--output", output_dir,
        "--aspect-ratio", f"{width}x{height}",
        "--cfg-scale", str(cfg_scale),
        "--sampler", sampler,
        "--scheduler", scheduler,
        "--image-number", str(image_number),
        "--performance", performance,
    ]

    if steps is not None:
        cmd.extend(["--steps", str(steps)])
    if negative_prompt:
        cmd.extend(["--negative-prompt", negative_prompt])
    if seed != -1:
        cmd.extend(["--seed", str(seed)])
    if styles:
        cmd.extend(["--styles"] + styles)
    if base_model:
        cmd.extend(["--base-model", base_model])
    if loras:
        for lora in loras:
            cmd.extend(["--lora", lora])
    if cn_cpds:
        cmd.extend([
            "--cn-cpds", cn_cpds,
            "--cn-cpds-weight", str(cn_cpds_weight),
            "--cn-cpds-stop", str(cn_cpds_stop),
        ])

    print(f"\n{'='*60}")
    print(f"[PIPELINE] Step 1: Generating scene with DreamForge")
    print(f"{'='*60}")
    print(f"  Prompt: {prompt[:100]}...")
    print(f"  Resolution: {width}x{height}")

    paths = _run_dreamforge_cmd(cmd, "Scene generation")

    if not paths:
        # Fallback: find most recent files in output dir
        full_output = os.path.join(PROJECT_ROOT, output_dir)
        candidates = sorted(
            glob.glob(os.path.join(full_output, "dreamforge_*")),
            key=os.path.getmtime,
            reverse=True
        )
        paths = candidates[:image_number]

    print(f"  Generated {len(paths)} image(s)")
    for p in paths:
        print(f"    -> {p}")
    return paths


def run_harmonization(
    composited_image_path,
    output_path,
    prompt,
    negative_prompt="",
    width=1152,
    height=896,
    denoise_strength=0.35,
    seed=-1,
    performance="Speed",
    steps=None,
    styles=None,
    base_model=None,
    cfg_scale=7.0,
    loras=None,
    cn_cpds=None,
    cn_cpds_weight=0.65,
    cn_cpds_stop=0.85,
):
    """
    Run DreamForge img2img at LOW denoise to harmonize composited text.

    This is THE KEY STEP that makes the text look painted into the scene
    rather than pasted on top. At 0.25-0.45 denoise:
    - The diffusion model re-renders the image lightly
    - Text inherits scene lighting, texture, color palette
    - Edges blend naturally
    - Overall structure (text shape) is preserved

    Args:
        composited_image_path: The composited image (scene + text overlay)
        output_path: Where to save the harmonized result
        prompt: Should describe the desired look ("elegant Arabic calligraphy...")
        denoise_strength: 0.25-0.45 for best results (too low = no effect, too high = destroys text)
    """
    python_exe = str(PYTHON_EXE)
    cli_script = os.path.join(BACKEND_ROOT, "dreamforge_cli_direct.py")

    cmd = [
        python_exe, cli_script,
        "--prompt", prompt,
        "--input-image", composited_image_path,
        "--vary-strength", str(denoise_strength),
        "--output", os.path.dirname(output_path) or "outputs",
        "--aspect-ratio", f"{width}x{height}",
        "--cfg-scale", str(cfg_scale),
        "--image-number", "1",
        "--performance", performance,
    ]

    if steps is not None:
        cmd.extend(["--steps", str(steps)])
    if negative_prompt:
        cmd.extend(["--negative-prompt", negative_prompt])
    if seed != -1:
        cmd.extend(["--seed", str(seed)])
    if styles:
        cmd.extend(["--styles"] + styles)
    if base_model:
        cmd.extend(["--base-model", base_model])
    if loras:
        for lora in loras:
            cmd.extend(["--lora", lora])
    if cn_cpds:
        cmd.extend([
            "--cn-cpds", cn_cpds,
            "--cn-cpds-weight", str(cn_cpds_weight),
            "--cn-cpds-stop", str(cn_cpds_stop),
        ])

    print(f"\n{'='*60}")
    print(f"[PIPELINE] Step 3: Harmonizing text with scene (denoise={denoise_strength})")
    print(f"{'='*60}")
    print(f"  Input: {composited_image_path}")
    print(f"  Denoise: {denoise_strength}")

    paths = _run_dreamforge_cmd(cmd, "Harmonization")

    if paths:
        # Copy the harmonized result to the desired output path
        shutil.copy2(paths[0], output_path)
        print(f"  Harmonized: {output_path}")
        return output_path
    else:
        print(f"  [WARNING] Harmonization failed, using composited image as final output")
        shutil.copy2(composited_image_path, output_path)
        return output_path


def run_text_compositing(
    arabic_text,
    background_path,
    output_path,
    font_style="default",
    font_path=None,
    random_font=False,
    effect="shadow",
    position="center",
    font_size=None,
    opacity=1.0,
    darken=0.0,
    padding=60,
    text_color="255,255,255",
    line_spacing=1.4,
    wrap=True,
    max_lines=None,
):
    """
    Composite Arabic text onto a background image.
    Uses the ArabicTextRenderer module.
    """
    print(f"\n{'='*60}")
    print(f"[PIPELINE] Step 2: Compositing Arabic text")
    print(f"{'='*60}")
    print(f"  Text: {arabic_text}")
    print(f"  Background: {background_path}")
    print(f"  Effect: {effect}, Position: {position}")

    # Import renderer
    sys.path.insert(0, BACKEND_ROOT)
    from arabic_text_renderer import ArabicTextRenderer

    renderer = ArabicTextRenderer(font_style=font_style, font_path=font_path, random_font=random_font)

    tc = tuple(int(c) for c in text_color.split(","))

    out_path, actual_font_size = renderer.composite_text_on_image(
        text=arabic_text,
        background_path=background_path,
        output_path=output_path,
        padding=padding,
        text_color=tc,
        effect=effect,
        position=position,
        font_size=font_size,
        opacity=opacity,
        text_area_darken=darken,
        line_spacing=line_spacing,
        wrap=wrap,
        max_lines=max_lines,
    )

    print(f"  Composited: {out_path} (Font Size: {actual_font_size}, Font: {renderer.font_path})")
    return out_path, actual_font_size, renderer.font_path


def create_text_reference(
    arabic_text,
    output_path,
    width,
    height,
    font_style="default",
    font_path=None,
    random_font=False,
    position="center",
    font_size=None,
    padding=60,
    line_spacing=1.4,
    wrap=True,
    max_lines=None,
):
    """Create a crisp text reference image for CPDS/layout guidance."""
    sys.path.insert(0, BACKEND_ROOT)
    from arabic_text_renderer import ArabicTextRenderer

    renderer = ArabicTextRenderer(font_style=font_style, font_path=font_path, random_font=random_font)
    renderer.render_text_image(
        text=arabic_text,
        output_path=output_path,
        width=width,
        height=height,
        padding=padding,
        text_color=(255, 255, 255),
        bg_color=(0, 0, 0),
        effect="none",
        position=position,
        font_size=font_size,
        line_spacing=line_spacing,
        wrap=wrap,
        max_lines=max_lines,
    )
    return output_path, renderer.font_path


def apply_preset(args):
    """Adjust defaults for common text-image quality targets."""
    defaults = {
        "preset": "balanced",
        "final_text_pass": None,
        "text_guide": "none",
        "cn_cpds_weight": 0.65,
        "cn_cpds_stop": 0.85,
        "line_spacing": 1.4,
        "no_wrap": False,
        "max_lines": None,
        "steps": None,
        "prompt_profile": "none",
        "export_scale": 1.0,
        "export_width": None,
        "export_height": None,
        "export_max_side": 4096,
        "crisp_export_text": False,
        "no_crisp_export_text": False,
        "export_text_opacity": 1.0,
    }
    for name, value in defaults.items():
        if not hasattr(args, name):
            setattr(args, name, value)

    preset = getattr(args, "preset", "balanced")
    if preset == "balanced":
        if args.final_text_pass is None:
            args.final_text_pass = 0.0
        if args.font_style == "default":
            args.font_style = "traditional"
            args.random_font = True
        return args

    if preset == "pro_text":
        if args.performance == "Speed":
            args.performance = "Quality"
        if args.steps is None:
            args.steps = 45
        if args.harmonize <= 0:
            args.harmonize = 0.32
        if args.final_text_pass is None:
            args.final_text_pass = 0.0
        if args.text_guide == "none":
            args.text_guide = "harmonize"
        if args.prompt_profile == "none":
            args.prompt_profile = "nano_banana_pro"
        if args.export_scale == 1.0 and args.export_width is None and args.export_height is None:
            args.export_scale = 2.0
        if not args.no_crisp_export_text:
            args.crisp_export_text = True
        if args.darken == 0:
            args.darken = 0.18
        if args.font_style == "default":
            args.font_style = "modern"
            args.random_font = True
        return args

    if preset == "clean_graphic":
        if args.final_text_pass is None:
            args.final_text_pass = 1.0
        if args.harmonize > 0.25:
            args.harmonize = 0.25
        if not args.no_crisp_export_text:
            args.crisp_export_text = True
        if args.prompt_profile == "none":
            args.prompt_profile = "image2"
        if args.font_style == "default":
            args.font_style = "modern"
            args.random_font = True
        return args

    if preset == "neon_sign":
        if args.harmonize <= 0:
            args.harmonize = 0.42
        if args.final_text_pass is None:
            args.final_text_pass = 0.25
        if args.text_effect == "shadow":
            args.text_effect = "glow"
        if args.text_guide == "none":
            args.text_guide = "harmonize"
        if args.prompt_profile == "none":
            args.prompt_profile = "signage"
        if args.font_style == "default":
            args.font_style = "heavy"
            args.random_font = True
        return args

    if args.final_text_pass is None:
        args.final_text_pass = 0.0
    return args


def run_full_pipeline(args):
    """
    Execute the complete Arabic poster generation pipeline.

    Workflow:
      1. Generate scene with DreamForge (prompt describes scene WITHOUT text)
      2. Composite Arabic text onto the generated scene
      3. (Optional) Harmonize with img2img to blend text into scene
    """
    timestamp = int(time.time())
    temp_dir = os.path.join(PROJECT_ROOT, "outputs", "pipeline_temp")
    os.makedirs(temp_dir, exist_ok=True)
    args = apply_recipe_defaults(args, text_pipeline=True)
    args._brand_kit = load_brand_kit(getattr(args, "brand_kit", None))
    args = apply_preset(args)

    wrap = not getattr(args, "no_wrap", False)

    # Auto-enhance prompt to exclude text generation attempts
    scene_prompt = build_scene_prompt(args)
    if not any(kw in scene_prompt.lower() for kw in ["no text", "without text", "text-free", "blank"]):
        scene_prompt += ", no text, no letters, no words, no logos, blank label surfaces, clean background"

    negative = compile_negative_prompt(args.negative_prompt or "", args, args._brand_kit)
    negative = append_unique_phrases(negative, [
        "text",
        "letters",
        "words",
        "typography",
        "writing",
        "watermark",
        "signature",
        "logo",
        "brand name",
        "label text",
        "gibberish text",
        "pseudo text",
        "fake text",
        "random letters",
        "latin letters",
    ])

    text_reference_path = None
    locked_font_path = args.font
    if args.text_guide in ("scene", "harmonize", "both"):
        text_reference_path = os.path.join(temp_dir, f"text_reference_{timestamp}.png")
        text_reference_path, locked_font_path = create_text_reference(
            arabic_text=args.arabic_text,
            output_path=text_reference_path,
            width=args.width,
            height=args.height,
            font_style=args.font_style,
            font_path=args.font,
            random_font=getattr(args, "random_font", False),
            position=args.text_position,
            font_size=args.font_size,
            padding=args.padding,
            line_spacing=args.line_spacing,
            wrap=wrap,
            max_lines=args.max_lines,
        )

    # Step 1: Generate the scene
    scene_paths = run_dreamforge_generation(
        prompt=scene_prompt,
        output_dir="outputs",
        width=args.width,
        height=args.height,
        negative_prompt=negative,
        seed=args.seed,
        performance=args.performance,
        steps=args.steps,
        styles=args.styles,
        base_model=args.base_model,
        cfg_scale=args.cfg_scale,
        image_number=args.image_number,
        loras=args.lora,
        cn_cpds=text_reference_path if args.text_guide in ("scene", "both") else None,
        cn_cpds_weight=args.cn_cpds_weight,
        cn_cpds_stop=args.cn_cpds_stop,
    )

    if not scene_paths:
        print("\n[PIPELINE] FAILED: No scene images were generated.", file=sys.stderr)
        if getattr(args, "json", False):
            print(json.dumps({"status": "error", "error_code": 3, "message": "DreamForge scene generation failed."}))
        sys.exit(3)

    # Step 2 & 3: Composite text + optional harmonization
    final_paths = []
    for i, scene_path in enumerate(scene_paths):
        if args.image_number > 1:
            base, ext = os.path.splitext(args.output)
            out_path = f"{base}_{i}{ext}"
        else:
            out_path = args.output

        # Make output path absolute
        if not os.path.isabs(out_path):
            out_path = os.path.join(PROJECT_ROOT, out_path)

        # Step 2: Composite text
        if args.harmonize > 0:
            # Save intermediate composite to temp
            composite_path = os.path.join(temp_dir, f"composite_{timestamp}_{i}.png")
        else:
            composite_path = out_path

        _, actual_font_size, actual_font_path = run_text_compositing(
            arabic_text=args.arabic_text,
            background_path=scene_path,
            output_path=composite_path,
            font_style=args.font_style,
            font_path=locked_font_path,
            random_font=getattr(args, "random_font", False) if locked_font_path == args.font else False,
            effect=args.text_effect,
            position=args.text_position,
            font_size=args.font_size,
            opacity=args.opacity,
            darken=args.darken,
            padding=args.padding,
            text_color=args.text_color,
            line_spacing=args.line_spacing,
            wrap=wrap,
            max_lines=args.max_lines,
        )

        # Step 3: Harmonize (if enabled)
        if args.harmonize > 0:
            harmonize_prompt = build_harmonize_prompt(args, scene_prompt)
            harmonize_negative = "blurry text, distorted letters, illegible, low quality"

            run_harmonization(
                composited_image_path=composite_path,
                output_path=out_path,
                prompt=harmonize_prompt,
                negative_prompt=harmonize_negative,
                width=args.width,
                height=args.height,
                denoise_strength=args.harmonize,
                seed=args.seed + i if args.seed != -1 else -1,
                performance=args.performance,
                steps=args.steps,
                styles=args.styles,
                base_model=args.base_model,
                cfg_scale=args.cfg_scale,
                loras=args.lora,
                cn_cpds=text_reference_path if args.text_guide in ("harmonize", "both") else None,
                cn_cpds_weight=args.cn_cpds_weight,
                cn_cpds_stop=args.cn_cpds_stop,
            )

            if args.final_text_pass and args.final_text_pass > 0 and not args.crisp_export_text:
                repair_path = os.path.join(temp_dir, f"final_text_pass_{timestamp}_{i}.png")
                print(f"\n[PIPELINE] Final exact-text pass (opacity={args.final_text_pass})")
                run_text_compositing(
                    arabic_text=args.arabic_text,
                    background_path=out_path,
                    output_path=repair_path,
                    font_style=args.font_style,
                    font_path=actual_font_path,
                    random_font=False,  # Locked to actual_font_path
                    effect="none",  # Prevent double shadows/duplicate layers
                    position=args.text_position,
                    font_size=actual_font_size,
                    opacity=args.final_text_pass,
                    darken=0.0,
                    padding=args.padding,
                    text_color=args.text_color,
                    line_spacing=args.line_spacing,
                    wrap=wrap,
                    max_lines=args.max_lines,
                )
                shutil.copy2(repair_path, out_path)

        export_high_res_with_optional_text(out_path, args, temp_dir, actual_font_size, actual_font_path, i)
        final_paths.append(out_path)

    mode = "harmonized" if args.harmonize > 0 else "composited"
    print(f"\n{'='*60}")
    print(f"[PIPELINE] COMPLETE! {len(final_paths)} {mode} image(s) with Arabic text")
    print(f"{'='*60}")
    for p in final_paths:
        print(f"  -> {p}")

    validation = []
    if getattr(args, "validate_output", False):
        validation = [validate_image(path) for path in final_paths]
        for item in validation:
            status = "ok" if item.get("ok") else "warning"
            print(f"  Validation {status}: {item['path']} {item.get('warnings', [])}")

    manifest_path = None
    if not getattr(args, "no_manifest", False):
        manifest_path = getattr(args, "manifest_path", None) or default_manifest_path(final_paths, os.path.join(PROJECT_ROOT, "outputs"))
        write_manifest(manifest_path, {
            "tool": "arabic-poster-cli",
            "use_case": getattr(args, "use_case", "none"),
            "brand_kit": args._brand_kit.get("_path") if isinstance(args._brand_kit, dict) else None,
            "preset": args.preset,
            "prompt_profile": args.prompt_profile,
            "scene_prompt": scene_prompt,
            "negative_prompt": negative,
            "arabic_text": args.arabic_text,
            "base_model": args.base_model,
            "styles": args.styles,
            "loras": args.lora,
            "seed": args.seed,
            "image_number": args.image_number,
            "width": args.width,
            "height": args.height,
            "performance": args.performance,
            "steps": args.steps,
            "harmonize": args.harmonize,
            "text_guide": args.text_guide,
            "cn_cpds_weight": args.cn_cpds_weight,
            "cn_cpds_stop": args.cn_cpds_stop,
            "font_style": args.font_style,
            "font": args.font,
            "text_position": args.text_position,
            "text_effect": args.text_effect,
            "final_text_pass": args.final_text_pass,
            "crisp_export_text": args.crisp_export_text,
            "duplicate_text_layer_risk": bool(args.final_text_pass and args.final_text_pass > 0 and args.crisp_export_text),
            "export": {
                "scale": args.export_scale,
                "width": args.export_width,
                "height": args.export_height,
                "max_side": args.export_max_side,
                "text_opacity": args.export_text_opacity,
            },
            "images": final_paths,
            "validation": validation,
        })
        print(f"  Manifest: {manifest_path}")

    if getattr(args, "json", False):
        print(json.dumps({
            "status": "success",
            "mode": mode,
            "images": final_paths,
            "font_style": args.font_style,
            "manifest": manifest_path,
            "validation": validation,
        }))

    return final_paths


def print_dry_run_plan(args):
    """Print the resolved generation plan without loading diffusion models."""
    args = apply_recipe_defaults(args, text_pipeline=True)
    args._brand_kit = load_brand_kit(getattr(args, "brand_kit", None))
    args = apply_preset(args)
    scene_prompt = build_scene_prompt(args)
    harmonize_prompt = build_harmonize_prompt(args, scene_prompt)
    font_value = resolve_font_identifier(args.font) if args.font else None
    model = resolve_model_name("checkpoints", args.base_model) if args.base_model else None

    plan = {
        "preset": args.preset,
        "use_case": args.use_case,
        "brand_kit": args._brand_kit.get("_path") if isinstance(args._brand_kit, dict) else None,
        "prompt_profile": args.prompt_profile,
        "base_model": args.base_model,
        "base_model_found": bool(model) if args.base_model else None,
        "base_model_path": model["path"] if model else None,
        "font": args.font,
        "font_resolved": font_value,
        "scene_prompt": scene_prompt,
        "negative_prompt": compile_negative_prompt(args.negative_prompt or "", args, args._brand_kit),
        "harmonize_prompt": harmonize_prompt,
        "styles": args.styles,
        "performance": args.performance,
        "steps": args.steps,
        "harmonize": args.harmonize,
        "text_guide": args.text_guide,
        "final_text_pass": args.final_text_pass,
        "export": {
            "scale": args.export_scale,
            "width": args.export_width,
            "height": args.export_height,
            "max_side": args.export_max_side,
            "crisp_text": args.crisp_export_text,
        },
        "manifest_enabled": not args.no_manifest,
        "validate_output": args.validate_output,
    }
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    return plan


def main():
    parser = argparse.ArgumentParser(
        description="Arabic Poster Pipeline - Generate images with correct Arabic text",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
The pipeline works in three phases:
  1. DreamForge generates the artistic scene (WITHOUT text in the image)
  2. Perfect Arabic text is composited on top with professional effects
  3. (Optional) DreamForge img2img re-renders at low denoise to HARMONIZE
     the text into the scene's style, lighting, and texture

The harmonization step is what makes text look PAINTED INTO the scene
rather than pasted on top. Use --harmonize 0.3 to 0.45 for best results.

Examples:
  # Basic (composite only, fast)
  python arabic_poster_pipeline.py \\
      --arabic-text "مرحبا بالعالم" \\
      --scene-prompt "luxury restaurant interior, warm lighting, elegant"

  # With harmonization (text looks integrated into scene)
  python arabic_poster_pipeline.py \\
      --arabic-text "مرحبا بالعالم" \\
      --scene-prompt "luxury restaurant interior, warm lighting, elegant" \\
      --harmonize 0.35

  # Islamic art with Naskh calligraphy, harmonized
  python arabic_poster_pipeline.py \\
      --arabic-text "بسم الله الرحمن الرحيم" \\
      --scene-prompt "intricate Islamic geometric pattern, dark blue and gold" \\
      --font-style naskh --text-effect all --darken 0.3 --harmonize 0.3

  # Business poster (no harmonization needed for clean backgrounds)
  python arabic_poster_pipeline.py \\
      --arabic-text "شركة التقنية المتقدمة\\nحلول مبتكرة للمستقبل" \\
      --scene-prompt "modern tech office, glass building, blue sky" \\
      --text-position bottom --text-effect shadow --darken 0.5

  # Multiple variations
  python arabic_poster_pipeline.py \\
      --arabic-text "مرحبا" \\
      --scene-prompt "mountain sunset landscape" \\
      --image-number 4 --seed 42 --harmonize 0.35
        """
    )

    add_inventory_arguments(parser)
    add_agent_arguments(parser)

    # Required for generation
    parser.add_argument("--arabic-text", default=None,
                        help="Arabic text to render (use \\\\n for newlines)")
    parser.add_argument("--scene-prompt", default=None,
                        help="Prompt describing the SCENE/BACKGROUND (do NOT include text descriptions)")

    # Output
    parser.add_argument("--output", default="arabic_poster.png",
                        help="Output file path")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print resolved model/font/preset/prompt/export plan as JSON without generating")
    parser.add_argument("--json", action="store_true",
                        help="Print final output paths as a structured JSON object (for AI agents)")
    parser.add_argument("--width", type=int, default=1152, help="Image width")
    parser.add_argument("--height", type=int, default=896, help="Image height")

    # Harmonization
    parser.add_argument("--harmonize", type=float, default=0.0,
                        help="Harmonization strength (0=disabled, 0.25-0.45=recommended). "
                             "Makes text look PAINTED INTO the scene via low-denoise img2img.")
    parser.add_argument("--preset", default="balanced",
                        choices=["balanced", "pro_text", "clean_graphic", "neon_sign"],
                        help="Quality preset for Arabic/text image workflows")
    parser.add_argument("--final-text-pass", type=float, default=None,
                        help="Overlay the exact shaped text after harmonization at this opacity. "
                             "Use 0 to disable, 0.25-0.55 for blended repair, 1.0 for exact graphic text.")
    parser.add_argument("--text-guide", default="none",
                        choices=["none", "scene", "harmonize", "both"],
                        help="Use a rendered text reference with CPDS ControlNet for scene, harmonize, or both stages")
    parser.add_argument("--cn-cpds-weight", type=float, default=0.65,
                        help="CPDS text-reference weight when --text-guide is enabled")
    parser.add_argument("--cn-cpds-stop", type=float, default=0.85,
                        help="CPDS text-reference stop step when --text-guide is enabled")

    # Prompt compiler
    parser.add_argument("--prompt-profile", default="none",
                        choices=["none", "nano_banana_pro", "image2", "product_ad", "infographic", "cinematic", "signage"],
                        help="Structured prompt profile inspired by modern text-capable image systems")
    parser.add_argument("--subject", default=None, help="Main subject for the compiled scene prompt")
    parser.add_argument("--composition", default=None, help="Composition/framing, e.g. centered product, wide shot, low angle")
    parser.add_argument("--action", default=None, help="What is happening in the scene")
    parser.add_argument("--location", default=None, help="Where the scene takes place")
    parser.add_argument("--visual-style", default=None, help="Visual style, e.g. photorealistic, editorial, 3D, watercolor")
    parser.add_argument("--lighting", default=None, help="Lighting direction and mood")
    parser.add_argument("--camera", default=None, help="Camera/lens/framing details")
    parser.add_argument("--mood", default=None, help="Emotional tone")
    parser.add_argument("--brand-colors", default=None, help="Brand color palette or color constraints")
    parser.add_argument("--materials", default=None, help="Important surface/material details")
    parser.add_argument("--text-role", default=None, help="Role of the Arabic text, e.g. headline, logo, sign, label")
    parser.add_argument("--typography", default=None, help="Typography treatment for harmonization prompt")

    # Text styling
    parser.add_argument("--font-style", default="default",
                        choices=["default", "naskh", "arabic", "modern", "heavy", "traditional"],
                        help="Font style category for Arabic text")
    parser.add_argument("--font", default=None, help="Custom font file path")
    parser.add_argument("--random-font", action="store_true", 
                        help="Select a random Arabic font from the system (within the style category)")
    parser.add_argument("--text-effect", default="shadow",
                        choices=["none", "outline", "shadow", "glow", "all"],
                        help="Text visual effect")
    parser.add_argument("--text-position", default="center",
                        choices=["center", "top", "bottom"],
                        help="Text placement on the image")
    parser.add_argument("--font-size", type=int, default=None,
                        help="Fixed font size (auto-fit if not set)")
    parser.add_argument("--opacity", type=float, default=1.0,
                        help="Text opacity (0.0-1.0)")
    parser.add_argument("--darken", type=float, default=0.0,
                        help="Darken area behind text for readability (0.0-1.0)")
    parser.add_argument("--padding", type=int, default=60,
                        help="Padding from image edges in pixels")
    parser.add_argument("--text-color", default="255,255,255",
                        help="Text color as R,G,B")
    parser.add_argument("--line-spacing", type=float, default=1.4,
                        help="Line spacing multiplier")
    parser.add_argument("--no-wrap", action="store_true",
                        help="Disable automatic wrapping for long Arabic text")
    parser.add_argument("--max-lines", type=int, default=None,
                        help="Maximum wrapped lines to fit before shrinking the font")

    # DreamForge generation settings
    parser.add_argument("--negative-prompt", default="",
                        help="Negative prompt for scene generation")
    parser.add_argument("--seed", type=int, default=-1, help="Random seed")
    parser.add_argument("--performance", default="Speed",
                        choices=["Speed", "Quality", "Extreme Speed"])
    parser.add_argument("--steps", type=int, default=None,
                        help="Exact diffusion step count (overrides --performance)")
    parser.add_argument("--styles", nargs="+", default=["DreamForge V2"],
                        help="DreamForge style presets")
    parser.add_argument("--base-model", default=None, help="Base model name")
    parser.add_argument("--cfg-scale", type=float, default=7.0)
    parser.add_argument("--image-number", type=int, default=1,
                        help="Number of scene variations to generate")
    parser.add_argument("--lora", action="append",
                        help="LoRA in format 'name:weight' (repeatable)")

    # Export finishing
    parser.add_argument("--export-scale", type=float, default=1.0,
                        help="Resize final output by this scale after generation (pro_text defaults to 2.0)")
    parser.add_argument("--export-width", type=int, default=None,
                        help="Final export width after generation")
    parser.add_argument("--export-height", type=int, default=None,
                        help="Final export height after generation")
    parser.add_argument("--export-max-side", type=int, default=4096,
                        help="Maximum final export side length")
    parser.add_argument("--crisp-export-text", action="store_true",
                        help="Repaint exact Arabic text after export resize for sharper final output")
    parser.add_argument("--no-crisp-export-text", action="store_true",
                        help="Disable preset-enabled final crisp text repaint")
    parser.add_argument("--export-text-opacity", type=float, default=1.0,
                        help="Opacity for crisp export text repaint")

    args = parser.parse_args()

    if handle_inventory_arguments(args):
        return

    if args.arabic_text and args.scene_prompt is None and args.subject:
        args.scene_prompt = args.subject

    if not args.arabic_text or not args.scene_prompt:
        parser.error("--arabic-text and --scene-prompt/--subject are required unless you use an inventory/list command")

    if args.dry_run:
        print_dry_run_plan(args)
        return

    run_full_pipeline(args)


if __name__ == "__main__":
    main()
