import os
import sys

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from dreamforge_prompt.ideogram4_workflows import (  # noqa: E402
    IDEOGRAM4_WORKFLOW_INPAINT,
    IDEOGRAM4_WORKFLOW_IMG2IMG,
    IDEOGRAM4_WORKFLOW_TXT2IMG,
    build_ideogram4_comfy_graph,
    ideogram4_workflow_planned,
    ideogram4_workflow_supported,
    ideogram4_workflow_unsupported_error,
    resolve_ideogram4_workflow_kind,
)


def test_resolve_txt2img_without_input():
    assert (
        resolve_ideogram4_workflow_kind(
            workflow_mode="generate",
            input_filename=None,
            mask_filename=None,
        )
        == IDEOGRAM4_WORKFLOW_TXT2IMG
    )


def test_resolve_inpaint_with_mask():
    assert (
        resolve_ideogram4_workflow_kind(
            workflow_mode="generate",
            input_filename="input.png",
            mask_filename="mask.png",
        )
        == IDEOGRAM4_WORKFLOW_INPAINT
    )


def test_resolve_img2img_with_input():
    assert (
        resolve_ideogram4_workflow_kind(
            workflow_mode="generate",
            input_filename="input.png",
            mask_filename=None,
        )
        == IDEOGRAM4_WORKFLOW_IMG2IMG
    )


def test_all_workflows_supported_without_runtime_check():
    assert ideogram4_workflow_supported(IDEOGRAM4_WORKFLOW_TXT2IMG)
    assert ideogram4_workflow_supported(IDEOGRAM4_WORKFLOW_INPAINT)
    assert ideogram4_workflow_planned(IDEOGRAM4_WORKFLOW_INPAINT)


def test_workflow_blocked_when_nodes_missing():
    info = {"KSampler": {}}
    assert not ideogram4_workflow_supported(IDEOGRAM4_WORKFLOW_TXT2IMG, object_info=info)


def test_unsupported_error_lists_missing_nodes():
    err = ideogram4_workflow_unsupported_error(
        IDEOGRAM4_WORKFLOW_TXT2IMG,
        missing_nodes=["DualModelGuider"],
    )
    assert err["code"] == "missing_custom_node_pack"


def test_edit_disabled_via_env(monkeypatch):
    monkeypatch.setenv("DREAMFORGE_DISABLE_IDEOGRAM4_EDIT", "1")
    assert not ideogram4_workflow_supported(IDEOGRAM4_WORKFLOW_IMG2IMG)


def test_build_img2img_graph():
    graph = build_ideogram4_comfy_graph(
        IDEOGRAM4_WORKFLOW_IMG2IMG,
        {
            "relative_path": "ideogram4_fp8_scaled.safetensors",
            "family": "ideogram4",
            "prompt": '{"high_level_description":"edit"}',
            "image": "input.png",
            "width": 1024,
            "height": 1024,
            "steps": 20,
            "denoise": 0.65,
            "seed": 2,
        },
    )
    assert graph["9"]["class_type"] == "LoadImage"
    assert graph["10"]["class_type"] == "VAEEncode"
    assert any(node.get("class_type") == "SplitSigmasDenoise" for node in graph.values())


def test_build_inpaint_graph():
    graph = build_ideogram4_comfy_graph(
        IDEOGRAM4_WORKFLOW_INPAINT,
        {
            "relative_path": "ideogram4_fp8_scaled.safetensors",
            "family": "ideogram4",
            "prompt": '{"high_level_description":"inpaint"}',
            "image": "input.png",
            "mask": "mask.png",
            "width": 1024,
            "height": 1024,
            "steps": 20,
            "grow_mask_by": 12,
            "seed": 3,
        },
    )
    assert graph["12"]["class_type"] == "VAEEncodeForInpaint"
    assert graph["12"]["inputs"]["grow_mask_by"] == 12


def test_build_txt2img_delegates():
    graph = build_ideogram4_comfy_graph(
        IDEOGRAM4_WORKFLOW_TXT2IMG,
        {
            "relative_path": "ideogram4_fp8_scaled.safetensors",
            "family": "ideogram4",
            "prompt": '{"high_level_description":"test"}',
            "width": 1024,
            "height": 1024,
            "steps": 20,
            "ideogram4_mu": 0.0,
            "ideogram4_std": 1.75,
            "dual_cfg": 7.0,
            "seed": 1,
        },
    )
    assert graph["4"]["inputs"]["type"] == "ideogram4"
