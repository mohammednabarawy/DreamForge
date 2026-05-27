"""Tests for Comfy workflow builders and API template import."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from dreamforge_comfy_workflow_import import (
    build_prompt_from_template,
    load_api_workflow_template,
    patch_api_workflow,
)
from dreamforge_comfy_workflows import (
    comfy_flux_dev_txt2img,
    comfy_flux_kontext_edit,
    comfy_inpaint_basic,
)
from dreamforge_krita_resources import (
    composite_inpaint_result,
    stitch_kontext_reference_images,
)


def test_kontext_workflow_uses_separate_reference_stitch():
    graph = comfy_flux_kontext_edit(
        {
            "ckpt_name": "flux1-kontext-dev.safetensors",
            "image": "main.png",
            "reference_stitch": "refs.png",
            "prompt": "edit",
            "negative": "",
        }
    )
    assert graph["2"]["inputs"]["image"] == "main.png"
    assert graph["13"]["inputs"]["image"] == "refs.png"
    assert graph["8"]["inputs"]["latent"] == ["15", 0]


def test_flux_diffusion_model_uses_unet_clip_vae_loaders():
    graph = comfy_flux_dev_txt2img(
        {
            "ckpt_name": "flux1-dev-kontext_fp8_scaled.safetensors",
            "relative_path": "flux1-dev-kontext_fp8_scaled.safetensors",
            "category": "diffusion_models",
            "family": "flux_kontext",
            "prompt": "edit",
            "negative": "",
        }
    )
    assert graph["30"]["class_type"] == "UNETLoader"
    assert graph["31"]["class_type"] == "DualCLIPLoader"
    assert graph["32"]["class_type"] == "VAELoader"
    assert graph["6"]["inputs"]["model"] == ["30", 0]


def test_inpaint_workflow_passes_grow_mask_by():
    graph = comfy_inpaint_basic(
        {
            "ckpt_name": "flux1-fill-dev.safetensors",
            "image": "main.png",
            "mask": "mask.png",
            "prompt": "fill",
            "negative": "",
            "grow_mask_by": 20,
        }
    )
    assert graph["5"]["inputs"]["grow_mask_by"] == 20


def test_api_template_loader_and_patch():
    template = {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": "old.safetensors"},
        },
        "2": {
            "class_type": "CLIPTextEncode",
            "inputs": {"clip": ["1", 1], "text": "old prompt"},
        },
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["1", 0],
                "positive": ["2", 0],
                "negative": ["2", 0],
                "latent_image": ["4", 0],
                "seed": 1,
                "steps": 10,
                "cfg": 7.0,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": 1.0,
            },
        },
    }
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "template.json"
        path.write_text(json.dumps(template), encoding="utf-8")
        loaded = load_api_workflow_template(path)
        patched = patch_api_workflow(
            loaded,
            {
                "ckpt_name": "new.safetensors",
                "prompt": "hello",
                "seed": 42,
                "steps": 25,
            },
        )
        assert patched["1"]["inputs"]["ckpt_name"] == "new.safetensors"
        assert patched["2"]["inputs"]["text"] == "hello"
        assert patched["3"]["inputs"]["seed"] == 42
        assert patched["3"]["inputs"]["steps"] == 25
        built = build_prompt_from_template(path, {"prompt": "from builder"})
        assert built["2"]["inputs"]["text"] == "from builder"


def test_stitch_kontext_reference_images_horizontal():
    pytest = __import__("pytest")
    Image = pytest.importorskip("PIL.Image")

    a = Image.new("RGB", (10, 20), color=(255, 0, 0))
    b = Image.new("RGB", (15, 10), color=(0, 255, 0))
    stitched = stitch_kontext_reference_images([a, b])
    assert stitched.size == (40, 20)


def test_composite_inpaint_result_preserves_outside_mask():
    pytest = __import__("pytest")
    Image = pytest.importorskip("PIL.Image")

    original = Image.new("RGB", (4, 4), color=(0, 0, 255))
    generated = Image.new("RGB", (4, 4), color=(255, 0, 0))
    mask = Image.new("L", (4, 4), color=0)
    mask.putpixel((1, 1), 255)
    merged = composite_inpaint_result(original, generated, mask)
    assert merged.getpixel((0, 0)) == (0, 0, 255)
    assert merged.getpixel((1, 1)) == (255, 0, 0)


def test_managed_comfy_extra_model_paths_points_to_shared_models(tmp_path, monkeypatch):
    import dreamforge_comfy_server as server

    models = (tmp_path / "models").resolve()
    monkeypatch.setattr(server, "MODELS_ROOT", models)
    comfy = tmp_path / "ComfyUI"
    path = server.ensure_dreamforge_extra_model_paths(comfy)
    text = path.read_text(encoding="utf-8")
    assert "dreamforge-managed:" in text
    assert models.as_posix() in text
    assert (models / "diffusion_models").is_dir()
