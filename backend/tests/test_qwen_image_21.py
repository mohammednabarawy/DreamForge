"""Tests for Qwen-Image-2.1 integration across DreamForge backend."""

from types import SimpleNamespace

from dreamforge_comfy_workflows import (
    comfy_qwen_image_edit,
    comfy_qwen_image_edit_plus,
    comfy_qwen_image_txt2img,
    comfy_qwen_image_background_removal,
    qwen_transparent_png_prompt,
    normalize_qwen_image_references,
)
from dreamforge_edit_routing import (
    model_supports_qwen_edit,
    score_edit_gallery_item,
)
from dreamforge_model_registry import (
    ModelCapabilities,
    model_capabilities_for_model,
)
from dreamforge_references import MAX_REFERENCE_SLOTS
from dreamforge_task_router import pick_curated_edit_model
from dreamforge_workflow_routing import resolve_comfy_workflow_mode
from dreamforge_generation import _build_comfy_prompt_graph
from modules.model_ui_defaults import auto_generation_settings


def test_qwen_21_max_reference_slots():
    assert MAX_REFERENCE_SLOTS == 10


def test_qwen_21_capabilities():
    model = {
        "engine_name": "qwen_image_2.1_int8_convrot.safetensors",
        "family": "qwen_image_2.1",
    }
    caps = model_capabilities_for_model(model, "qwen_image_2.1")
    assert ModelCapabilities.TEXT_TO_IMAGE in caps
    assert ModelCapabilities.IMAGE_TO_IMAGE in caps
    assert ModelCapabilities.QWEN_SEMANTIC_EDIT in caps
    assert ModelCapabilities.KONTEXT_EDIT in caps
    assert ModelCapabilities.INPAINT in caps


def test_qwen_21_edit_routing_support():
    model = {
        "engine_name": "qwen_image_2.1_int8_convrot.safetensors",
        "family": "qwen_image_2.1",
    }
    assert model_supports_qwen_edit(model, "qwen_image_2.1") is True

    # Check scoring priority
    score = score_edit_gallery_item(model)
    assert score >= 170  # Top tier base (120) + 2.1 bonus (50)


def test_qwen_21_comfy_edit_uses_textencode_qwen_image_21():
    graph = comfy_qwen_image_edit(
        {
            "ckpt_name": "qwen_image_2.1_int8_convrot.safetensors",
            "relative_path": "qwen_image_2.1_int8_convrot.safetensors",
            "category": "diffusion_models",
            "family": "qwen_image_2.1",
            "image": "photo.png",
            "prompt": "change background to a neon cyberpunk city",
            "negative": "blurry, low quality",
        }
    )
    # UNET, CLIP, VAE loaders
    assert graph["30"]["class_type"] == "UNETLoader"
    assert graph["31"]["class_type"] == "CLIPLoader"
    assert graph["32"]["class_type"] == "VAELoader"

    # Should use QwenImage21Cache instead of AuraFlow/CFGNorm
    cache_nodes = [n for n in graph.values() if n.get("class_type") == "QwenImage21Cache"]
    assert len(cache_nodes) == 1
    assert cache_nodes[0]["inputs"]["device"] == "auto"

    # Must use a SINGLE TextEncodeQwenImage21 node that generates pos, neg, and latent
    text_nodes = [n for n in graph.values() if n.get("class_type") == "TextEncodeQwenImage21"]
    assert len(text_nodes) == 1
    encode_node = text_nodes[0]
    assert "vae" in encode_node["inputs"]
    assert "images.image_1" in encode_node["inputs"]
    assert "image1" not in encode_node["inputs"]
    assert encode_node["inputs"]["prompt"] == "change background to a neon cyberpunk city"
    assert encode_node["inputs"]["negative_prompt"] == "blurry, low quality"

    # Verify KSampler uses outputs from TextEncodeQwenImage21 and proper flow-matching defaults
    ksampler = next(n for n in graph.values() if n.get("class_type") == "KSampler")
    encode_id = next(k for k, v in graph.items() if v == encode_node)
    assert ksampler["inputs"]["positive"] == [encode_id, 0]
    assert ksampler["inputs"]["negative"] == [encode_id, 1]
    assert ksampler["inputs"]["latent_image"] == [encode_id, 2]
    assert ksampler["inputs"]["cfg"] == 1.0  # Flow matching default
    assert ksampler["inputs"]["steps"] == 25
    assert ksampler["inputs"]["scheduler"] == "simple"
    assert ksampler["inputs"]["sampler_name"] == "euler"
    assert ksampler["inputs"]["denoise"] == 1.0


