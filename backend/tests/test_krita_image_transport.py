"""Krita cache transport must survive retries without changing pixels or masks."""
import io
import json
from copy import deepcopy
from datetime import datetime
from unittest.mock import Mock

import pytest
from PIL import Image

from dreamforge_comfy_client import ComfyClient, ComfyExecutionError
from dreamforge_cli_direct import _resolve_output_paths
from dreamforge_output_cleanup import seq_from_filename
import dreamforge_output_index as index


def test_cache_transport_and_restart_preserve_graph_and_alpha(monkeypatch, tmp_path):
    buffer = io.BytesIO()
    Image.new("RGBA", (8, 6), (10, 20, 30, 64)).save(buffer, format="PNG")
    data = buffer.getvalue()
    client = ComfyClient("http://comfy")
    name = client.stage_image(image_bytes=data, filename="reference.png")["name"]
    assert client.stage_image(image_bytes=data, filename="another-name.png")["name"] == name
    client._object_info = {"ETN_LoadImageCache": {}, "ETN_SaveImageCache": {}}
    native = Mock(side_effect=AssertionError("must not upload to disk"))
    monkeypatch.setattr(client, "upload_image", native)
    requests = []
    response = Mock()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.read.return_value = data
    monkeypatch.setattr("urllib.request.urlopen", lambda req, **kw: requests.append(req) or response)
    graph = {
        "1": {"class_type": "LoadImage", "inputs": {"image": name}},
        "2": {"class_type": "SaveImage", "inputs": {"images": ["1", 0], "filename_prefix": "test"}},
        "3": {"class_type": "MaskToImage", "inputs": {"mask": ["1", 1]}},
    }
    original = deepcopy(graph)
    prepared = client._prepare_image_transport(graph)
    assert graph == original
    assert prepared["1"]["class_type"] == "ETN_LoadImageCache"
    assert prepared["2"]["class_type"] == "ETN_SaveImageCache"
    assert prepared["3"]["inputs"]["mask"] == ["1", 1]
    with Image.open(io.BytesIO(requests[0].data)) as image:
        assert image.getpixel((0, 0)) == (10, 20, 30, 191)
    monkeypatch.setattr(client, "object_info", lambda **kw: {"ETN_LoadImageCache": {}, "ETN_SaveImageCache": {}})
    assert client.reconnect("http://restarted") is client
    retried = client._prepare_image_transport(graph)
    assert retried["2"]["inputs"]["_dreamforge_transfer_id"] != prepared["2"]["inputs"]["_dreamforge_transfer_id"]
    assert requests[-1].full_url.startswith("http://restarted/api/etn/image/")
    assert client.result_image({"source": "http", "id": "result-id"}) == data
    assert requests[-1].get_method() == "GET"
    staged = tmp_path / "staged.png"
    staged.write_bytes(data)
    saved = _resolve_output_paths([str(staged)], str(tmp_path / "outputs"), consume=True)
    assert not staged.exists()
    with Image.open(saved[0]) as image:
        assert image.size == (8, 6) and image.getpixel((0, 0)) == (10, 20, 30, 64)
    assert _resolve_output_paths(saved, str(tmp_path / "outputs"), consume=True) == saved
    assert seq_from_filename("DreamForge_12abcdef.png") is None
    assert seq_from_filename("DreamForge_00012__123.png") == 12


def test_legacy_server_fallback_and_expired_cache(monkeypatch):
    client = ComfyClient("http://comfy")
    client._object_info = {}
    name = client.stage_image(image_bytes=b"png", filename="source.png")["name"]
    monkeypatch.setattr(client, "upload_image", lambda **kw: {"name": "actual.png", "subfolder": "job"})
    graph = client._prepare_image_transport({"1": {"class_type": "LoadImage", "inputs": {"image": name}},
        "2": {"class_type": "SaveImage", "inputs": {"images": ["1", 0], "filename_prefix": "test"}}})
    assert graph["1"]["inputs"]["image"] == "job/actual.png"
    assert graph["2"]["class_type"] == "SaveImage"
    monkeypatch.setattr(client, "view", lambda **kw: b"native png")
    assert client.result_image({"filename": "actual.png"}) == b"native png"
    from urllib.error import HTTPError
    monkeypatch.setattr("urllib.request.urlopen", Mock(side_effect=HTTPError("cache", 404, "missing", {}, None)))
    with pytest.raises(ComfyExecutionError, match="cache expired"):
        client.result_image({"source": "http", "id": "expired"})


