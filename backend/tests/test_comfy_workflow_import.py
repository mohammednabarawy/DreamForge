"""Tests for Comfy API workflow import and UI sibling repair."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dreamforge_comfy_workflow_import import (
    guess_ui_workflow_sibling,
    inspect_comfy_workflow_file,
    load_api_workflow_template,
    repair_api_workflow_class_types,
    ui_active_node_count,
    ui_node_type_map,
)


def test_guess_api_workflow_sibling_from_ui_filename(tmp_path: Path):
    ui = tmp_path / "Carousel Maker v2 - LoRAtech.json"
    api = tmp_path / "Carousel Maker v2 -API- LoRAtech.json"
    ui.write_text("{}", encoding="utf-8")
    api.write_text("{}", encoding="utf-8")
    from dreamforge_comfy_workflow_import import guess_api_workflow_sibling

    assert guess_api_workflow_sibling(ui) == api


def test_guess_ui_workflow_sibling_from_api_filename(tmp_path: Path):
    api = tmp_path / "Carousel Maker v2 -API- LoRAtech.json"
    ui = tmp_path / "Carousel Maker v2 - LoRAtech.json"
    api.write_text("{}", encoding="utf-8")
    ui.write_text("{}", encoding="utf-8")
    assert guess_ui_workflow_sibling(api) == ui


def test_repair_missing_class_types_from_ui_export(tmp_path: Path):
    api_path = tmp_path / "tool-api.json"
    ui_path = tmp_path / "tool-ui.json"
    api_path.write_text(
        json.dumps(
            {
                "187": {
                    "inputs": {"model": ["190", 0], "positive": ["108", 0]},
                },
                "108": {
                    "class_type": "CLIPTextEncode",
                    "inputs": {"text": "hello", "clip": ["107", 0]},
                },
            }
        ),
        encoding="utf-8",
    )
    ui_path.write_text(
        json.dumps(
            {
                "nodes": [
                    {"id": 187, "type": "KSampler (Efficient)"},
                    {"id": 108, "type": "CLIPTextEncode"},
                ]
            }
        ),
        encoding="utf-8",
    )
    graph = load_api_workflow_template(api_path, ui_path=ui_path)
    assert graph["187"]["class_type"] == "KSampler (Efficient)"


def test_inspect_flags_ui_workflow(tmp_path: Path):
    ui_path = tmp_path / "ui.json"
    ui_path.write_text(json.dumps({"nodes": [{"id": 1, "type": "LoadImage"}]}), encoding="utf-8")
    payload = inspect_comfy_workflow_file(ui_path)
    assert payload["ui_format"] is True
    assert payload["api_format"] is True
    assert payload["converts_at_runtime"] is True
    assert payload["nodes"]


def test_patch_node_field_preserves_workflow_links():
    from dreamforge_comfy_workflow_import import patch_node_field

    graph = {
        "108": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": ["186", 0], "clip": ["107", 0]},
        }
    }
    assert patch_node_field(graph, "108", "text", "override prompt") is False
    assert graph["108"]["inputs"]["text"] == ["186", 0]
    assert patch_node_field(graph, "108", "text", "override prompt", preserve_links=False) is True
    assert graph["108"]["inputs"]["text"] == "override prompt"


def test_apply_custom_tool_bindings_skip_linked_prompt_nodes():
    from dreamforge_custom_tools import apply_custom_tool_bindings

    graph = {
        "108": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": ["186", 0], "clip": ["107", 0]},
        },
        "191": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "bad prompt", "clip": ["107", 0]},
        },
    }
    tool = {
        "bindings": {
            "a_positive": {"type": "text", "node_id": "108", "field": "text"},
            "b_negative": {"type": "text", "node_id": "191", "field": "text"},
        }
    }
    patched = apply_custom_tool_bindings(
        graph,
        tool,
        prompt="hello",
        negative="bad",
        seed=1,
        settings={},
        uploaded_images={},
    )
    assert patched["108"]["inputs"]["text"] == ["186", 0]
    assert patched["191"]["inputs"]["text"] == "bad"


def test_ui_active_node_count_ignores_bypass_and_notes():
    ui = {
        "nodes": [
            {"id": 1, "type": "KSampler", "mode": 0},
            {"id": 2, "type": "FaceDetailer", "mode": 4},
            {"id": 3, "type": "MarkdownNote", "mode": 0},
        ]
    }
    assert ui_active_node_count(ui) == 1


@pytest.mark.skipif(
    not Path(r"C:\Users\moham\Desktop\Carousel Maker v2 - LoRAtech.json").is_file(),
    reason="user carousel UI workflow not present",
)
def test_carousel_ui_workflow_converts_to_api_graph():
    ui = Path(r"C:\Users\moham\Desktop\Carousel Maker v2 - LoRAtech.json")
    graph = load_api_workflow_template(ui)
    assert graph["108"]["inputs"]["text"] == ["186", 0]
    assert graph["187"]["inputs"]["steps"] == 6
    assert graph["197"]["class_type"] == "SaveImage"


@pytest.mark.skipif(
    not Path(r"C:\Users\moham\Desktop\Carousel Maker v2 -API- LoRAtech.json").is_file(),
    reason="user carousel API workflow not present",
)
def test_carousel_api_workflow_repairs_from_desktop_ui_sibling():
    api = Path(r"C:\Users\moham\Desktop\Carousel Maker v2 -API- LoRAtech.json")
    payload = inspect_comfy_workflow_file(api)
    assert payload["api_format"] is True
    graph = load_api_workflow_template(api)
    assert graph["187"]["class_type"] == "KSampler (Efficient)"
    assert graph["190"]["class_type"] == "Lora Loader Stack (rgthree)"
