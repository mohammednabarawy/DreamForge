import io
import json

from PIL import Image, PngImagePlugin

from dreamforge_workflow_compatibility import analyze_workflow_file
from dreamforge_workflow_provider import download_workflow, parse_workflow_index


def _native_graph():
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "model.safetensors"}},
        "2": {"class_type": "KSampler", "inputs": {}},
        "3": {"class_type": "SaveImage", "inputs": {}},
    }


def test_png_workflow_metadata_is_analyzed(tmp_path):
    meta = PngImagePlugin.PngInfo()
    meta.add_text("workflow", json.dumps(_native_graph()))
    image = Image.new("RGB", (2, 2), "black")
    path = tmp_path / "workflow.png"
    image.save(path, pnginfo=meta)
    assert analyze_workflow_file(path)["state"] == "NATIVE"


def test_index_normalization_and_https_download(tmp_path, monkeypatch):
    items = parse_workflow_index({"workflows": [{"slug": "fox", "name": "Fox", "url": "https://example.test/fox.json"}]})
    assert items[0]["id"] == "fox"
    assert parse_workflow_index({"workflows": [{"url": "http://unsafe.test/x"}]}) == []

    class Response(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *args): return False

    monkeypatch.setattr("dreamforge_workflow_provider.WORKFLOW_DOWNLOAD_ROOT", tmp_path / "library")
    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: Response(json.dumps(_native_graph()).encode()))
    result = download_workflow("https://example.test/fox.json", filename="Fox Workflow")
    assert result["ok"] is True
    assert (tmp_path / "library" / "Fox_Workflow.json").is_file()


def test_download_rejects_unsafe_workflow(tmp_path, monkeypatch):
    class Response(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *args): return False

    monkeypatch.setattr("dreamforge_workflow_provider.WORKFLOW_DOWNLOAD_ROOT", tmp_path / "library")
    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: Response(b'{"1":{"class_type":"ExecutePython","inputs":{}}}'))
    result = download_workflow("https://example.test/unsafe.json")
    assert result["ok"] is False
    assert not (tmp_path / "library" / "workflow.json").exists()
