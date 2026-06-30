import json
import os
import sys

import pytest

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from dreamforge_prompt.ideogram4 import (  # noqa: E402
    apply_ideogram_composition_guardrails,
    build_magic_prompt_instruction,
    build_magic_prompt_messages,
    ideogram4_scheduler_params,
    looks_like_ideogram_json,
    normalize_ideogram_caption,
    resolve_ideogram4_mode,
    _brain_system_prompt,
    _IDEOGRAM4_SLIM_SYSTEM,
)


def test_looks_like_ideogram_json():
    payload = json.dumps({"high_level_description": "a red cat on a bench"})
    assert looks_like_ideogram_json(payload) is True
    assert looks_like_ideogram_json("plain text prompt") is False


def test_normalize_ideogram_caption_minifies():
    raw = '{\n  "high_level_description": "test",\n  "aspect_ratio": "1:1"\n}'
    out = normalize_ideogram_caption(raw)
    assert out == '{"aspect_ratio":"1:1","high_level_description":"test"}'


def test_build_magic_prompt_instruction_replaces_placeholders():
    text = build_magic_prompt_instruction("sunset city", 1024, 768)
    assert "{{original_prompt}}" not in text
    assert "sunset city" in text
    assert "1024:768" in text


def test_build_magic_prompt_messages_splits_system_and_user():
    system, user = build_magic_prompt_messages("sunset city", 1024, 768)
    assert "OUTPUT CONTRACT" in system or "three top-level keys" in system
    assert "Minimum v1-only shape" in system or "Minimum v1 shape" in system
    assert "compositional_deconstruction` is REQUIRED" in system
    assert "Text: `type`, optional `bbox`, `text`, `desc`" in system
    assert "sunset city" in user
    assert "1024:768" in user
    assert "{{aspect_ratio}}" not in user
    assert len(user) < 500


def test_build_magic_prompt_messages_uses_aspect_ratio_placeholder():
    _, user = build_magic_prompt_messages("cat", 512, 512)
    assert "512:512" in user
    assert "{{width}}" not in user


def test_brain_system_prompt_always_uses_full_v1_template():
    full, user = build_magic_prompt_messages("cat", 1024, 1024)
    assert _brain_system_prompt("embedded", full, user) == full.strip()
    assert _brain_system_prompt("ollama", full, user) == full.strip()
    long_user = user + ("\n" + "detail line " * 200)
    assert _brain_system_prompt("embedded", full, long_user) == full.strip()


def test_is_long_magic_prompt_brief():
    from dreamforge_prompt.ideogram4 import _is_long_magic_prompt_brief

    assert not _is_long_magic_prompt_brief("short idea")
    assert _is_long_magic_prompt_brief("x" * 400)
    assert _is_long_magic_prompt_brief("\n".join(f"line {i}" for i in range(10)))


def test_loads_ideogram_json_skips_user_prompt_fallback_when_disabled():
    from dreamforge_prompt.ideogram4 import _loads_ideogram_json_object

    with pytest.raises(ValueError, match="invalid JSON"):
        _loads_ideogram_json_object("{not json", user_prompt="fallback idea", allow_user_prompt_fallback=False)


def test_resolve_ideogram4_mode_defaults():
    from dreamforge_prompt.ideogram4 import resolve_ideogram4_prompt_mode

    assert resolve_ideogram4_prompt_mode({}) == "auto"
    assert resolve_ideogram4_prompt_mode({"ideogram4_prompt_mode": "structured"}) == "structured"
    assert resolve_ideogram4_mode({"ideogram4_mode": "turbo"}) == "turbo"
    assert resolve_ideogram4_mode({"ideogram4_mode": "invalid"}) == "default"
    assert resolve_ideogram4_mode({"performance": "Speed"}) == "default"
    assert resolve_ideogram4_mode({"performance": "Quality"}) == "quality"
    assert resolve_ideogram4_mode({"performance": "Custom...", "steps": 48}) == "quality"
    assert resolve_ideogram4_mode({"performance": "Custom...", "steps": 12}) == "turbo"


def test_ideogram4_vram_caps_downgrade_quality_on_16gb():
    sched = ideogram4_scheduler_params(
        {"ideogram4_mode": "quality"},
        width=1344,
        height=1344,
        vram_tier="16gb",
    )
    assert sched["mode"] == "default"
    assert sched["width"] <= 896
    assert sched["height"] <= 896
    assert sched["steps"] == 20
    assert any("Quality" in w for w in sched.get("warnings") or [])


