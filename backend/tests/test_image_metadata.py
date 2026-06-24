"""Tests for PNG metadata import."""

import json

from dreamforge_image_metadata import (
    import_image_metadata,
    settings_patch_from_metadata,
    _parse_parameters_blob,
)


def test_parse_dreamforge_json_parameters():
    blob = json.dumps(
        {
            "Prompt": "a cat in space",
            "Negative": "blurry",
            "steps": 20,
            "cfg": 7.0,
            "seed": 42,
            "sampler_name": "euler",
            "scheduler": "normal",
            "width": 1024,
            "height": 768,
            "base_model_name": "flux1-dev.safetensors",
        }
    )
    parsed = _parse_parameters_blob(blob)
    assert parsed is not None
    assert parsed["Prompt"] == "a cat in space"
    patch = settings_patch_from_metadata(parsed)
    assert patch["prompt"] == "a cat in space"
    assert patch["negative_prompt"] == "blurry"
    assert patch["steps"] == 20
    assert patch["cfg_scale"] == 7.0
    assert patch["model"] == "flux1-dev.safetensors"
    assert patch["aspect_ratio"] == "1024x768"


def test_parse_a1111_parameters_string():
    blob = (
        "masterpiece portrait\n"
        "Negative prompt: ugly, blurry\n"
        "Steps: 30, Sampler: DPM++ 2M Karras, CFG scale: 7.5, Seed: 12345, Size: 512x768"
    )
    parsed = _parse_parameters_blob(blob)
    assert parsed is not None
    assert "portrait" in parsed["Prompt"]
    assert parsed["Negative"] == "ugly, blurry"
    assert parsed["width"] == 512
    assert parsed["height"] == 768


def test_import_missing_metadata(tmp_path):
    from PIL import Image

    path = tmp_path / "plain.png"
    Image.new("RGB", (8, 8), color=(0, 0, 0)).save(path)
    result = import_image_metadata(str(path))
    assert result["ok"] is False
    assert result["error"] == "no_generation_metadata"
