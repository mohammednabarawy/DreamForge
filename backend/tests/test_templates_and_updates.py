"""Tests for workflow templates, error constructors, and node updates."""

from dreamforge_workflow_templates import list_workflow_templates, get_workflow_template
from dreamforge_errors import model_corrupt, download_failed
from dreamforge_comfy_manager import check_custom_node_updates


def test_workflow_templates():
    templates = list_workflow_templates()
    assert len(templates) >= 4
    portrait = get_workflow_template("portrait_face_consistency")
    assert portrait is not None
    assert portrait["id"] == "portrait_face_consistency"
    assert "default_params" in portrait


def test_error_constructors():
    err1 = model_corrupt("sdxl_base.safetensors")
    assert err1["code"] == "model_corrupt"
    assert len(err1["suggestions"]) >= 1

    err2 = download_failed("https://civitai.com/model", "401 Unauthorized")
    assert err2["code"] == "download_failed"
    assert "CivitAI" in err2["suggestions"][1]


def test_check_custom_node_updates():
    res = check_custom_node_updates()
    assert res["ok"] is True
    assert isinstance(res["nodes"], list)
