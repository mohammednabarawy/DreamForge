from __future__ import annotations

import json
import struct
import sys
import zlib
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from research_comfy_workflows import (  # noqa: E402
    classify_node_types,
    node_types_from_payload,
    parse_workflow_payload,
    png_text_chunks,
)


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)


def test_source_metadata_tags_official_examples():
    from research_comfy_workflows import source_metadata

    source_class, license_note = source_metadata(
        "https://comfyanonymous.github.io/ComfyUI_examples/flux/workflow.json",
        "public-web",
    )
    assert source_class == "official_examples"
    assert "license" in license_note.lower()


def test_classifies_api_format_txt2img_and_flux():
    payload = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "flux.safetensors"}},
        "2": {"class_type": "DualCLIPLoader", "inputs": {}},
        "3": {"class_type": "EmptySD3LatentImage", "inputs": {}},
        "4": {"class_type": "FluxGuidance", "inputs": {}},
        "5": {"class_type": "KSampler", "inputs": {}},
    }

    node_types = node_types_from_payload(payload)
    tasks = classify_node_types(node_types)

    assert "txt2img" in tasks
    assert "flux" in tasks


def test_classifies_ui_format_inpaint_and_compositing():
    payload = {
        "nodes": [
            {"type": "LoadImage"},
            {"type": "LoadImageMask"},
            {"type": "VAEEncodeForInpaint"},
            {"type": "KSampler"},
            {"type": "ImageCompositeMasked"},
        ]
    }

    tasks = classify_node_types(node_types_from_payload(payload))

    assert "inpaint" in tasks
    assert "compositing" in tasks


def test_extracts_png_workflow_metadata(tmp_path):
    workflow = {"prompt": {"1": {"class_type": "LoadUpscaleModel", "inputs": {}}}}
    png = (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + _png_chunk(b"tEXt", b"workflow\x00" + json.dumps(workflow).encode("utf-8"))
        + _png_chunk(b"IEND", b"")
    )
    path = tmp_path / "workflow.png"
    path.write_bytes(png)

    chunks = png_text_chunks(png)
    payloads = parse_workflow_payload(path)

    assert "workflow" in chunks
    assert any("prompt" in payload for payload in payloads)
    assert "upscale" in classify_node_types(["LoadUpscaleModel"])


def test_research_output_dir_must_live_under_dot_research(tmp_path):
    from research_comfy_workflows import RESEARCH_ROOT, validate_research_output_dir

    allowed = validate_research_output_dir(RESEARCH_ROOT)
    assert str(allowed).endswith("comfy_workflow_research")

    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        validate_research_output_dir(outside, force=False)
        assert False, "expected refusal for path outside .research"
    except SystemExit:
        pass

    forced = validate_research_output_dir(outside, force=True)
    assert forced == outside.resolve()


def test_research_main_writes_only_to_output_dir(tmp_path, monkeypatch):
    from research_comfy_workflows import main

    out_dir = tmp_path / "comfy_workflow_research"
    artifacts = out_dir / "artifacts"
    artifacts.mkdir(parents=True)
    sample = artifacts / "sample.json"
    sample.write_text('{"1": {"class_type": "KSampler", "inputs": {}}}', encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    code = main(["--no-network", "--out", str(out_dir), "--force-out"])
    assert code == 0
    assert (out_dir / "workflow_index.json").is_file()
    assert (out_dir / "ANALYSIS.md").is_file()
    index = json.loads((out_dir / "workflow_index.json").read_text(encoding="utf-8"))
    assert index[0]["source_class"]
    assert index[0]["license_note"]


def test_research_module_does_not_execute_workflows():
    import research_comfy_workflows as research

    source = Path(research.__file__).read_text(encoding="utf-8").lower()
    assert "dreamforge_generation" not in source
    assert "subprocess" not in source
    assert "execute_job" not in source