def test_ideogram4_vram_caps_allow_quality_on_16gb():
    sched = ideogram4_scheduler_params(
        {"performance": "Quality"},
        width=1024,
        height=1024,
        vram_tier="16gb",
    )
    assert sched["mode"] == "quality"
    assert sched["steps"] == 48


def test_validate_ideogram_caption_repairs_trailing_comma():
    from dreamforge_prompt.ideogram4 import validate_ideogram_caption

    raw = '{"high_level_description":"a cat on a bench",}'
    out = validate_ideogram_caption(raw)
    assert out["ok"] is True
    assert "cat on a bench" in (out.get("normalized") or "")


def test_validate_ideogram_caption_preserves_schema_order_for_text_elements():
    from dreamforge_prompt.ideogram4 import validate_ideogram_caption

    raw = (
        '{"high_level_description":"A woman playing handball on a beach with Arabic calligraphy overlays.",'
        '"compositional_deconstruction":{"elements":[{"type":"text",'
        '"desc":"Arabic calligraphy overlay integrated with scene lighting","text":"كرة اليد"}]}}'
    )
    out = validate_ideogram_caption(raw)
    assert out["ok"] is True
    normalized = out["normalized"] or ""
    assert '"background":"A woman playing handball on a beach with Arabic calligraphy overlays."' in normalized
    assert normalized.index('"text":"كرة اليد"') < normalized.index('"desc":"Arabic calligraphy')


def test_loads_ideogram_json_fallback_from_partial():
    from dreamforge_prompt.ideogram4 import _loads_ideogram_json_object

    broken = (
        '{"aspect_ratio":"1024:1024","high_level_description":"A red sports car '
        'with chrome wheels on wet pavement"'
    )
    obj = _loads_ideogram_json_object(broken, user_prompt="fallback idea")
    assert "high_level_description" in obj


def test_repair_bbox_pixel_coordinates():
    from dreamforge_prompt.ideogram4 import _normalize_bbox

    repaired = _normalize_bbox([120, 80, 960, 1344])
    assert repaired is not None
    assert all(0 <= v <= 1000 for v in repaired)
    assert repaired[2] > repaired[0]
    assert repaired[3] > repaired[1]


def test_repair_bbox_percent_coordinates():
    from dreamforge_prompt.ideogram4 import _normalize_bbox

    assert _normalize_bbox([10, 20, 50, 80]) == [100, 200, 500, 800]


def test_canonicalize_drops_invalid_bbox_instead_of_failing():
    from dreamforge_prompt.ideogram4 import validate_ideogram_caption

    raw = (
        '{"aspect_ratio":"16:9","high_level_description":"A romantic garden scene.",'
        '"compositional_deconstruction":{"background":"Paradise garden at sunset.",'
        '"elements":[{"type":"text","bbox":[1200,50,1300,900],'
        '"text":"حواء يا أم البشر","desc":"Arabic calligraphy overlay"}]}}'
    )
    result = validate_ideogram_caption(raw)
    assert result["ok"] is True
    parsed = json.loads(result["normalized"] or "{}")
    el = parsed["compositional_deconstruction"]["elements"][0]
    assert el["text"] == "حواء يا أم البشر"
    if "bbox" in el:
        assert all(0 <= v <= 1000 for v in el["bbox"])


def test_extract_required_image_text_from_structured_brief():
    from dreamforge_prompt.ideogram4 import extract_required_image_text

    prompt = """
[TEXT OVERLAY - ARABIC]
Main line in elegant Arabic calligraphy:
"حواء يا أم البشر… آدم هنا مشتاق"

Secondary line:
"من ضلعي الإله سواكي"

[TEXT OVERLAY - CREDITS]
"كلمات: محمد النبراوي"
"من ديوان: صيف ممطر"
"الألحان والتوزيع: بالذكاء الاصطناعي"

[NAME]
"محمد النبراوي"
"MOHAMED ELNABARAWI"

[QUALITY]
"heavenly light, eden garden"
"""
    required = extract_required_image_text(prompt)
    assert "حواء يا أم البشر… آدم هنا مشتاق" in required
    assert "من ضلعي الإله سواكي" in required
    assert "كلمات: محمد النبراوي" in required
    assert "MOHAMED ELNABARAWI" in required
    assert "heavenly light, eden garden" not in required


