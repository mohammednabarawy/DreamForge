"""Custom toolbox workflow import, binding, and preflight."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from dreamforge_custom_tools import (
    CustomToolError,
    apply_custom_tool_bindings,
    custom_tool_dependency_entries,
    custom_tool_preflight,
    find_custom_tool,
    missing_workflow_graph_model_entries,
)


def _api_graph() -> dict:
    return {
        "1": {
            "class_type": "LoadImage",
            "inputs": {"image": "placeholder.png"},
        },
        "2": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "old prompt", "clip": ["9", 0]},
        },
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "seed": 1,
                "steps": 8,
                "cfg": 7.0,
                "denoise": 1.0,
                "model": ["9", 0],
                "positive": ["2", 0],
                "negative": ["2", 0],
                "latent_image": ["9", 0],
            },
        },
        "4": {
            "class_type": "SaveImage",
            "inputs": {"images": ["3", 0], "filename_prefix": "old"},
        },
    }


def test_apply_custom_tool_bindings_patches_prompt_image_and_sampler(tmp_path: Path):
    graph = _api_graph()
    tool = {
        "bindings": {
            "img": {"type": "image", "node_id": "1", "field": "image"},
            "pos": {"type": "text", "node_id": "2", "field": "text"},
            "seed": {"type": "number", "node_id": "3", "field": "seed"},
            "steps": {"type": "number", "node_id": "3", "field": "steps"},
            "cfg": {"type": "number", "node_id": "3", "field": "cfg"},
            "denoise": {"type": "number", "node_id": "3", "field": "denoise"},
        }
    }
    patched = apply_custom_tool_bindings(
        graph,
        tool,
        prompt="hello world",
        negative="bad",
        seed=42,
        settings={"steps": 12, "cfg_scale": 5.5, "edit_strength": 0.35, "filename_prefix": "ToolRun"},
        uploaded_images={"img": "uploaded.png"},
    )
    assert patched["1"]["inputs"]["image"] == "uploaded.png"
    assert patched["2"]["inputs"]["text"] == "hello world"
    assert patched["3"]["inputs"]["seed"] == 42
    assert patched["3"]["inputs"]["steps"] == 12
    assert patched["3"]["inputs"]["cfg"] == 5.5
    assert patched["3"]["inputs"]["denoise"] == 0.35
    assert patched["4"]["inputs"]["filename_prefix"] == "ToolRun"


def test_find_custom_tool_reads_app_config(tmp_path: Path, monkeypatch):
    cfg_path = tmp_path / "app_config.json"
    cfg_path.write_text(
        json.dumps(
            {
                "custom_tools": [
                    {
                        "id": "custom_1",
                        "name": "Pixel Art",
                        "workflow_path": "D:/workflows/pixel.json",
                        "bindings": {},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("DREAMFORGE_APP_CONFIG_PATH", str(cfg_path))
    tool = find_custom_tool("custom_1")
    assert tool is not None
    assert tool["name"] == "Pixel Art"
    assert find_custom_tool("missing") is None


def test_custom_tool_preflight_flags_missing_nodes_and_ui_json(tmp_path: Path):
    api_path = tmp_path / "api.json"
    api_path.write_text(json.dumps(_api_graph()), encoding="utf-8")
    tool = {"workflow_path": str(api_path)}
    missing = custom_tool_preflight(tool, {"LoadImage": {}, "CLIPTextEncode": {}})
    assert "KSampler" in missing
    assert "SaveImage" in missing

    ui_path = tmp_path / "ui.json"
    ui_path.write_text(json.dumps({"nodes": [{"id": 1, "type": "LoadImage"}]}), encoding="utf-8")
    ui_tool = {"workflow_path": str(ui_path)}
    assert custom_tool_preflight(ui_tool, None) == []


def test_build_custom_tool_prompt_graph_requires_api_format(tmp_path: Path, monkeypatch):
    from dreamforge_custom_tools import build_custom_tool_prompt_graph

    ui_path = tmp_path / "ui.json"
    ui_path.write_text(json.dumps({"nodes": []}), encoding="utf-8")
    cfg_path = tmp_path / "app_config.json"
    cfg_path.write_text(
        json.dumps(
            {
                "custom_tools": [
                    {
                        "id": "custom_bad",
                        "name": "Bad Tool",
                        "workflow_path": str(ui_path),
                        "bindings": {},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("DREAMFORGE_APP_CONFIG_PATH", str(cfg_path))
    job = SimpleNamespace(custom_tool_id="custom_bad", input_image=None)
    client = SimpleNamespace(
        upload_image=lambda **_: {"name": "uploaded.png"},
    )
    with pytest.raises(CustomToolError, match="workflow could not be loaded"):
        build_custom_tool_prompt_graph(
            client=client,
            job=job,
            settings={},
            prompt="",
            negative="",
            seed=1,
            input_path=None,
            extra_reference_paths=None,
            mask_path=None,
        )


def test_resolve_comfy_workflow_mode_custom_tool():
    from dreamforge_workflow_routing import WorkflowRoute, resolve_comfy_workflow_mode

    route = WorkflowRoute(
        plan_mode="edit",
        reference_role="edit",
        is_upscale_job=False,
        is_inpaint_job=False,
        input_path="/tmp/in.png",
        cn_selection="Custom...",
        cn_type="edit",
        edit_type="qwen_edit",
        workflow_mode="edit",
        route_label="edit",
        custom_tool_id="custom_1",
    )
    mode = resolve_comfy_workflow_mode(
        route,
        model={"name": "qwen.safetensors"},
        model_family="qwen_image",
        input_filename="in.png",
    )
    assert mode == "custom_tool"


def test_custom_tool_dependency_entries_maps_known_nodes(monkeypatch, tmp_path):
    workflow = tmp_path / "tool.json"
    workflow.write_text(
        json.dumps(
            {
                "1": {
                    "class_type": "LayerMask: SegformerB2ClothesUltra",
                    "inputs": {},
                }
            }
        ),
        encoding="utf-8",
    )
    tool = {
        "id": "seg_tool",
        "name": "Seg Tool",
        "workflow_path": str(workflow),
        "bindings": {},
    }
    entries = custom_tool_dependency_entries(tool, object_info={})
    assert len(entries) == 1
    assert entries[0]["pack_id"] == "ComfyUI_LayerStyle"
    assert entries[0]["install_via"] == "manager"


def test_custom_tool_dependency_entries_never_flag_ui_workflow_as_api_format(tmp_path: Path):
    ui_path = tmp_path / "Carousel Maker v2 - LoRAtech.json"
    ui_path.write_text(
        json.dumps(
            {
                "nodes": [
                    {"id": 148, "type": "LoadImage", "mode": 0},
                    {"id": 108, "type": "CLIPTextEncode", "mode": 0},
                ]
            }
        ),
        encoding="utf-8",
    )
    tool = {"workflow_path": str(ui_path), "id": "carousel", "name": "Carousel", "bindings": {}}
    entries = custom_tool_dependency_entries(tool, object_info=None)
    assert all(str(item.get("id") or "") != "workflow_not_api_format" for item in entries)


def test_collect_task_missing_skips_gallery_model_when_custom_tool_selected():
    from dreamforge_companion_download import _collect_task_missing

    _model, missing = _collect_task_missing(
        model_name="ideogram4_fp8_scaled.safetensors",
        studio_mode="generate",
        upscale_method=None,
        performance=None,
        template_id=None,
        edit_task=None,
        custom_tool_id="custom_carousel",
    )
    assert not any(
        "ideogram4" in str(item.get("relative") or item.get("filename") or "")
        for item in missing
    )


def test_custom_tool_dependency_entries_unknown_nodes_use_manager_hint(tmp_path: Path):
    workflow = tmp_path / "tool.json"
    workflow.write_text(
        json.dumps({"1": {"class_type": "TotallyUnknownNode", "inputs": {}}}),
        encoding="utf-8",
    )
    tool = {
        "id": "unknown_tool",
        "workflow_path": str(workflow),
        "bindings": {},
    }
    entries = custom_tool_dependency_entries(tool, object_info={})
    assert len(entries) == 1
    assert entries[0]["install_via"] == "manager"
    assert "TotallyUnknownNode" in entries[0]["note"]


def _carousel_like_graph() -> dict:
    return {
        "106": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": "flux-2-klein-9b-fp8.safetensors"},
        },
        "107": {
            "class_type": "CLIPLoader",
            "inputs": {"clip_name": "qwen_3_8b_fp8mixed.safetensors", "type": "flux2"},
        },
        "110": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": "flux2-vae.safetensors"},
        },
        "187": {"class_type": "KSampler (Efficient)", "inputs": {}},
        "190": {"class_type": "Lora Loader Stack (rgthree)", "inputs": {}},
        "186": {"class_type": "CR Prompt List", "inputs": {}},
        "196": {"class_type": "IdentityFeatureTransferV3", "inputs": {}},
    }


def test_resolve_pack_ids_for_nodes_maps_carousel_packs():
    from dreamforge_workflow_planner import resolve_pack_ids_for_nodes

    pack_ids = resolve_pack_ids_for_nodes(
        [
            "KSampler (Efficient)",
            "Lora Loader Stack (rgthree)",
            "CR Prompt List",
            "IdentityFeatureTransferV3",
        ]
    )
    assert "efficiency-nodes-comfyui" in pack_ids
    assert "rgthree-comfy" in pack_ids
    assert "ComfyUI_Comfyroll_CustomNodes" in pack_ids
    assert "ComfyUI-Flux2Klein-Enhancer" in pack_ids


def test_custom_tool_dependency_entries_include_missing_graph_models(
    tmp_path,
    monkeypatch,
):
    workflow = tmp_path / "carousel.json"
    workflow.write_text(json.dumps(_carousel_like_graph()), encoding="utf-8")
    tool = {
        "id": "carousel",
        "name": "Carousel",
        "workflow_path": str(workflow),
        "bindings": {},
    }
    object_info = {
        "UNETLoader": {},
        "CLIPLoader": {},
        "VAELoader": {},
        "KSampler (Efficient)": {},
        "Lora Loader Stack (rgthree)": {},
        "CR Prompt List": {},
        "IdentityFeatureTransferV3": {},
    }
    monkeypatch.setattr(
        "dreamforge_custom_tools.workflow_graph_model_file_present",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(
        "dreamforge_companion_download.companion_item_present",
        lambda *_args, **_kwargs: False,
    )
    entries = custom_tool_dependency_entries(tool, object_info=object_info)
    ids = {str(item.get("id") or item.get("catalog_id")) for item in entries}
    assert "flux-2-klein-9b-fp8.safetensors" in ids or "graph_model:flux-2-klein-9b-fp8.safetensors" in ids
    assert "vae_flux2" in ids or "flux2-vae.safetensors" in ids
    assert "qwen_3_8b_fp8mixed.safetensors" in ids or "graph_model:qwen_3_8b_fp8mixed.safetensors" in ids
    assert all(item.get("kind") == "model_companion" for item in entries)


def test_custom_tool_dependency_entries_skip_satisfied_assets(monkeypatch):
    from dreamforge_custom_tools import custom_tool_dependency_entries

    tool = {
        "id": "carousel",
        "name": "Carousel",
        "workflow_path": r"C:\Users\moham\Desktop\Carousel Maker v2 -API- LoRAtech.json",
        "bindings": {},
    }
    if not Path(tool["workflow_path"]).is_file():
        pytest.skip("Carousel workflow not on disk")
    object_info = {
        "UNETLoader": {},
        "CLIPLoader": {},
        "VAELoader": {},
        "KSampler (Efficient)": {},
        "Lora Loader Stack (rgthree)": {},
        "CR Prompt List": {},
        "IdentityFeatureTransferV3": {},
    }
    entries = custom_tool_dependency_entries(tool, object_info=object_info)
    ids = {str(item.get("id") or item.get("pack_id")) for item in entries}
    assert "rgthree-comfy" not in ids
    assert "graph_model:flux-2-klein-9b-fp8.safetensors" not in ids
    assert "graph_model:qwen_3_8b_fp8mixed.safetensors" not in ids


def test_workflow_graph_model_file_present_accepts_qwen3vl_8b(tmp_path, monkeypatch):
    from dreamforge_custom_tools import workflow_graph_model_file_present

    models_root = tmp_path / "models"
    target = models_root / "text_encoders" / "qwen3vl_8b_fp8_scaled.safetensors"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"x" * 200)
    monkeypatch.setattr("_paths.MODELS_ROOT", models_root, raising=False)

    assert workflow_graph_model_file_present(
        "qwen_3_8b_fp8mixed.safetensors",
        folders=("text_encoders",),
        min_bytes=100,
    )


def test_apply_custom_tool_model_overrides_patches_loader(tmp_path):
    from dreamforge_custom_tools import (
        WORKFLOW_MODEL_DEFAULT,
        apply_custom_tool_model_overrides,
        workflow_model_ref_key,
    )

    graph = {
        "106": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": "flux-2-klein-9b-fp8.safetensors"},
        }
    }
    key = workflow_model_ref_key("106", "unet_name")
    tool = {
        "model_overrides": {
            key: "flux-2-klein-9b-kv-fp8.safetensors",
        }
    }
    patched = apply_custom_tool_model_overrides(graph, tool)
    assert patched["106"]["inputs"]["unet_name"] == "flux-2-klein-9b-kv-fp8.safetensors"

    tool_default = {"model_overrides": {key: WORKFLOW_MODEL_DEFAULT}}
    patched_default = apply_custom_tool_model_overrides(graph, tool_default)
    assert patched_default["106"]["inputs"]["unet_name"] == "flux-2-klein-9b-fp8.safetensors"


def test_missing_workflow_graph_model_entries_respects_override(tmp_path, monkeypatch):
    from dreamforge_custom_tools import (
        missing_workflow_graph_model_entries,
        workflow_model_ref_key,
    )

    models_root = tmp_path / "models"
    target = models_root / "diffusion_models" / "my-custom-unet.safetensors"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"x" * (2 * 1024 * 1024))
    monkeypatch.setattr("_paths.MODELS_ROOT", models_root, raising=False)

    graph = {
        "106": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": "flux-2-klein-9b-fp8.safetensors"},
        }
    }
    key = workflow_model_ref_key("106", "unet_name")
    tool = {"model_overrides": {key: "my-custom-unet.safetensors"}}
    assert missing_workflow_graph_model_entries(graph, tool=tool) == []

    assert missing_workflow_graph_model_entries(graph, tool={"model_overrides": {}}) != []


def test_list_custom_tool_workflow_models(tmp_path):
    from dreamforge_custom_tools import WORKFLOW_MODEL_DEFAULT, list_custom_tool_workflow_models

    workflow = tmp_path / "tool.json"
    workflow.write_text(
        json.dumps(
            {
                "106": {
                    "class_type": "UNETLoader",
                    "inputs": {"unet_name": "flux-2-klein-9b-fp8.safetensors"},
                },
                "107": {
                    "class_type": "CLIPLoader",
                    "inputs": {"clip_name": "qwen_3_8b_fp8mixed.safetensors"},
                },
                "110": {
                    "class_type": "VAELoader",
                    "inputs": {"vae_name": "flux2-vae.safetensors"},
                },
            }
        ),
        encoding="utf-8",
    )
    tool = {
        "workflow_path": str(workflow),
        "model_overrides": {},
    }
    slots = list_custom_tool_workflow_models(tool)
    assert len(slots) == 3
    assert slots[0]["workflow_filename"] == "flux-2-klein-9b-fp8.safetensors"
    assert slots[0]["selection"] == WORKFLOW_MODEL_DEFAULT
    clip_slot = next(item for item in slots if item["class_type"] == "CLIPLoader")
    vae_slot = next(item for item in slots if item["class_type"] == "VAELoader")
    assert clip_slot["library_options"]
    assert vae_slot["library_options"]
    assert all(
        item.get("category") in {"text_encoders", "clip"}
        for item in clip_slot["library_options"]
    )
    assert all(item.get("category") == "vae" for item in vae_slot["library_options"])


def test_workflow_graph_model_file_present_accepts_klein_kv_variant(tmp_path, monkeypatch):
    from dreamforge_custom_tools import workflow_graph_model_file_present

    models_root = tmp_path / "models"
    target = models_root / "diffusion_models" / "flux-2-klein-9b-kv-fp8.safetensors"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"x" * 200)
    monkeypatch.setattr("_paths.MODELS_ROOT", models_root, raising=False)

    assert workflow_graph_model_file_present(
        "flux-2-klein-9b-fp8.safetensors",
        folders=("diffusion_models",),
        min_bytes=100,
    )
