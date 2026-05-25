"""Smoke tests for local CLI inventory, fonts, presets, and advanced text images.

These tests avoid full diffusion generation so they can run quickly on machines
where loading all DreamForge models would be slow or VRAM-heavy.
"""

import os
import sys
from argparse import Namespace
from pathlib import Path

from PIL import Image, ImageDraw, ImageStat

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import arabic_poster_pipeline as pipeline
from arabic_text_renderer import ArabicTextRenderer
from dreamforge_agent_tools import (
    apply_recipe_defaults,
    compile_creative_prompt,
    compile_negative_prompt,
    validate_image,
    write_manifest,
)
from dreamforge_cli_inventory import (
    infer_model_family,
    list_model_inventory,
    list_system_fonts,
    recommended_generation_models,
    resolve_generation_model,
)


OUTPUTS = ROOT / "outputs" / "cli_inventory_tests"


def assert_nonblank_image(path):
    image = Image.open(path).convert("L")
    extrema = ImageStat.Stat(image).extrema[0]
    assert extrema[0] != extrema[1], f"image appears blank: {path}"


def make_background(path, size=(900, 500)):
    image = Image.new("RGB", size, (18, 24, 36))
    draw = ImageDraw.Draw(image)
    for y in range(size[1]):
        tone = int(35 + 80 * (y / max(size[1] - 1, 1)))
        draw.line([(0, y), (size[0], y)], fill=(tone // 2, tone, 100))
    draw.rectangle((50, 50, size[0] - 50, size[1] - 50), outline=(220, 210, 160), width=3)
    image.save(path)
    return path


def test_inventory_has_models_and_fonts():
    inventory = list_model_inventory()
    assert inventory["categories"]["checkpoints"], "no checkpoints found"
    assert inventory["presets"], "no DreamForge presets found"
    assert inventory["styles"], "no DreamForge styles found"

    fonts = list_system_fonts()
    assert fonts, "no system fonts found"
    assert any(font["likely_arabic"] for font in fonts), "no likely Arabic-capable fonts found"


def test_prompt_presets_compile():
    inventory = list_model_inventory()
    models = inventory["categories"]["checkpoints"][:3]
    assert len(models) >= 3, "need at least three checkpoints for model plan smoke test"

    base = dict(
        arabic_text="اختبار",
        scene_prompt="premium technology poster",
        output=str(OUTPUTS / "dummy.png"),
        width=900,
        height=500,
        font_style="default",
        font=None,
        text_effect="shadow",
        text_position="center",
        font_size=None,
        opacity=1.0,
        darken=0.0,
        padding=70,
        text_color="255,255,255",
        negative_prompt="",
        seed=123,
        performance="Speed",
        steps=None,
        styles=["DreamForge V2"],
        base_model=None,
        cfg_scale=7.0,
        image_number=1,
        lora=None,
        harmonize=0.0,
        prompt_profile="none",
        text_guide="none",
        final_text_pass=None,
        cn_cpds_weight=0.65,
        cn_cpds_stop=0.85,
        line_spacing=1.4,
        no_wrap=False,
        max_lines=2,
        export_scale=1.0,
        export_width=None,
        export_height=None,
        export_max_side=4096,
        crisp_export_text=False,
        no_crisp_export_text=False,
        export_text_opacity=1.0,
        subject="glass AI assistant device",
        composition="centered product with clean negative space",
        action=None,
        location=None,
        visual_style="photorealistic advertising",
        lighting="soft studio lighting",
        camera=None,
        mood=None,
        brand_colors="deep blue, white, cyan",
        materials=None,
        text_role="headline",
        typography="bold modern Arabic headline",
        use_case="none",
        brand_kit=None,
        manifest_path=None,
        no_manifest=False,
        validate_output=False,
    )

    for preset in ("balanced", "pro_text", "clean_graphic", "neon_sign"):
        args = Namespace(**base)
        args.preset = preset
        args.base_model = models[0]["name"]
        pipeline.apply_preset(args)
        scene_prompt = pipeline.build_scene_prompt(args)
        harmonize_prompt = pipeline.build_harmonize_prompt(args, scene_prompt)
        assert "premium technology poster" in scene_prompt
        assert "headline" in harmonize_prompt

    args = Namespace(**base)
    args.preset = "pro_text"
    pipeline.apply_preset(args)
    assert args.final_text_pass == 0.0
    assert args.crisp_export_text is True

    for model, preset in zip(models, ("balanced", "pro_text", "clean_graphic")):
        args = Namespace(**base)
        args.preset = preset
        args.base_model = model["stem"]
        args.font = "arial"
        plan = pipeline.print_dry_run_plan(args)
        assert plan["base_model_found"], f"model did not resolve: {model['stem']}"
        assert plan["font_resolved"], "font alias did not resolve"

    args = Namespace(**base)
    args.use_case = "product_ad"
    args.prompt = "wireless headphones"
    args.aspect_ratio = "1152×896"
    apply_recipe_defaults(args)
    compiled = compile_creative_prompt(args.prompt, args, {"colors": ["black", "gold"], "tone": "luxury"})
    negative = compile_negative_prompt("", args, {"forbidden": ["discount badge"]})
    assert "premium product advertising campaign" in compiled
    assert "brand colors: black, gold" in compiled
    assert "discount badge" in negative
    assert args.base_model is not None


def test_modern_model_inventory_and_resolution():
    inventory = list_model_inventory()
    assert inventory["categories"]["diffusion_models"], "modern diffusion_models folder was not inventoried"
    assert inventory["categories"]["text_encoders"], "text_encoders folder was not inventoried"
    assert any(item["name"].lower().endswith(".gguf") for item in inventory["categories"]["diffusion_models"]), "GGUF diffusion models missing"

    flux = resolve_generation_model("flux1-dev-fp8")
    assert flux and flux["family"] == "flux"
    assert flux["engine_name"].endswith("flux1-dev-fp8.safetensors")

    qwen = resolve_generation_model("Qwen_Image_Edit-Q3_K_M")
    assert qwen and qwen["family"] == "qwen_image_edit"
    assert ".." in qwen["engine_name"], "non-checkpoint modern models must be loadable via checkpoint-relative path"

    five_gb_choices = recommended_generation_models("5gb")[:5]
    assert any("flux" in item["name"].lower() for item in five_gb_choices), "5GB profile should prefer quantized Flux-class models"


def test_hidream_o1_family_and_dependencies():
    assert infer_model_family("hidream_o1_image_dev_mxfp8.safetensors") == "hidream_o1"
    assert infer_model_family("HiDream-I1-full.safetensors") == "hidream"
    assert infer_model_family("dreamshaper_8.safetensors") == "sd15"

    from dreamforge_cli_direct import build_plan
    from argparse import Namespace

    args = Namespace(
        model="hidream_o1_image_dev_mxfp8.safetensors",
        prompt="neon city",
        negative_prompt="",
        aspect_ratio="1024x1024",
        width=None,
        height=None,
        vram_profile="16gb",
        styles=None,
        steps=None,
        cfg_scale=None,
        sampler=None,
        scheduler=None,
        use_case="none",
        brand_kit=None,
        input_image=None,
        upscale_image=None,
        no_manifest=True,
    )
    plan = build_plan(args)
    if plan.get("model"):
        assert plan["model"]["family"] == "hidream_o1"
        assert plan["settings"]["steps"] >= 28
        assert plan["settings"]["cfg"] == 1.0
        assert plan["settings"]["performance_selection"] == "HiDream"
        assert plan["settings"]["styles"] == []


def test_different_system_fonts_render_advanced_images():
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    background = make_background(OUTPUTS / "advanced_background.png")
    fonts = [font for font in list_system_fonts() if font["likely_arabic"]][:3]
    assert fonts, "no Arabic-capable fonts available for render test"

    for index, font in enumerate(fonts):
        renderer = ArabicTextRenderer(font_path=font["alias"])
        output = OUTPUTS / f"font_{index}_{font['alias']}.png"
        renderer.composite_text_on_image(
            text="مستقبل الذكاء الاصطناعي\nتصميم احترافي",
            background_path=str(background),
            output_path=str(output),
            padding=60,
            text_color=(255, 245, 210),
            effect="all",
            position="center",
            opacity=0.95,
            line_spacing=1.25,
            text_area_darken=0.25,
            max_lines=2,
        )
        assert_nonblank_image(output)

    validation = validate_image(str(output))
    assert validation["ok"], validation
    manifest = OUTPUTS / "smoke_manifest.json"
    write_manifest(str(manifest), {"images": [str(output)], "validation": [validation]})
    assert manifest.exists()


if __name__ == "__main__":
    test_inventory_has_models_and_fonts()
    test_prompt_presets_compile()
    test_modern_model_inventory_and_resolution()
    test_hidream_o1_family_and_dependencies()
    test_different_system_fonts_render_advanced_images()
    print("CLI inventory/font/preset smoke tests passed.")