def test_ensure_required_text_elements_adds_missing():
    from dreamforge_prompt.ideogram4 import _ensure_required_text_elements, normalize_ideogram_caption

    obj = {
        "aspect_ratio": "16:9",
        "high_level_description": "Romantic garden scene.",
        "compositional_deconstruction": {"background": "Eden at sunset."},
    }
    merged = _ensure_required_text_elements(obj, ["حواء يا أم البشر", "كلمات: محمد النبراوي"])
    out = normalize_ideogram_caption(json.dumps(merged))
    parsed = json.loads(out)
    texts = [
        el["text"]
        for el in parsed["compositional_deconstruction"]["elements"]
        if el.get("type") == "text"
    ]
    assert "حواء يا أم البشر" in texts
    assert "كلمات: محمد النبراوي" in texts


def test_canonicalize_many_text_elements_with_bad_bboxes():
    from dreamforge_prompt.ideogram4 import normalize_ideogram_caption

    obj = {
        "aspect_ratio": "16:9",
        "high_level_description": "Cinematic romantic Adam and Eve in an Eden garden.",
        "compositional_deconstruction": {
            "background": "Lush paradise garden at sunset with waterfalls and golden light.",
            "elements": [
                {
                    "type": "obj",
                    "bbox": [2000, 100, 2500, 900],
                    "desc": "Middle Eastern couple standing close with modest elegant clothing.",
                },
                {
                    "type": "text",
                    "bbox": [-10, 800, 120, 980],
                    "text": "حواء يا أم البشر… آدم هنا مشتاق",
                    "desc": "Main Arabic calligraphy line.",
                },
                {
                    "type": "text",
                    "text": "كلمات: محمد النبراوي",
                    "desc": "Credit line.",
                },
            ],
        },
    }
    out = normalize_ideogram_caption(json.dumps(obj))
    parsed = json.loads(out)
    texts = [
        el.get("text")
        for el in parsed["compositional_deconstruction"]["elements"]
        if el.get("type") == "text"
    ]
    assert "حواء يا أم البشر… آدم هنا مشتاق" in texts
    assert "كلمات: محمد النبراوي" in texts


def test_validate_ideogram_caption_style_description():
    from dreamforge_prompt.ideogram4 import validate_ideogram_caption

    raw = (
        '{"high_level_description":"a cat","style_description":'
        '{"color_palette":["#FF0000"]}}'
    )
    out = validate_ideogram_caption(raw)
    assert out["ok"] is True
    assert "#FF0000" in (out.get("normalized") or "")


def test_validate_ideogram_caption_preserves_art_style_branch_order():
    from dreamforge_prompt.ideogram4 import validate_ideogram_caption

    raw = (
        '{"high_level_description":"a poster","style_description":'
        '{"aesthetics":"minimal","lighting":"even","medium":"graphic_design",'
        '"art_style":"flat vector poster","photo":"35mm camera look",'
        '"color_palette":["#ffffff","#112233"]}}'
    )
    out = validate_ideogram_caption(raw)
    assert out["ok"] is True
    normalized = out["normalized"] or ""
    assert '"medium":"graphic_design","art_style":"flat vector poster","color_palette":["#FFFFFF","#112233"]' in normalized
    assert '"photo"' not in normalized


def test_prepare_ideogram_inpaint_skips_magic_json():
    from types import SimpleNamespace

    from dreamforge_prompt.ideogram4 import prepare_ideogram4_generation_prompts

    job = SimpleNamespace(
        edit_type="inpaint",
        cn_type="inpaint",
        workflow_mode="inpaint",
        input_image="photo.png",
        inpaint_mask_path="mask.png",
    )
    out = prepare_ideogram4_generation_prompts(
        job,
        "add golden flowers",
        "",
        {"ideogram4_prompt_mode": "auto"},
        width=1024,
        height=1024,
    )
    assert out.get("prompt_format") == "natural"
    assert out.get("ideogram4_inpaint") is True
    assert "masked region" in out["prompt"].lower()
    assert "golden flowers" in out["prompt"]
    assert "compositional_deconstruction" not in out["prompt"]


def test_prepare_ideogram_inpaint_extracts_hld_from_json():
    from types import SimpleNamespace

    from dreamforge_prompt.ideogram4 import prepare_ideogram4_generation_prompts

    job = SimpleNamespace(
        edit_type="inpaint",
        input_image="photo.png",
        inpaint_mask_path="mask.png",
    )
    json_prompt = (
        '{"high_level_description":"a blue sky","compositional_deconstruction":{"elements":[]}}'
    )
    out = prepare_ideogram4_generation_prompts(
        job,
        json_prompt,
        "",
        {},
        width=1024,
        height=1024,
    )
    assert out["prompt_format"] == "natural"
    assert "blue sky" in out["prompt"]
    assert "compositional_deconstruction" not in out["prompt"]