def test_qwen_21_comfy_edit_plus_10_reference_images():
    images = [f"ref_{i}.png" for i in range(1, 11)]
    graph = comfy_qwen_image_edit_plus(
        {
            "ckpt_name": "qwen_image_2.1_int8_convrot.safetensors",
            "relative_path": "qwen_image_2.1_int8_convrot.safetensors",
            "category": "diffusion_models",
            "family": "qwen_image_2.1",
            "images": images,
            "prompt": "combine all elements from <image1> through <image10>",
            "negative": "",
        }
    )
    # A single TextEncodeQwenImage21 node receiving all 10 images
    plus_nodes = [n for n in graph.values() if n.get("class_type") == "TextEncodeQwenImage21"]
    assert len(plus_nodes) == 1
    # Verify all 10 images are linked into TextEncodeQwenImage21
    for i in range(1, 11):
        assert f"images.image_{i}" in plus_nodes[0]["inputs"]
        assert f"image{i}" not in plus_nodes[0]["inputs"]

    load_nodes = [n for n in graph.values() if n.get("class_type") == "LoadImage"]
    assert len(load_nodes) == 10

    # KSampler uses the node's 3rd output as latent
    ksampler = next(n for n in graph.values() if n.get("class_type") == "KSampler")
    encode_id = next(k for k, v in graph.items() if v == plus_nodes[0])
    assert ksampler["inputs"]["latent_image"] == [encode_id, 2]
    assert ksampler["inputs"]["cfg"] == 1.0
    assert ksampler["inputs"]["steps"] == 25
    assert ksampler["inputs"]["scheduler"] == "simple"


def test_qwen_21_edit_reference_wording_and_alpha_prompt():
    assert normalize_qwen_image_references("Keep image 1 and use picture_2", 2) == "Keep <image1> and use <image2>"
    prompt = qwen_transparent_png_prompt("A small red apple on a transparent background")
    assert prompt.startswith("This is an RGBA image with transparency.")
    assert prompt.endswith("The image has alpha channel and the background is transparent.")


def test_qwen_21_comfy_txt2img():
    graph = comfy_qwen_image_txt2img(
        {
            "ckpt_name": "qwen_image_2.1_int8_convrot.safetensors",
            "relative_path": "qwen_image_2.1_int8_convrot.safetensors",
            "category": "diffusion_models",
            "family": "qwen_image_2.1",
            "prompt": "A cinematic shot of a futuristic cyberpunk city",
            "negative": "blurry",
            "width": 1024,
            "height": 1024,
        }
    )
    text_nodes = [n for n in graph.values() if n.get("class_type") == "TextEncodeQwenImage21"]
    assert len(text_nodes) == 1
    assert text_nodes[0]["inputs"]["prompt"] == "A cinematic shot of a futuristic cyberpunk city"
    assert text_nodes[0]["inputs"]["negative_prompt"] == "blurry"

    latent_nodes = [n for n in graph.values() if n.get("class_type") == "EmptyLatentImage"]
    assert len(latent_nodes) == 1
    assert latent_nodes[0]["inputs"]["width"] == 1024
    assert latent_nodes[0]["inputs"]["height"] == 1024

    ksampler = next(n for n in graph.values() if n.get("class_type") == "KSampler")
    assert ksampler["inputs"]["cfg"] == 1.0
    assert ksampler["inputs"]["steps"] == 25
    assert ksampler["inputs"]["scheduler"] == "simple"
    assert ksampler["inputs"]["sampler_name"] == "euler"


def test_qwen_21_generate_mode_passes_ordered_reference_images():
    graph = comfy_qwen_image_txt2img({
        "ckpt_name": "qwen_image_2.1_int8_convrot.safetensors",
        "family": "qwen_image_2.1",
        "prompt": "Use image 1 for the character and image 2 for the style",
        "images": ["character.png", "style.png"],
        "width": 2048,
        "height": 2048,
    })
    encoder = next(node for node in graph.values() if node["class_type"] == "TextEncodeQwenImage21")
    assert encoder["inputs"]["prompt"] == "Use <image1> for the character and <image2> for the style"
    assert encoder["inputs"]["images.image_1"] == ["33", 0]
    assert encoder["inputs"]["images.image_2"] == ["34", 0]
    for index in (1, 2):
        linked_id, output_index = encoder["inputs"][f"images.image_{index}"]
        assert graph[linked_id]["class_type"] == "LoadImage"
        assert output_index == 0
    assert "vae" in encoder["inputs"]
    assert encoder["inputs"]["resolution"] == 1024
    latent = next(node for node in graph.values() if node["class_type"] == "EmptyLatentImage")
    assert (latent["inputs"]["width"], latent["inputs"]["height"]) == (2048, 2048)


