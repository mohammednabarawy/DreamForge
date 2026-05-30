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