def test_prepare_structured_mode_requires_json():
    from types import SimpleNamespace

    from dreamforge_prompt.ideogram4 import prepare_ideogram4_generation_prompts

    out = prepare_ideogram4_generation_prompts(
        SimpleNamespace(),
        "plain text",
        "",
        {"ideogram4_prompt_mode": "structured"},
        width=1024,
        height=1024,
    )
    assert out.get("prompt_prepare_error")


def test_prepare_ideogram_identity_generate_skips_magic_json():
    from types import SimpleNamespace

    from dreamforge_prompt.ideogram4 import prepare_ideogram4_generation_prompts

    job = SimpleNamespace(
        workflow_mode="generate",
        input_image="portrait.png",
        face_preservation=True,
        edit_type="auto",
        cn_type="img2img",
    )
    json_prompt = (
        '{"high_level_description":"romantic garden at sunset",'
        '"compositional_deconstruction":{"elements":[{"type":"text"}]}}'
    )
    out = prepare_ideogram4_generation_prompts(
        job,
        json_prompt,
        "",
        {},
        width=1024,
        height=1024,
    )
    assert out.get("prompt_format") == "natural"
    assert "same person" in out["prompt"].lower()
    assert "romantic garden" in out["prompt"].lower()
    assert "compositional_deconstruction" not in out["prompt"]


def test_identity_generate_boost_in_pipeline():
    from types import SimpleNamespace

    from dreamforge_prompt.pipeline import _identity_generate_boost

    job = SimpleNamespace(
        input_image="face.png",
        face_preservation=True,
    )
    boosted = _identity_generate_boost(job, "generate", "standing in a cyberpunk city")
    assert "same person" in boosted.lower()
    assert "cyberpunk" in boosted.lower()


def test_ideogram4_cfg_override_schedule_matches_official_presets():
    turbo = ideogram4_scheduler_params({"ideogram4_mode": "turbo"}, vram_tier="24gb")
    assert turbo["cfg_override"] == 3.0
    assert abs(turbo["cfg_override_start"] - (11 / 12)) < 0.01

    default = ideogram4_scheduler_params({"ideogram4_mode": "default"}, vram_tier="24gb")
    assert abs(default["cfg_override_start"] - 0.9) < 0.001

    quality = ideogram4_scheduler_params({"ideogram4_mode": "quality"}, vram_tier="24gb")
    assert abs(quality["cfg_override_start"] - (45 / 48)) < 0.01


def test_normalize_aspect_ratio_value():
    from dreamforge_prompt.ideogram4 import _normalize_aspect_ratio_value

    assert _normalize_aspect_ratio_value("768", width=768, height=768) == "768:768"
    assert _normalize_aspect_ratio_value("1:1", width=1024, height=768) == "1:1"
    assert _normalize_aspect_ratio_value("", width=768, height=768) == "1:1"


def test_ideogram4_vram_caps_forces_turbo_on_8gb():
    sched = ideogram4_scheduler_params(
        {"ideogram4_mode": "default"},
        width=1024,
        height=1024,
        vram_tier="8gb",
    )
    assert sched["mode"] == "turbo"
    assert sched["width"] <= 768
    assert sched["steps"] == 12


def test_ideogram4_custom_aspect_dimensions_are_honored():
    from dreamforge_prompt.ideogram4_presets import apply_ideogram4_aspect_preset

    out = apply_ideogram4_aspect_preset(
        {"aspect_ratio": "896x896"},
        vram_tier="16gb",
    )
    assert out["width"] == 896
    assert out["height"] == 896
    assert out["aspect_ratio"] == "896:896"


def test_guardrails_fixes_wrong_transparent_office_scene():
    raw = {
        "high_level_description": (
            "A founder working at a standing desk in a modern office with city views."
        ),
        "compositional_deconstruction": {
            "background": "transparent background",
            "elements": [
                {
                    "type": "obj",
                    "bbox": [200, 300, 700, 700],
                    "desc": "Founder in business casual at a standing desk",
                },
                {
                    "type": "obj",
                    "bbox": [50, 600, 400, 950],
                    "desc": "Floor-to-ceiling glass windows with Riyadh skyline",
                },
                {
                    "type": "obj",
                    "bbox": [450, 350, 650, 550],
                    "desc": "Open laptop showing charts",
                },
            ],
        },
    }
    out = apply_ideogram_composition_guardrails(raw, user_prompt="founder in modern office")
    comp = out["compositional_deconstruction"]
    assert comp["background"] != "transparent background"
    assert "skyline" in comp["background"].lower() or "window" in comp["background"].lower()
    assert len(comp["elements"]) == 2
    for el in comp["elements"]:
        assert el["type"] == "obj"
        assert "bbox" not in el


