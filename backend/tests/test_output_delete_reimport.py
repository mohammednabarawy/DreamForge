"""Ensure deleted generations are removed from every storage location."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

import dreamforge_output_cleanup as cleanup
import dreamforge_output_index as output_index


def _patch_layout(tmp_path: Path, monkeypatch):
    outputs = tmp_path / "outputs"
    outputs.mkdir(parents=True)
    previews = tmp_path / "temp" / "previews"
    previews.mkdir(parents=True)
    staging = tmp_path / "temp" / "comfy-staging"
    staging.mkdir(parents=True)
    comfy_out = tmp_path / "engines" / "comfyui" / "output"
    comfy_out.mkdir(parents=True)
    comfy_in = tmp_path / "engines" / "comfyui" / "input"
    comfy_in.mkdir(parents=True)
    legacy_outputs = tmp_path / "backend" / "outputs"
    legacy_outputs.mkdir(parents=True)
    legacy_previews = tmp_path / "backend" / "temp" / "previews"
    legacy_previews.mkdir(parents=True)

    monkeypatch.setattr(output_index, "OUTPUTS_ROOT", outputs)
    monkeypatch.setattr(output_index, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(cleanup, "OUTPUTS_ROOT", outputs)
    monkeypatch.setattr(cleanup, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(cleanup, "PREVIEWS_DIR", previews)
    monkeypatch.setattr(cleanup, "COMFY_STAGING_DIR", staging)
    monkeypatch.setattr(cleanup, "COMFY_OUTPUT_DIR", comfy_out)
    monkeypatch.setattr(cleanup, "COMFY_INPUT_DIR", comfy_in)
    monkeypatch.setattr(cleanup, "BACKEND_LEGACY_OUTPUTS", legacy_outputs)
    monkeypatch.setattr(cleanup, "BACKEND_LEGACY_PREVIEWS", legacy_previews)
    monkeypatch.setattr(cleanup, "_ALLOWED_DELETE_ROOTS", [])
    return outputs, comfy_out, comfy_in, previews, staging, legacy_outputs


def test_delete_generation_removes_all_storage_copies(tmp_path, monkeypatch):
    outputs, comfy_out, comfy_in, previews, staging, legacy_outputs = _patch_layout(
        tmp_path, monkeypatch
    )

    image = outputs / "DreamForge_00001__1234567890.png"
    image.write_bytes(b"img")
    composite = outputs / "DreamForge_00001__1234567890_composite.png"
    composite.write_bytes(b"comp")
    nested = outputs / "dreamforge" / "DreamForge_00001__1234567890.png"
    nested.parent.mkdir(parents=True)
    nested.write_bytes(b"nested")
    legacy_copy = legacy_outputs / "DreamForge_00001__1234567890.png"
    legacy_copy.write_bytes(b"legacy")
    comfy_copy = comfy_out / "DreamForge_00001_.png"
    comfy_copy.write_bytes(b"img")
    comfy_input = comfy_in / "DreamForge_00001__999.png"
    comfy_input.write_bytes(b"in")
    staging_copy = staging / "DreamForge_00001__1234567890.png"
    staging_copy.write_bytes(b"stage")
    preview = previews / "preview-job-abc.jpg"
    preview.write_bytes(b"prev")
    legacy_preview = legacy_outputs / "preview-job-abc.jpg"
    legacy_preview.write_bytes(b"prev2")

    manifest = outputs / "DreamForge_00001__1234567890.generation_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "prompt": "portrait",
                "job_id": "job-abc",
                "images": [str(image)],
                "raw_images": ["DreamForge_00001_.png"],
            }
        ),
        encoding="utf-8",
    )

    result = output_index.delete_generation(str(manifest))
    assert result["ok"] is True
    for path in (
        manifest,
        image,
        composite,
        nested,
        legacy_copy,
        comfy_copy,
        comfy_input,
        staging_copy,
        preview,
        legacy_preview,
    ):
        assert not path.exists(), f"expected delete: {path}"
