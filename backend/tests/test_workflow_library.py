import json

import dreamforge_workflow_library as library


def _native_workflow():
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "model.safetensors"}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "a fox"}},
        "3": {"class_type": "EmptyLatentImage", "inputs": {"width": 512, "height": 512}},
        "4": {"class_type": "KSampler", "inputs": {"steps": 10, "cfg": 5, "sampler_name": "euler"}},
        "5": {"class_type": "SaveImage", "inputs": {"filename_prefix": "DreamForge"}},
    }


def test_save_workflow_file_is_atomic_and_reports_compatibility(tmp_path, monkeypatch):
    source = tmp_path / "my workflow.json"
    source.write_text(json.dumps(_native_workflow()), encoding="utf-8")
    destination = tmp_path / "library"
    monkeypatch.setattr(library, "WORKFLOW_LIBRARY_ROOT", destination)

    result = library.save_workflow_file(source)

    assert result["ok"] is True
    saved = destination / result["filename"]
    assert saved.is_file()
    assert result["report"]["state"] == "NATIVE"
    assert result["execution"] == "disabled"
    assert not list(destination.glob("*.part"))


def test_save_workflow_file_rejects_invalid_json(tmp_path, monkeypatch):
    source = tmp_path / "bad.json"
    source.write_text("not json", encoding="utf-8")
    monkeypatch.setattr(library, "WORKFLOW_LIBRARY_ROOT", tmp_path / "library")
    result = library.save_workflow_file(source)
    assert result["ok"] is False
    assert result["error"].startswith("workflow_json_invalid")
