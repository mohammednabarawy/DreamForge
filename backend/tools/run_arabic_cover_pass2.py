"""Pass 2: Quality Qwen Edit scene + Arabic composite + side-by-side compare."""
from __future__ import annotations

import json
import sys
import time
from argparse import Namespace
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from _paths import extend_sys_path

extend_sys_path()

REF_IMAGE = Path(
    r"C:\Users\moham\Desktop\1778182698575-1777642911342-20240709_010711_5aacb593d990bb7575608e3404fdab2b.jpeg"
)
OUT_DIR = BACKEND / "outputs" / "test_runs"
SCENE_PROMPT_FILE = OUT_DIR / "arabic_cover_scene_prompt.txt"
NEG_FILE = OUT_DIR / "arabic_cover_negative.txt"
PASS1_IMAGE = OUT_DIR / "arabic_cover_qwen_speed_test.png"
PASS1_FALLBACK = Path(
    r"D:\DreamForge\outputs\dreamforge\comfy\DreamForge_00033__1780186142710.png"
)

ARABIC_POEM = """صيف ممطر

بعيد عن ربى مضايق
سكران ياناس ومش فايـق
وعشان بعيـد عن ربى
دايما زعلان ومش رايق
نفسي اكون من الصالحين
بتمنى كدة بقالي سنين
لكن ماعملتش حاجة تقربني
وع الحال ده على طول عايشين

من ديوان صيف ممطر
محمد النبراوي"""

SCENE_OUT = OUT_DIR / "arabic_cover_qwen_quality_scene.png"
COMPOSITE_OUT = OUT_DIR / "arabic_cover_quality_composited.png"
HARMONIZED_OUT = OUT_DIR / "arabic_cover_quality_final.png"
COMPARE_OUT = OUT_DIR / "arabic_cover_compare_side_by_side.png"
REPORT_OUT = OUT_DIR / "arabic_cover_pass2_report.json"


def _build_generation_args(*, performance: str, prompt: str, negative: str, output: Path) -> Namespace:
    return Namespace(
        model="qwen_image_edit_2509_fp8_e4m3fn.safetensors",
        prompt=prompt,
        negative_prompt=negative,
        width=832,
        height=1248,
        aspect_ratio=None,
        seed=42,
        image_number=1,
        output=str(output),
        performance=performance,
        steps=None,
        cfg_scale=None,
        sampler=None,
        scheduler=None,
        styles=None,
        lora=[],
        input_image=str(REF_IMAGE),
        reference_images=None,
        comfy_workflow_api=None,
        use_comfy_server=True,
        upscale_image=None,
        upscale_method="2x",
        edit_type="qwen_edit",
        edit_strength=1.0,
        qwen_edit_mode="single",
        qwen_image_shift=None,
        qwen_scale_megapixels=1.0,
        inpaint_mask_path=None,
        cn_selection="None",
        cn_type="None",
        controlnet_model=None,
        cn_strength=None,
        cn_start=None,
        cn_stop=None,
        outpaint_left=0,
        outpaint_top=0,
        outpaint_right=0,
        outpaint_bottom=0,
        outpaint_amount=256,
        outpaint_direction="",
        outpaint_feathering=40,
        hires=False,
        workflow_mode=None,
        reference_mode="",
        vram_profile="16gb",
        style="image_edit",
        validate_output=True,
        no_manifest=False,
        json=True,
        dry_run=False,
        batch=None,
        brain_plan=False,
        subcommand="generate",
    )


def _resolve_pass1() -> Path:
    if PASS1_IMAGE.is_file():
        return PASS1_IMAGE
    if PASS1_FALLBACK.is_file():
        return PASS1_FALLBACK
    raise FileNotFoundError("Pass 1 (Speed) output not found")


def _composite_arabic(scene_path: Path, output_path: Path) -> Path:
    from arabic_text_renderer import ArabicTextRenderer

    bg = Image.open(scene_path)
    width, height = bg.size
    # Right-side typography column (~48% from left edge).
    text_x = int(width * 0.48)
    text_y = int(height * 0.06)

    renderer = ArabicTextRenderer(font_style="naskh")
    out_path, _font_size = renderer.composite_text_on_image(
        text=ARABIC_POEM,
        background_path=str(scene_path),
        output_path=str(output_path),
        padding=36,
        text_color=(235, 198, 92),
        effect="all",
        outline_color=(40, 28, 8),
        outline_width=2,
        shadow_color=(0, 0, 0, 180),
        shadow_offset=(4, 4),
        shadow_blur=6,
        glow_color=(255, 220, 120, 90),
        glow_radius=14,
        position=(text_x, text_y),
        opacity=0.96,
        line_spacing=1.35,
        text_area_darken=0.12,
        wrap=True,
    )
    return Path(out_path)