def test_library_filters_before_pagination_and_ignores_missing_images(monkeypatch, tmp_path):
    monkeypatch.setattr(index, "OUTPUTS_ROOT", tmp_path)
    manifests = []
    for number in range(4):
        project = tmp_path / ("one" if number % 2 else "two")
        project.mkdir(exist_ok=True)
        image = project / f"{number}.png"
        if number != 3:
            image.write_bytes(b"image")
        manifest = project / f"{number}.generation_manifest.json"
        manifest.write_text(json.dumps({"prompt": "hello\nworld", "model": {"name": "qwen"},
            "images": [str(image), str(image)]}))
        manifests.append(str(manifest))
    items, total = index.list_outputs(limit=1)
    assert total == 3 and len(items) == 1 and len(items[0]["images"]) == 1
    assert datetime.fromisoformat(items[0]["timestamp"]).utcoffset() is not None
    items, total = index.search_outputs("hello\nworld", session="one", limit=1)
    assert total == 1 and items[0]["session"] == "one"
    items, total = index.list_outputs(manifest_paths=[manifests[0]], limit=1)
    assert total == 1 and items[0]["manifest_path"] == manifests[0]
    assert index.list_outputs(manifest_paths=[])[1] == 0
    assert len(index.search_outputs("qwen", limit=1, offset=2)[0]) == 1
    from dreamforge_agent_tools import write_manifest
    written = write_manifest(str(tmp_path / "atomic.generation_manifest.json"), {"prompt": "hello\nworld"})
    assert json.loads(open(written).read())["prompt"] == "hello\nworld"
    assert not list(tmp_path.glob("*.tmp"))
    outside = tmp_path.parent / "outside.json"
    outside.write_text('{}')
    assert index.get_generation_bundle(str(outside))["status"] == "error"
    unrelated = tmp_path / "one" / "keep.txt"
    unrelated.write_text("not a generated image")
    deleted = index.delete_session("one")
    assert deleted["ok"] and unrelated.is_file()
    assert deleted["preserved_directory"] == str(tmp_path / "one")


def test_saved_png_import_restores_multiline_settings_and_actual_dimensions(tmp_path):
    from dreamforge_generation import _save_comfy_result_png
    from dreamforge_image_metadata import import_image_metadata

    path = tmp_path / "composite.png"
    graph = {"1": {"class_type": "ETN_SaveImageCache", "inputs": {}}}
    parameters = {"Prompt": "مرحبا\nSecond line", "Negative": "text\nblur", "model": "qwen.safetensors",
                  "seed": 42, "steps": 20, "cfg": 2.5, "sampler_name": "euler", "scheduler": "beta",
                  "width": 4, "height": 4}
    _save_comfy_result_png(Image.new("RGBA", (8, 6), (10, 20, 30, 64)), path, graph, parameters)
    with Image.open(path) as image:
        assert image.getpixel((0, 0)) == (10, 20, 30, 64)
        assert json.loads(image.info["prompt"]) == graph
    imported = import_image_metadata(str(path))
    assert imported["ok"]
    patch = imported["patch"]
    assert patch["prompt"] == parameters["Prompt"] and patch["negative_prompt"] == parameters["Negative"]
    assert (patch["width"], patch["height"], patch["seed"], patch["cfg_scale"]) == (8, 6, 42, 2.5)
    assert patch["model"] == "qwen.safetensors" and patch["scheduler"] == "beta"
