import io
import json

from PIL import Image, PngImagePlugin

from dreamforge_workflow_compatibility import analyze_workflow_file
from dreamforge_workflow_provider import _public_https_url, download_workflow, parse_workflow_index


def _native_graph():
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "model.safetensors"}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "fox", "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": "blur", "clip": ["1", 1]}},
        "4": {"class_type": "EmptyLatentImage", "inputs": {"width": 512, "height": 512}},
        "5": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["4", 0], "steps": 10, "cfg": 5, "sampler_name": "euler", "scheduler": "normal"}},
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage", "inputs": {"images": ["6", 0]}},
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
    monkeypatch.setattr("dreamforge_workflow_provider._public_https_url", lambda value: str(value))
    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: Response(json.dumps(_native_graph()).encode()))
    result = download_workflow("https://example.test/fox.json", filename="Fox Workflow")
    assert result["ok"] is True
    assert list((tmp_path / "library").glob("Fox_Workflow-*.json"))


def test_official_comfy_index_is_flattened_with_categories_and_filters():
    items = parse_workflow_index([
        {
            "title": "Image",
            "type": "image",
            "templates": [{
                "name": "image_fox",
                "title": "Fox Image",
                "description": "Text to image",
                "tags": ["Image", "Text to Image"],
                "models": ["Flux"],
                "openSource": True,
                "thumbnail": ["output/image_fox.png"],
            }],
        }
    ])
    assert items[0]["category"] == "Image"
    assert items[0]["tags"] == ["Image", "Text to Image"]
    assert items[0]["open_source"] is True
    assert items[0]["url"].endswith("/image_fox.json")
    assert items[0]["thumbnail_url"].endswith("/main/output/image_fox.png")


def test_download_rejects_unsafe_workflow(tmp_path, monkeypatch):
    class Response(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *args): return False

    monkeypatch.setattr("dreamforge_workflow_provider.WORKFLOW_DOWNLOAD_ROOT", tmp_path / "library")
    monkeypatch.setattr("dreamforge_workflow_provider._public_https_url", lambda value: str(value))
    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: Response(b'{"1":{"class_type":"ExecutePython","inputs":{}}}'))
    result = download_workflow("https://example.test/unsafe.json")
    assert result["ok"] is False
    assert not (tmp_path / "library" / "workflow.json").exists()


def test_workflow_provider_rejects_private_network_targets():
    assert _public_https_url("https://127.0.0.1/workflows.json") == ""
    assert _public_https_url("https://user:pass@example.com/workflows.json") == ""
