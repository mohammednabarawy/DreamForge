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
    comfy_area_composition,
    comfy_controlnet_basic,
    comfy_face_detail_basic,
    comfy_flux_dev_txt2img,
    comfy_flux_kontext_edit,
    comfy_hires_two_pass,
    comfy_ideogram4_img2img,
    comfy_ideogram4_inpaint,
    comfy_ideogram4_txt2img,
    comfy_inpaint_basic,
    comfy_outpaint_basic,
    comfy_pid_flux_upscale,
    comfy_kandinsky5_img2img,
    comfy_flux_img2img,
    comfy_qwen_image_edit,
    comfy_qwen_image_edit_plus,
    comfy_qwen_image_txt2img,
    comfy_txt2img_basic,
    comfy_z_image_img2img,
    comfy_z_image_txt2img,
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


def test_qwen_edit_split_loaders_and_text_encode():
    graph = comfy_qwen_image_edit(
        {
            "ckpt_name": "qwen_image_edit_2509_fp8_e4m3fn.safetensors",
            "relative_path": "qwen_image_edit_2509_fp8_e4m3fn.safetensors",
            "category": "diffusion_models",
            "family": "qwen_image_edit",
            "image": "input.png",
            "prompt": "make the sky sunset",
            "negative": "",
        }
    )
    assert graph["30"]["class_type"] == "UNETLoader"
    assert graph["31"]["class_type"] == "CLIPLoader"
    assert graph["31"]["inputs"]["type"] == "qwen_image"
    assert graph["32"]["class_type"] == "VAELoader"
    text_nodes = [n for n in graph.values() if n.get("class_type") == "TextEncodeQwenImageEdit"]
    assert len(text_nodes) == 2
    cfg_norm = next(n for n in graph.values() if n.get("class_type") == "CFGNorm")
    assert cfg_norm["inputs"]["strength"] == 1.0


def test_qwen_checkpoint_edit_uses_explicit_clip_and_vae_loaders():
    graph = comfy_qwen_image_edit(
        {
            "ckpt_name": "qwenImage2512Nvfp4_v10.safetensors",
            "relative_path": "qwenImage2512Nvfp4_v10.safetensors",
            "category": "checkpoints",
            "family": "qwen_image",
            "image": "input.png",
            "prompt": "make the sky sunset",
            "negative": "",
            "vae": "qwen_image_vae.safetensors",
            "clip": "qwen_2.5_vl_7b_fp8_scaled.safetensors",
        }
    )
    assert graph["30"]["class_type"] == "CheckpointLoaderSimple"
    assert graph["31"]["class_type"] == "CLIPLoader"
    assert graph["32"]["class_type"] == "VAELoader"
    vae_encode = next(n for n in graph.values() if n.get("class_type") == "VAEEncode")
    assert vae_encode["inputs"]["vae"] == ["32", 0]


def test_qwen_edit_lightning_lora_when_requested():
    graph = comfy_qwen_image_edit(
        {
            "ckpt_name": "qwen_image_edit_2509_fp8_e4m3fn.safetensors",
            "relative_path": "qwen_image_edit_2509_fp8_e4m3fn.safetensors",
            "category": "diffusion_models",
            "family": "qwen_image_edit",
            "image": "input.png",
            "prompt": "make the sky sunset",
            "negative": "",
            "use_qwen_lightning_lora": True,
            "qwen_lightning_lora": "Qwen-Image-Edit-Lightning-4steps-V1.0.safetensors",
        }
    )
    lora_nodes = [n for n in graph.values() if n.get("class_type") == "LoraLoaderModelOnly"]
    assert len(lora_nodes) == 1
    assert "Lightning" in lora_nodes[0]["inputs"]["lora_name"]