def test_qwen_21_create_uses_selected_canvas_with_two_references():
    model = {"name": "qwen_image_2.1_int8_convrot.safetensors", "family": "qwen_image_2.1"}
    route = SimpleNamespace(workflow_mode="generate", edit_task=None, custom_tool_id=None)
    assert resolve_comfy_workflow_mode(
        route, model=model, model_family="qwen_image_2.1", input_filename="first.png"
    ) == "txt2img"
    settings = auto_generation_settings(model["name"], model["family"],
                                        vram_profile="16gb", width=2048, height=2048)
    assert (settings["width"], settings["height"]) == (2048, 2048)
    job = SimpleNamespace(_resolved_reference_slots=[
        {"role": "image_prompt", "image": "first.png"},
        {"role": "image_prompt", "image": "second.png"},
    ])
    graph, _ = _build_comfy_prompt_graph(
        job=job, mode="txt2img", model=model, model_family="qwen_image_2.1",
        settings=settings, prompt="Put <image1> and <image2> together", negative="",
        seed=1, edit_strength=1, cn_upscale="", input_filename="first.png",
        mask_filename=None, reference_stitch_filename=None, grow_mask_by=0,
    )
    encoder = next(node for node in graph.values() if node["class_type"] == "TextEncodeQwenImage21")
    assert "images.image_2" in encoder["inputs"]
    latent = next(node for node in graph.values() if node["class_type"] == "EmptyLatentImage")
    assert (latent["inputs"]["width"], latent["inputs"]["height"]) == (2048, 2048)


def test_qwen_21_unified_request_chooses_native_edit_or_mask_graph():
    model = {"name": "qwen_image_2.1_int8_convrot.safetensors", "family": "qwen_image_2.1"}
    for cn_type, edit_type, expected in (("None", "qwen_edit", "qwen_edit"),
                                         ("inpaint", "inpaint", "inpaint")):
        route = SimpleNamespace(workflow_mode="edit", cn_type=cn_type,
                                edit_type=edit_type, edit_task=None, custom_tool_id=None)
        assert resolve_comfy_workflow_mode(
            route, model=model, model_family="qwen_image_2.1", input_filename="source.png"
        ) == expected


def test_qwen_21_background_removal():
    graph = comfy_qwen_image_background_removal(
        {
            "ckpt_name": "qwen_image_2.1_int8_convrot.safetensors",
            "relative_path": "qwen_image_2.1_int8_convrot.safetensors",
            "category": "diffusion_models",
            "family": "qwen_image_2.1",
            "image": "portrait.png",
        }
    )
    text_nodes = [n for n in graph.values() if n.get("class_type") == "TextEncodeQwenImage21"]
    assert len(text_nodes) == 1
    assert "Remove the background, and output a PNG image" in text_nodes[0]["inputs"]["prompt"]

    save_node = next(n for n in graph.values() if n.get("class_type") == "SaveImage")
    assert "DreamForge_Cutout" in save_node["inputs"]["filename_prefix"]


def test_qwen_21_curated_edit_model_picker():
    gallery = [
        {"family": "qwen_image_edit", "engine_name": "Qwen-Image-Edit-2511-Q4_K_M.gguf"},
        {"family": "qwen_image_2.1", "engine_name": "qwen_image_2.1_int8_convrot.safetensors"},
    ]
    model_name, edit_type = pick_curated_edit_model(gallery)
    assert "2.1" in model_name
    assert edit_type == "qwen_edit"


def test_qwen_21_cache_not_added_to_official_t2i_graph():
    graph = comfy_qwen_image_txt2img({
        "ckpt_name": "qwen_image_2.1_int8_convrot.safetensors",
        "family": "qwen_image_2.1",
        "prompt": "Transparent PNG icon",
    })
    assert not any(node["class_type"] == "QwenImage21Cache" for node in graph.values())
    encoder = next(node for node in graph.values() if node["class_type"] == "TextEncodeQwenImage21")
    assert encoder["inputs"]["prompt"].startswith("This is an RGBA image with transparency.")
