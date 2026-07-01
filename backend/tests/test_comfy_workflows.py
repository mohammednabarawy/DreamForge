"""Tests for Comfy workflow builders and API template import."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from dreamforge_comfy_workflow_import import (
    build_prompt_from_template,
    load_api_workflow_template,
    patch_api_workflow,
)
from dreamforge_generation import _build_comfy_prompt_graph
from dreamforge_comfy_workflows import (
    comfy_area_composition,
    comfy_controlnet_basic,
    comfy_face_detail_basic,
    comfy_flux_dev_txt2img,
    comfy_flux_kontext_edit,
    comfy_flux_fill_inpaint,
    comfy_hires_two_pass,
    comfy_hidream_o1_reference_images,
    comfy_ideogram4_img2img,
    comfy_ideogram4_inpaint,
    comfy_ideogram4_txt2img,
    comfy_inpaint_basic,
    comfy_outpaint_basic,
    comfy_pid_flux_upscale,
    comfy_photo_restore,
    comfy_cutout_compose,
    compute_cutout_layout,
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


def test_kontext_identity_generate_starts_from_empty_latent():
    graph = comfy_flux_kontext_edit(
        {
            "ckpt_name": "flux1-kontext-dev.safetensors",
            "image": "face.png",
            "prompt": "same person as a character card",
            "negative": "",
            "width": 832,
            "height": 1216,
            "identity_generate": True,
        }
    )
    assert graph["16"]["class_type"] == "EmptySD3LatentImage"
    assert graph["16"]["inputs"]["width"] == 832
    assert graph["16"]["inputs"]["height"] == 1216
    assert graph["10"]["inputs"]["latent_image"] == ["16", 0]
    assert graph["8"]["inputs"]["latent"] == ["15", 0]


def test_photo_restore_builds_depth_lineart_controlnet_nodes():
    graph = comfy_photo_restore(
        {
            "ckpt_name": "epicrealismXL.safetensors",
            "image": "old_photo.png",
            "controlnet_model": "controlnet-union-sdxl.safetensors",
            "prompt": "restore this old photo",
            "negative": "blurry",
            "depth_strength": 0.18,
            "lineart_strength": 0.42,
            "face_preservation": True,
        }
    )
    class_types = {node["class_type"] for node in graph.values()}
    assert "DepthAnythingV2Preprocessor" in class_types
    assert "LineartStandardPreprocessor" in class_types
    assert "SetUnionControlNetType" in class_types
    assert "ControlNetApplyAdvanced" in class_types
    assert "ImageScaleToTotalPixels" in class_types
    depth_nodes = [
        n for n in graph.values() if n.get("class_type") == "ControlNetApplyAdvanced"
    ]
    assert len(depth_nodes) == 2
    strengths = sorted(n["inputs"]["strength"] for n in depth_nodes)
    assert strengths == [0.18, 0.42]
    face_nodes = [n for n in graph.values() if n.get("class_type") == "FaceDetailer"]
    assert len(face_nodes) == 1


def test_cutout_compose_builds_rmbg_composite_and_qwen_edit():
    graph = comfy_cutout_compose(
        {
            "ckpt_name": "qwen_image_edit_2511-Q4_K_M.gguf",
            "image": "subject.png",
            "reference_image": "background.png",
            "prompt": "harmonize subject into scene",
            "negative": "",
            "cutout_placement": "center",
            "cutout_layout": {"x": 10, "y": 20, "target_w": 400, "target_h": 600},
            "denoise": 0.35,
        }
    )
    class_types = {node["class_type"] for node in graph.values()}
    assert "RemBGSession+" in class_types
    assert "ImageRemoveBackground+" in class_types
    assert "ImageCompositeMasked" in class_types
    assert "TextEncodeQwenImageEdit" in class_types
    rembg_nodes = [
        n for n in graph.values() if n.get("class_type") == "ImageRemoveBackground+"
    ]
    assert rembg_nodes
    assert "rembg_session" in rembg_nodes[0]["inputs"]
    session_nodes = [n for n in graph.values() if n.get("class_type") == "RemBGSession+"]
    assert session_nodes
    assert session_nodes[0]["inputs"]["model"] == "u2net_human_seg: human segmentation"


def test_compute_cutout_layout_foreground_is_larger_than_background():
    _, _, fg_w, fg_h = compute_cutout_layout(1024, 1024, 512, 512, "foreground")
    _, _, bg_w, bg_h = compute_cutout_layout(1024, 1024, 512, 512, "background")
    assert fg_w > bg_w
    assert fg_h > bg_h


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


def test_qwen_edit_plus_preserve_resolution_uses_reference_latents():
    graph = comfy_qwen_image_edit_plus(
        {
            "ckpt_name": "qwen_image_edit_2509_fp8_e4m3fn.safetensors",
            "relative_path": "qwen_image_edit_2509_fp8_e4m3fn.safetensors",
            "category": "diffusion_models",
            "family": "qwen_image_edit",
            "images": ["main.png", "ref_a.png", "ref_b.png"],
            "prompt": "combine styles",
            "negative": "",
            "width": 1536,
            "height": 1024,
            "qwen_preserve_resolution": True,
        }
    )
    plus_nodes = [n for n in graph.values() if n.get("class_type") == "TextEncodeQwenImageEditPlus"]
    assert len(plus_nodes) == 2
    assert not any("image1" in node["inputs"] for node in plus_nodes)
    assert sum(1 for n in graph.values() if n.get("class_type") == "ReferenceLatent") == 6
    assert sum(1 for n in graph.values() if n.get("class_type") == "VAEEncode") == 3
    scale_nodes = [n for n in graph.values() if n.get("class_type") == "ImageScaleToTotalPixels"]
    assert len(scale_nodes) == 3
    assert scale_nodes[0]["inputs"]["megapixels"] == 1.572864
    sampler = next(n for n in graph.values() if n.get("class_type") == "KSampler")
    first_vae = next(n for n in graph.values() if n.get("class_type") == "VAEEncode")
    first_vae_id = next(key for key, node in graph.items() if node is first_vae)
    assert sampler["inputs"]["latent_image"] == [first_vae_id, 0]
    assert first_vae_id


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
    assert not any(node.get("class_type", "").startswith("ETN_") for node in graph.values())


def test_flux_fill_inpaint_uses_inpaint_model_conditioning():
    graph = comfy_flux_fill_inpaint(
        {
            "ckpt_name": "flux1-fill-dev.safetensors",
            "relative_path": "flux1-fill-dev.safetensors",
            "category": "diffusion_models",
            "family": "flux_fill",
            "image": "main.png",
            "mask": "mask.png",
            "prompt": "black shirt",
            "negative": "",
            "cfg": 30.0,
            "steps": 20,
            "grow_mask_by": 8,
            "denoise": 0.9,
        }
    )
    assert any(node.get("class_type") == "InpaintModelConditioning" for node in graph.values())
    # DifferentialDiffusion is intentionally omitted: it suppresses denoising of the
    # masked latent on Flux Fill and makes inpaint return the original image unchanged.
    assert not any(node.get("class_type") == "DifferentialDiffusion" for node in graph.values())
    assert not any(node.get("class_type") == "VAEEncodeForInpaint" for node in graph.values())
    assert not any(node.get("class_type") == "ETN_DefineRegion" for node in graph.values())
    guidance = next(node for node in graph.values() if node.get("class_type") == "FluxGuidance")
    assert guidance["inputs"]["guidance"] == 30.0
    assert not any(node.get("class_type") == "GrowMask" for node in graph.values())
    sampler = next(node for node in graph.values() if node.get("class_type") == "KSampler")
    assert sampler["inputs"]["cfg"] == 1.0
    assert sampler["inputs"]["denoise"] == 0.9
    zero_out = next(node for node in graph.values() if node.get("class_type") == "ConditioningZeroOut")
    assert zero_out is not None


def test_flux_fill_inpaint_routes_from_generation_graph_builder():
    graph, _template = _build_comfy_prompt_graph(
        job=SimpleNamespace(),
        mode="inpaint",
        model={
            "name": "FLUX.1-Fill-dev_fp8.safetensors",
            "category": "diffusion_models",
            "relative_path": "FLUX.1-Fill-dev_fp8.safetensors",
        },
        model_family="flux_fill",
        settings={
            "steps": 20,
            "cfg": 30.0,
            "sampler_name": "euler",
            "scheduler": "simple",
            "width": 768,
            "height": 768,
            "comfy_loras": [],
        },
        prompt="fill masked region",
        negative="",
        seed=42,
        edit_strength=0.9,
        cn_upscale="",
        input_filename="main.png",
        mask_filename="mask.png",
        reference_stitch_filename=None,
        grow_mask_by=8,
        model_loader_args={
            "ckpt_name": "FLUX.1-Fill-dev_fp8.safetensors",
            "relative_path": "FLUX.1-Fill-dev_fp8.safetensors",
            "category": "diffusion_models",
            "family": "flux_fill",
        },
    )
    assert any(node.get("class_type") == "InpaintModelConditioning" for node in graph.values())
    assert not any(node.get("class_type") == "VAEEncodeForInpaint" for node in graph.values())


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


def test_krea2_txt2img_uses_krea2_clip_and_auraflow():
    from dreamforge_comfy_workflows import comfy_krea2_txt2img

    graph = comfy_krea2_txt2img(
        {
            "ckpt_name": "krea2_turbo_fp8_scaled.safetensors",
            "relative_path": "krea2_turbo_fp8_scaled.safetensors",
            "category": "diffusion_models",
            "family": "krea2",
            "clip": "qwen3vl_4b_fp8_scaled.safetensors",
            "vae": "qwen_image_vae.safetensors",
            "prompt": "a portrait",
            "negative": "",
            "width": 1024,
            "height": 1024,
        }
    )
    clip = next(n for n in graph.values() if n.get("class_type") == "CLIPLoader")
    assert clip["inputs"]["type"] == "krea2"
    assert clip["inputs"]["clip_name"] == "qwen3vl_4b_fp8_scaled.safetensors"
    unet = next(n for n in graph.values() if n.get("class_type") == "UNETLoader")
    assert unet["inputs"]["unet_name"] == "krea2_turbo_fp8_scaled.safetensors"
    vae = next(n for n in graph.values() if n.get("class_type") == "VAELoader")
    assert vae["inputs"]["vae_name"] == "qwen_image_vae.safetensors"
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
    # Source pixels must flow through the aspect-preserving 64-aligned resize so
    # the encoded latent is divisible by the DiT patch stride.
    scale = next(n for n in graph.values() if n.get("class_type") == "ImageScaleToTotalPixels")
    assert scale["inputs"]["resolution_steps"] == 64
    assert vae_encode["inputs"]["pixels"] == ["20", 0]
    sampler = next(n for n in graph.values() if n.get("class_type") == "KSampler")
    assert sampler["inputs"]["denoise"] == 0.35
    assert sampler["inputs"]["latent_image"] == ["3", 0]
    assert any(n.get("class_type") == "ModelSamplingAuraFlow" for n in graph.values())


def test_img2img_builders_align_source_to_patch_stride():
    """All reference/img2img builders resize the source to a 64-aligned size so
    DiT patchify (Flux/Z-Image stride 16, HiDream-O1 stride 32) never receives an
    indivisible latent (regression: native 2586x2062 photo crashed KSampler)."""
    from dreamforge_comfy_workflows import comfy_img2img_basic

    base = {
        "ckpt_name": "model.safetensors",
        "relative_path": "model.safetensors",
        "category": "checkpoints",
        "image": "ref.png",
        "prompt": "a portrait",
        "negative": "",
        "width": 1024,
        "height": 1024,
    }
    builders = [
        (comfy_img2img_basic, {**base, "family": "hidream_o1"}),
        (comfy_flux_img2img, {**base, "family": "flux", "guidance": 3.5}),
        (comfy_kandinsky5_img2img, {**base, "family": "kandinsky5", "category": "diffusion_models"}),
    ]
    for builder, args in builders:
        graph = builder(args)
        scale = next(n for n in graph.values() if n.get("class_type") == "ImageScaleToTotalPixels")
        assert scale["inputs"]["resolution_steps"] == 64
        assert scale["inputs"]["image"] == ["2", 0]
        vae_encode = next(n for n in graph.values() if n.get("class_type") == "VAEEncode")
        assert vae_encode["inputs"]["pixels"] == ["20", 0]


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


def test_ipadapter_faceid_graph_uses_faceid_nodes():
    from dreamforge_comfy_workflows import comfy_ipadapter_faceid_reference

    graph = comfy_ipadapter_faceid_reference(
        {
            "ckpt_name": "realvisxl.safetensors",
            "relative_path": "realvisxl.safetensors",
            "family": "sdxl",
            "reference_image": "face_ref.png",
            "ipadapter_faceid_model": "ip-adapter-faceid_sdxl.bin",
            "prompt": "portrait in studio",
            "negative": "",
            "width": 1024,
            "height": 1024,
            "steps": 20,
            "cfg": 7.0,
            "seed": 42,
        }
    )
    class_types = {node["class_type"] for node in graph.values() if isinstance(node, dict)}
    assert "IPAdapterUnifiedLoaderFaceID" in class_types
    assert "IPAdapterFaceID" in class_types
    assert "KSampler" in class_types


def test_hidream_o1_dev_txt2img_uses_native_sampler_chain():
    from dreamforge_comfy_workflows import comfy_hidream_o1_dev_txt2img

    graph = comfy_hidream_o1_dev_txt2img(
        {
            "ckpt_name": "hidream_o1_image_dev_mxfp8.safetensors",
            "relative_path": "hidream_o1_image_dev_mxfp8.safetensors",
            "category": "checkpoints",
            "prompt": "a knight on a dragon",
            "negative": "",
            "width": 2048,
            "height": 2048,
            "steps": 28,
            "cfg": 1.0,
            "scheduler": "normal",
            "seed": 42,
            "hidream_noise_scale": 7.6,
            "hidream_s_noise": 1.0,
            "hidream_s_noise_end": 1.0,
            "hidream_noise_clip_std": 2.5,
            "hidream_patch_seam_smoothing": True,
        }
    )
    class_types = {node["class_type"] for node in graph.values() if isinstance(node, dict)}
    assert "CheckpointLoaderSimple" in class_types
    assert "EmptyHiDreamO1LatentImage" in class_types
    assert "ModelNoiseScale" in class_types
    assert "SamplerLCM" in class_types
    assert "SamplerCustom" in class_types
    assert "BasicScheduler" in class_types
    assert "HiDreamO1PatchSeamSmoothing" in class_types
    assert "KSampler" not in class_types
    assert "EmptySD3LatentImage" not in class_types

    noise = next(n for n in graph.values() if n.get("class_type") == "ModelNoiseScale")
    assert noise["inputs"]["noise_scale"] == 7.6
    lcm = next(n for n in graph.values() if n.get("class_type") == "SamplerLCM")
    assert lcm["inputs"]["noise_clip_std"] == 2.5
    sample = next(n for n in graph.values() if n.get("class_type") == "SamplerCustom")
    assert sample["inputs"]["cfg"] == 1.0


def test_hidream_o1_reference_images_uses_native_reference_node():
    graph = comfy_hidream_o1_reference_images(
        {
            "ckpt_name": "hidream_o1_image_dev_mxfp8.safetensors",
            "relative_path": "hidream_o1_image_dev_mxfp8.safetensors",
            "category": "checkpoints",
            "prompt": "make them stand together",
            "negative": "",
            "images": ["a.png", "b.png", "c.png"],
            "width": 2048,
            "height": 2048,
            "steps": 28,
            "cfg": 1.0,
            "scheduler": "normal",
            "seed": 42,
        }
    )
    class_types = {node["class_type"] for node in graph.values() if isinstance(node, dict)}
    assert "HiDreamO1ReferenceImages" in class_types
    assert "SamplerCustom" in class_types
    assert "KSampler" not in class_types
    assert sum(1 for node in graph.values() if node.get("class_type") == "LoadImage") == 3

    reference = next(
        node for node in graph.values() if node.get("class_type") == "HiDreamO1ReferenceImages"
    )
    assert "images.image_1" in reference["inputs"]
    assert "images.image_2" in reference["inputs"]
    assert "images.image_3" in reference["inputs"]


def test_hidream_o1_dev_txt2img_uses_prepared_prompt_directly():
    from dreamforge_comfy_workflows import comfy_hidream_o1_dev_txt2img

    graph = comfy_hidream_o1_dev_txt2img(
        {
            "ckpt_name": "hidream_o1_image_dev_mxfp8.safetensors",
            "relative_path": "hidream_o1_image_dev_mxfp8.safetensors",
            "category": "checkpoints",
            "prompt": "a knight on a dragon at night",
            "negative": "",
            "width": 2048,
            "height": 2048,
            "steps": 28,
            "cfg": 1.0,
            "scheduler": "normal",
            "seed": 42,
        }
    )
    class_types = {node["class_type"] for node in graph.values() if isinstance(node, dict)}
    assert "TextGenerate" not in class_types
    assert "JsonExtractString" not in class_types
    positive = next(
        n
        for n in graph.values()
        if n.get("class_type") == "CLIPTextEncode"
        and n["inputs"].get("text") == "a knight on a dragon at night"
    )
    assert positive