def test_qwen_edit_handles_empty_optional_sampling_values():
    graph = comfy_qwen_image_edit(
        {
            "ckpt_name": "qwen_image_edit_2509_fp8_e4m3fn.safetensors",
            "relative_path": "qwen_image_edit_2509_fp8_e4m3fn.safetensors",
            "category": "diffusion_models",
            "family": "qwen_image_edit",
            "image": "input.png",
            "prompt": "make the sky sunset",
            "negative": "",
            "qwen_image_shift": None,
            "qwen_cfg_norm_strength": None,
        }
    )
    aura = next(n for n in graph.values() if n.get("class_type") == "ModelSamplingAuraFlow")
    cfg_norm = next(n for n in graph.values() if n.get("class_type") == "CFGNorm")
    assert aura["inputs"]["shift"] == 3.1
    assert cfg_norm["inputs"]["strength"] == 1.0


def test_qwen_edit_plus_multi_reference():
    graph = comfy_qwen_image_edit_plus(
        {
            "ckpt_name": "qwen_image_edit_2509_fp8_e4m3fn.safetensors",
            "relative_path": "qwen_image_edit_2509_fp8_e4m3fn.safetensors",
            "category": "diffusion_models",
            "family": "qwen_image_edit",
            "images": ["main.png", "ref_a.png", "ref_b.png"],
            "prompt": "combine styles",
            "negative": "",
            "qwen_scale_megapixels": 0.75,
        }
    )
    plus_nodes = [n for n in graph.values() if n.get("class_type") == "TextEncodeQwenImageEditPlus"]
    assert len(plus_nodes) == 2
    assert "image1" in plus_nodes[0]["inputs"]
    assert "image2" in plus_nodes[0]["inputs"]
    assert "image3" in plus_nodes[0]["inputs"]
    load_nodes = [n for n in graph.values() if n.get("class_type") == "LoadImage"]
    assert len(load_nodes) == 3
    scale_nodes = [n for n in graph.values() if n.get("class_type") == "ImageScaleToTotalPixels"]
    assert len(scale_nodes) == 1


def test_qwen_txt2img_uses_empty_sd3_latent():
    graph = comfy_qwen_image_txt2img(
        {
            "ckpt_name": "qwen_image_fp8_e4m3fn.safetensors",
            "relative_path": "qwen_image_fp8_e4m3fn.safetensors",
            "category": "diffusion_models",
            "family": "qwen_image",
            "prompt": "a cat",
            "negative": "",
            "width": 768,
            "height": 768,
        }
    )
    assert graph["4"]["class_type"] == "EmptySD3LatentImage"
    assert graph["31"]["class_type"] == "CLIPLoader"
    cfg_norm = next(n for n in graph.values() if n.get("class_type") == "CFGNorm")
    assert cfg_norm["inputs"]["strength"] == 1.0


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


def test_vae_decode_tiled_includes_comfy024_required_inputs():
    from dreamforge_comfy_workflows import _vae_decode_node

    node = _vae_decode_node(
        {"width": 768, "height": 768, "enable_vae_tiling": True},
        ["12", 0],
        ["13", 0],
    )
    assert node["class_type"] == "VAEDecodeTiled"
    inputs = node["inputs"]
    assert inputs["tile_size"] == 512
    assert inputs["overlap"] == 64
    assert inputs["temporal_size"] == 64
    assert inputs["temporal_overlap"] == 8


def test_ideogram4_txt2img_uses_dual_unet_and_scheduler():
    graph = comfy_ideogram4_txt2img(
        {
            "relative_path": "ideogram4_fp8_scaled.safetensors",
            "category": "diffusion_models",
            "family": "ideogram4",
            "prompt": '{"high_level_description":"a cat"}',
            "width": 1024,
            "height": 1024,
            "steps": 20,
            "cfg_override": 3.0,
            "cfg_override_start": 0.9,
            "cfg_override_end": 1.0,
        }
    )
    assert graph["1"]["class_type"] == "UNETLoader"
    assert graph["3"]["class_type"] == "UNETLoader"
    assert graph["4"]["inputs"]["type"] == "ideogram4"
    assert graph["7"]["class_type"] == "DualModelGuider"
    assert graph["2"]["inputs"]["cfg"] == 3.0
    assert abs(graph["2"]["inputs"]["start_percent"] - 0.9) < 0.001
    assert graph["9"]["class_type"] == "Ideogram4Scheduler"
    assert graph["12"]["class_type"] == "SamplerCustomAdvanced"