def _harmonize(composited_path: Path, output_path: Path, scene_prompt: str, negative: str) -> Path:
    from arabic_poster_pipeline import build_harmonize_prompt, run_harmonization

    harmonize_prompt = build_harmonize_prompt(
        Namespace(scene_prompt=scene_prompt, preset="cinematic"),
        scene_prompt,
    )
    run_harmonization(
        composited_image_path=str(composited_path),
        output_path=str(output_path),
        prompt=harmonize_prompt,
        negative_prompt=negative or "blurry text, distorted letters, illegible Arabic, low quality",
        width=Image.open(composited_path).size[0],
        height=Image.open(composited_path).size[1],
        denoise_strength=0.28,
        seed=42,
        performance="Speed",
        base_model="qwen_image_edit_2509_fp8_e4m3fn.safetensors",
        cfg_scale=2.5,
    )
    return output_path if output_path.is_file() else composited_path


def _label(img: Image.Image, title: str) -> Image.Image:
    bar_h = 48
    out = Image.new("RGB", (img.width, img.height + bar_h), (18, 18, 22))
    out.paste(img, (0, bar_h))
    draw = ImageDraw.Draw(out)
    try:
        font = ImageFont.truetype("arial.ttf", 18)
    except OSError:
        font = ImageFont.load_default()
    draw.text((12, 12), title, fill=(230, 230, 235), font=font)
    return out


def _compare(pass1: Path, pass2: Path, out_path: Path) -> None:
    im1 = Image.open(pass1).convert("RGB")
    im2 = Image.open(pass2).convert("RGB")
    target_h = 1200
    im1 = im1.resize(
        (int(im1.width * target_h / im1.height), target_h),
        Image.Resampling.LANCZOS,
    )
    im2 = im2.resize(
        (int(im2.width * target_h / im2.height), target_h),
        Image.Resampling.LANCZOS,
    )
    im1 = _label(im1, "Pass 1 — Speed + Lightning (4 steps, in-prompt typography)")
    im2 = _label(im2, "Pass 2 — Quality scene + Arabic composite pipeline")
    gap = 12
    canvas = Image.new("RGB", (im1.width + im2.width + gap, max(im1.height, im2.height)), (12, 12, 16))
    canvas.paste(im1, (0, 0))
    canvas.paste(im2, (im1.width + gap, 0))
    canvas.save(out_path, quality=95)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report: dict = {"steps": []}

    if not REF_IMAGE.is_file():
        print(json.dumps({"status": "error", "message": f"missing reference: {REF_IMAGE}"}))
        return 1

    scene_prompt = SCENE_PROMPT_FILE.read_text(encoding="utf-8").strip()
    negative = NEG_FILE.read_text(encoding="utf-8").strip() if NEG_FILE.is_file() else ""

    from dreamforge_comfy_server import boot_managed_comfy_server
    from dreamforge_cli_direct import process_single

    import os

    os.environ.setdefault("DREAMFORGE_USE_COMFY_SERVER", "1")

    t0 = time.time()
    print("Booting Comfy…", flush=True)
    boot_managed_comfy_server()

    print("Pass 2a: Quality Qwen Edit (scene-only prompt)…", flush=True)
    gen_args = _build_generation_args(
        performance="Quality",
        prompt=scene_prompt,
        negative=negative,
        output=SCENE_OUT,
    )
    scene_result = process_single(gen_args)
    report["quality_scene"] = scene_result
    if scene_result.get("status") != "success":
        print(json.dumps(scene_result, ensure_ascii=False, indent=2))
        return 1

    scene_path = Path(scene_result["images"][0]["path"])
    if scene_path != SCENE_OUT:
        SCENE_OUT.write_bytes(scene_path.read_bytes())
        scene_path = SCENE_OUT

    print("Pass 2b: Arabic text composite…", flush=True)
    composited = _composite_arabic(scene_path, COMPOSITE_OUT)
    report["composited"] = str(composited)

    print("Pass 2c: Harmonize (denoise 0.28)…", flush=True)
    final_path = _harmonize(composited, HARMONIZED_OUT, scene_prompt, negative)
    report["final"] = str(final_path)

    pass1 = _resolve_pass1()
    _compare(pass1, final_path, COMPARE_OUT)
    report["compare"] = str(COMPARE_OUT)
    report["pass1"] = str(pass1)
    report["elapsed_seconds"] = round(time.time() - t0, 1)

    REPORT_OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
