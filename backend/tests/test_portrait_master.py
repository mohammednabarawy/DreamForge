"""Tests for Portrait Master toolbox."""

from __future__ import annotations

from types import SimpleNamespace

from dreamforge_portrait_master import (
    build_portrait_master_prompt,
    merge_portrait_master_prompt,
)


def test_build_portrait_master_prompt_from_sliders():
    prompt = build_portrait_master_prompt(
        {
            "portrait_shot": "closeup",
            "portrait_age": 42,
            "portrait_expression": "confident",
            "portrait_lighting": "dramatic",
            "portrait_skin_detail": 0.9,
            "portrait_eye_detail": 0.8,
        }
    )
    assert "close-up" in prompt
    assert "42 years old" in prompt
    assert "confident expression" in prompt
    assert "dramatic cinematic lighting" in prompt


def test_merge_portrait_master_prompt_appends_slider_prompt():
    job = SimpleNamespace(
        edit_task="portrait_master",
        portrait_shot="portrait",
        portrait_age=25,
        portrait_expression="happy",
        portrait_lighting="studio",
        portrait_skin_detail=0.5,
        portrait_eye_detail=0.5,
    )
    merged = merge_portrait_master_prompt("red scarf", job)
    assert merged.startswith("red scarf,")
    assert "happy expression" in merged


def test_comfy_portrait_master_graph_uses_openpose_and_depth():
    from dreamforge_comfy_workflows import comfy_portrait_master

    graph = comfy_portrait_master(
        {
            "ckpt_name": "epicrealism.safetensors",
            "image": "portrait.png",
            "controlnet_model": "controlnet-union-sdxl.safetensors",
            "prompt": "studio portrait",
            "negative": "blurry",
            "portrait_pose_strength": 0.7,
            "portrait_depth_strength": 0.6,
        }
    )
    class_types = {node["class_type"] for node in graph.values() if isinstance(node, dict)}
    assert "OpenposePreprocessor" in class_types
    assert "DepthAnythingV2Preprocessor" in class_types
    assert class_types.count("ControlNetApplyAdvanced") if False else sum(
        1 for node in graph.values() if node.get("class_type") == "ControlNetApplyAdvanced"
    ) == 2
