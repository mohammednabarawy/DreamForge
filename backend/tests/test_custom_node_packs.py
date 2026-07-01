"""Tests for custom node pack resolution."""

from __future__ import annotations

import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from dreamforge_workflow_planner import (
    missing_custom_node_pack_entries,
    required_custom_node_pack_ids,
    resolve_pack_id_for_nodes,
)


def test_resolve_pack_id_for_ultimate_sd_upscale_node():
    assert resolve_pack_id_for_nodes(["UltimateSDUpscale"]) == "ComfyUI_UltimateSDUpscale"


def test_resolve_pack_id_for_cutout_background_removal_nodes():
    assert (
        resolve_pack_id_for_nodes(["RemBGSession+", "ImageRemoveBackground+"])
        == "ComfyUI_essentials"
    )


def test_required_custom_node_pack_ids_for_upscale_mode():
    assert required_custom_node_pack_ids(studio_mode="upscale") == [
        "ComfyUI_UltimateSDUpscale"
    ]


def test_required_custom_node_pack_ids_for_photo_restore():
    assert required_custom_node_pack_ids(
        studio_mode="edit",
        edit_task="photo_restore",
    ) == [
        "comfyui_controlnet_aux",
        "ComfyUI-Impact-Pack",
        "ComfyUI-Impact-Subpack",
    ]


def test_required_custom_node_pack_ids_for_cutout_compose():
    assert required_custom_node_pack_ids(
        studio_mode="edit",
        edit_task="cutout_compose",
    ) == [
        "ComfyUI_essentials",
    ]


def test_missing_custom_node_pack_entries_when_directory_missing(monkeypatch):
    monkeypatch.setattr(
        "dreamforge_workflow_planner._custom_node_directory_present",
        lambda _pack: False,
    )
    missing = missing_custom_node_pack_entries(["ComfyUI_UltimateSDUpscale"])
    assert len(missing) == 1
    assert missing[0]["pack_id"] == "ComfyUI_UltimateSDUpscale"
    assert missing[0]["kind"] == "custom_node_pack"