def test_ideogram4_img2img_stub_uses_encode_and_add_noise():
    graph = comfy_ideogram4_img2img(
        {
            "relative_path": "ideogram4_fp8_scaled.safetensors",
            "family": "ideogram4",
            "prompt": '{"high_level_description":"edit"}',
            "image": "source.png",
            "width": 1024,
            "height": 1024,
            "steps": 20,
            "denoise": 0.5,
        }
    )
    assert graph["7"]["class_type"] == "DualModelGuider"
    assert graph["10"]["class_type"] == "VAEEncode"
    assert any(node.get("class_type") == "SplitSigmasDenoise" for node in graph.values())
    add_noise = next(node for node in graph.values() if node.get("class_type") == "AddNoise")
    assert add_noise["inputs"]["latent_image"] == ["10", 0]


def test_ideogram4_inpaint_stub_uses_vae_encode_for_inpaint():
    graph = comfy_ideogram4_inpaint(
        {
            "relative_path": "ideogram4_fp8_scaled.safetensors",
            "family": "ideogram4",
            "prompt": '{"high_level_description":"fill"}',
            "image": "source.png",
            "mask": "mask.png",
            "width": 1024,
            "height": 1024,
            "steps": 20,
            "grow_mask_by": 8,
        }
    )
    assert graph["12"]["class_type"] == "VAEEncodeForInpaint"
    assert graph["12"]["inputs"]["grow_mask_by"] == 8
    assert any(node.get("class_type") == "SamplerCustomAdvanced" for node in graph.values())


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


def test_controlnet_workflow_uses_apply_advanced():
    graph = comfy_controlnet_basic(
        {
            "ckpt_name": "sdxl.safetensors",
            "control_image": "depth.png",
            "controlnet_model": "control_depth.safetensors",
            "prompt": "portrait",
            "negative": "",
        }
    )
    assert any(node.get("class_type") == "ControlNetApplyAdvanced" for node in graph.values())
    assert any(node.get("class_type") == "ControlNetLoader" for node in graph.values())


def test_outpaint_workflow_pads_canvas_before_inpaint():
    graph = comfy_outpaint_basic(
        {
            "ckpt_name": "sdxl.safetensors",
            "image": "main.png",
            "prompt": "extend scene",
            "negative": "",
            "outpaint_direction": "right",
            "outpaint_amount": 160,
        }
    )
    pad = next(node for node in graph.values() if node.get("class_type") == "ImagePadForOutpaint")
    assert pad["inputs"]["right"] == 160
    assert any(node.get("class_type") == "VAEEncodeForInpaint" for node in graph.values())


def test_hires_workflow_uses_latent_upscale_second_pass():
    graph = comfy_hires_two_pass(
        {
            "ckpt_name": "sdxl.safetensors",
            "prompt": "city",
            "negative": "",
            "width": 1024,
            "height": 1024,
            "hires_denoise": 0.25,
        }
    )
    samplers = [node for node in graph.values() if node.get("class_type") == "KSampler"]
    assert len(samplers) == 2
    assert samplers[1]["inputs"]["denoise"] == 0.25
    assert any(node.get("class_type") == "LatentUpscale" for node in graph.values())


def test_face_detail_workflow_uses_impact_nodes():
    graph = comfy_face_detail_basic(
        {
            "ckpt_name": "epicrealismXL_vxiAbeast.safetensors",
            "image": "portrait.png",
            "prompt": "sharp detailed face",
            "negative": "blurry",
            "sam_model": "sam_vit_b_01ec64.pth",
        }
    )
    assert graph["1"]["class_type"] == "LoadImage"
    assert any(node.get("class_type") == "UltralyticsDetectorProvider" for node in graph.values())
    assert any(node.get("class_type") == "FaceDetailer" for node in graph.values())
    assert any(node.get("class_type") == "SAMLoader" for node in graph.values())
    detailer = next(node for node in graph.values() if node.get("class_type") == "FaceDetailer")
    assert detailer["inputs"]["bbox_detector"]
    assert detailer["inputs"]["sam_model_opt"]