def test_guardrails_preserves_cutout_when_user_requests():
    raw = {
        "high_level_description": "Red sports car isolated for compositing.",
        "compositional_deconstruction": {
            "background": "transparent background",
            "elements": [
                {"type": "obj", "desc": "Red sports car, three-quarter view"},
            ],
        },
    }
    out = apply_ideogram_composition_guardrails(raw, user_prompt="isolated cutout sticker of a red car")
    comp = out["compositional_deconstruction"]
    assert comp["background"] == "transparent background"


def test_guardrails_preserves_poster_text_bboxes():
    raw = {
        "high_level_description": "Bold typography social media poster mockup with headline.",
        "compositional_deconstruction": {
            "background": "transparent background",
            "elements": [
                {
                    "type": "text",
                    "bbox": [100, 150, 250, 850],
                    "text": "LAUNCH",
                    "desc": "Large headline typography",
                },
                {
                    "type": "obj",
                    "bbox": [300, 350, 700, 650],
                    "desc": "Product hero render centered",
                },
            ],
        },
    }
    out = apply_ideogram_composition_guardrails(raw, user_prompt="poster mockup layout")
    comp = out["compositional_deconstruction"]
    assert comp["background"] != "transparent background"
    text_el = next(el for el in comp["elements"] if el["type"] == "text")
    assert text_el["bbox"] == [100, 150, 250, 850]
    obj_el = next(el for el in comp["elements"] if el["type"] == "obj")
    assert obj_el["bbox"] == [300, 350, 700, 650]


def test_normalize_applies_guardrails_to_pasted_json():
    raw = (
        '{"high_level_description":"Portrait in a sunlit studio.",'
        '"compositional_deconstruction":{"background":"transparent background",'
        '"elements":[{"type":"obj","bbox":[200,200,800,800],"desc":"Woman in linen dress"}]}}'
    )
    normalized = normalize_ideogram_caption(raw)
    parsed = json.loads(normalized)
    assert parsed["compositional_deconstruction"]["background"] != "transparent background"
    assert "bbox" not in parsed["compositional_deconstruction"]["elements"][0]


def test_strict_required_keys_validation():
    from dreamforge_prompt.ideogram4_layout import caption_from_layout
    import pytest
    
    with pytest.raises(ValueError, match="aspect_ratio"):
        caption_from_layout(
            aspect_ratio="",
            high_level_description="cat",
            background="sky",
            elements=[],
        )

    with pytest.raises(ValueError, match="high_level_description"):
        caption_from_layout(
            aspect_ratio="1:1",
            high_level_description="",
            background="sky",
            elements=[],
        )


def test_strict_hex_color_validation():
    from dreamforge_prompt.ideogram4_layout import caption_from_layout
    import pytest
    
    with pytest.raises(ValueError, match="Invalid hex color"):
        caption_from_layout(
            aspect_ratio="1:1",
            high_level_description="cat",
            background="sky",
            elements=[],
            style_description={"color_palette": ["#GGGGGG"]},
        )


def test_strict_bbox_bounds_validation():
    from dreamforge_prompt.ideogram4_layout import caption_from_layout
    import pytest
    
    with pytest.raises(ValueError, match="bbox must be an array of 4"):
        caption_from_layout(
            aspect_ratio="1:1",
            high_level_description="cat",
            background="sky",
            elements=[{"type": "obj", "bbox": [100, 200], "desc": "box"}],
        )

    with pytest.raises(ValueError, match="y1.*must be less than y2"):
        caption_from_layout(
            aspect_ratio="1:1",
            high_level_description="cat",
            background="sky",
            elements=[{"type": "obj", "bbox": [500, 100, 200, 800], "desc": "box"}],
        )

    with pytest.raises(ValueError, match="x1.*must be less than x2"):
        caption_from_layout(
            aspect_ratio="1:1",
            high_level_description="cat",
            background="sky",
            elements=[{"type": "obj", "bbox": [100, 600, 300, 200], "desc": "box"}],
        )


