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
    assert custom_tool_preflight(ui_tool, {}) == ["workflow_not_api_format"]


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
    with pytest.raises(CustomToolError, match="API Format"):
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


def test_custom_tool_dependency_entries_unknown_nodes_use_manager_hint(tmp_path):
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