def test_pid_flux_upscale_uses_pixeldit_route():
    graph = comfy_pid_flux_upscale(
        {
            "image": "input.png",
            "prompt": "a detailed studio portrait",
            "negative": "low quality, worst quality, blurry",
            "width": 4096,
            "height": 4096,
            "pid_model": "pid_flux1_1024_to_4096_4step_mxfp8.safetensors",
            "clip": "gemma_2_2b_it_elm_fp8_scaled.safetensors",
            "source_vae": "flux-vae-bf16.safetensors",
            "seed": 123,
        }
    )

    assert graph["4"]["class_type"] == "UNETLoader"
    assert graph["4"]["inputs"]["unet_name"] == "pid_flux1_1024_to_4096_4step_mxfp8.safetensors"
    assert graph["5"]["class_type"] == "CLIPLoader"
    assert graph["5"]["inputs"]["type"] == "pixeldit"
    assert graph["5"]["inputs"]["clip_name"] == "gemma_2_2b_it_elm_fp8_scaled.safetensors"
    assert graph["7"]["class_type"] == "PiDConditioning"
    assert graph["8"]["class_type"] == "CLIPTextEncode"
    assert graph["8"]["inputs"]["text"] == "low quality, worst quality, blurry"
    assert graph["9"]["class_type"] == "EmptyChromaRadianceLatentImage"
    assert graph["9"]["inputs"]["width"] == 4096
    
    assert graph["10"]["class_type"] == "KSamplerSelect"
    assert graph["10"]["inputs"]["sampler_name"] == "lcm"
    
    assert graph["11"]["class_type"] == "BasicScheduler"
    assert graph["11"]["inputs"]["steps"] == 4
    assert graph["11"]["inputs"]["scheduler"] == "simple"
    
    assert graph["12"]["class_type"] == "SamplerCustom"
    
    assert graph["13"]["class_type"] == "VAELoader"
    assert graph["13"]["inputs"]["vae_name"] == "pixel_space"
    
    assert graph["14"]["class_type"] == "VAEDecode"


def test_area_composition_workflow_combines_regions():
    graph = comfy_area_composition(
        {
            "ckpt_name": "sdxl.safetensors",
            "negative": "",
            "region_prompts": [
                {"prompt": "studio background", "x": 0, "y": 0, "width": 1024, "height": 1024},
                {"prompt": "product hero", "x": 256, "y": 128, "width": 512, "height": 512},
            ],
        }
    )
    assert any(node.get("class_type") == "ConditioningSetArea" for node in graph.values())
    assert any(node.get("class_type") == "ConditioningCombine" for node in graph.values())


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


def test_z_image_txt2img_uses_lumina2_clip_and_auraflow():
    graph = comfy_z_image_txt2img(
        {
            "ckpt_name": "z_image_turbo_nvfp4.safetensors",
            "relative_path": "z_image_turbo_nvfp4.safetensors",
            "category": "diffusion_models",
            "family": "z_image",
            "prompt": "a portrait",
            "negative": "",
            "width": 1024,
            "height": 1024,
        }
    )
    clip = next(n for n in graph.values() if n.get("class_type") == "CLIPLoader")
    assert clip["inputs"]["type"] == "lumina2"
    assert any(n.get("class_type") == "ModelSamplingAuraFlow" for n in graph.values())
    assert graph["4"]["class_type"] == "EmptySD3LatentImage"


def test_kandinsky5_img2img_uses_kandinsky_clip_encode():
    graph = comfy_kandinsky5_img2img(
        {
            "ckpt_name": "kandinsky5lite_t2i.safetensors",
            "relative_path": "kandinsky5lite_t2i.safetensors",
            "category": "diffusion_models",
            "family": "kandinsky5",
            "image": "ref.png",
            "prompt": "a portrait",
            "negative": "",
            "denoise": 0.7,
        }
    )
    encoders = [n for n in graph.values() if n.get("class_type") == "CLIPTextEncodeKandinsky5"]
    assert len(encoders) == 2
    assert any(n.get("class_type") == "VAEEncode" for n in graph.values())
    sampler = next(n for n in graph.values() if n.get("class_type") == "KSampler")
    assert sampler["inputs"]["denoise"] == 0.7


