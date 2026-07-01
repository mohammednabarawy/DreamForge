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
    ui_node_type_map,
)


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
    assert payload["api_format"] is False


@pytest.mark.skipif(
    not Path(r"C:\Users\moham\Desktop\Carousel Maker v2 -API- LoRAtech.json").is_file(),
    reason="user carousel workflow not present",
)
def test_carousel_api_workflow_repairs_from_desktop_ui_sibling():
    api = Path(r"C:\Users\moham\Desktop\Carousel Maker v2 -API- LoRAtech.json")
    payload = inspect_comfy_workflow_file(api)
    assert payload["api_format"] is True
    assert payload["repaired_nodes"]
    graph = load_api_workflow_template(api)
    assert graph["187"]["class_type"] == "KSampler (Efficient)"
    assert graph["190"]["class_type"] == "Lora Loader Stack (rgthree)"