def test_flux_img2img_uses_flux_guidance_and_cfg_one():
    graph = comfy_flux_img2img(
        {
            "ckpt_name": "flux1-dev.safetensors",
            "relative_path": "flux1-dev.safetensors",
            "category": "diffusion_models",
            "family": "flux",
            "image": "ref.png",
            "prompt": "a knight in a forest",
            "negative": "",
            "guidance": 3.5,
            "denoise": 0.75,
        }
    )
    assert any(n.get("class_type") == "VAEEncode" for n in graph.values())
    guidance = next(n for n in graph.values() if n.get("class_type") == "FluxGuidance")
    assert guidance["inputs"]["guidance"] == 3.5
    sampler = next(n for n in graph.values() if n.get("class_type") == "KSampler")
    assert sampler["inputs"]["cfg"] == 1.0
    assert sampler["inputs"]["denoise"] == 0.75
    # KSampler positive must come from FluxGuidance, not raw CLIPTextEncode.
    assert sampler["inputs"]["positive"] == [guidance_id(graph), 0]


def guidance_id(graph: dict) -> str:
    for key, node in graph.items():
        if node.get("class_type") == "FluxGuidance":
            return key
    raise AssertionError("FluxGuidance node not found")


def test_sd3_txt2img_uses_sd3_latent():
    graph = comfy_txt2img_basic(
        {
            "ckpt_name": "sd3.5_large.safetensors",
            "relative_path": "sd3.5_large.safetensors",
            "category": "checkpoints",
            "family": "sd3",
            "prompt": "a castle",
            "negative": "",
            "width": 1024,
            "height": 1024,
        }
    )
    assert any(n.get("class_type") == "EmptySD3LatentImage" for n in graph.values())
    assert not any(n.get("class_type") == "EmptyLatentImage" for n in graph.values())


def test_hidream_txt2img_uses_sd3_latent():
    graph = comfy_txt2img_basic(
        {
            "ckpt_name": "hidream_i1_dev.safetensors",
            "relative_path": "hidream_i1_dev.safetensors",
            "category": "diffusion_models",
            "family": "hidream",
            "prompt": "a castle",
            "negative": "",
            "width": 1024,
            "height": 1024,
        }
    )
    assert any(n.get("class_type") == "EmptySD3LatentImage" for n in graph.values())


def test_sdxl_txt2img_keeps_plain_latent():
    graph = comfy_txt2img_basic(
        {
            "ckpt_name": "sdxl.safetensors",
            "relative_path": "sdxl.safetensors",
            "category": "checkpoints",
            "family": "sdxl",
            "prompt": "a castle",
            "negative": "",
            "width": 1024,
            "height": 1024,
        }
    )
    assert any(n.get("class_type") == "EmptyLatentImage" for n in graph.values())
    assert not any(n.get("class_type") == "EmptySD3LatentImage" for n in graph.values())


def test_z_image_img2img_uses_vae_encode_and_auraflow():
    graph = comfy_z_image_img2img(
        {
            "ckpt_name": "z_image_turbo_nvfp4.safetensors",
            "relative_path": "z_image_turbo_nvfp4.safetensors",
            "category": "diffusion_models",
            "family": "z_image",
            "image": "ref.png",
            "prompt": "a portrait in a garden",
            "negative": "",
            "denoise": 0.35,
        }
    )
    clip = next(n for n in graph.values() if n.get("class_type") == "CLIPLoader")
    assert clip["inputs"]["type"] == "lumina2"
    vae_encode = next(n for n in graph.values() if n.get("class_type") == "VAEEncode")
    assert vae_encode["inputs"]["pixels"] == ["2", 0]
    sampler = next(n for n in graph.values() if n.get("class_type") == "KSampler")
    assert sampler["inputs"]["denoise"] == 0.35
    assert sampler["inputs"]["latent_image"] == ["3", 0]
    assert any(n.get("class_type") == "ModelSamplingAuraFlow" for n in graph.values())


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
    assert (models / "sams").is_dir()
    assert (models / "ultralytics" / "bbox").is_dir()
