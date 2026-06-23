"""Tests for history output deletion (images + manifest metadata)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

import dreamforge_output_index as output_index


def _patch_outputs_root(tmp_path: Path, monkeypatch):
    outputs = tmp_path / "outputs"
    outputs.mkdir(parents=True)
    monkeypatch.setattr(output_index, "OUTPUTS_ROOT", outputs)
    monkeypatch.setattr(output_index, "PROJECT_ROOT", tmp_path)
    return outputs


def test_delete_generation_removes_manifest_raw_and_sidecars(tmp_path, monkeypatch):
    outputs = _patch_outputs_root(tmp_path, monkeypatch)
    session = outputs / "dreamforge"
    session.mkdir()

    image = session / "shot.png"
    raw = session / "shot_raw.png"
    composite = session / "shot_composite.png"
    image.write_bytes(b"img")
    raw.write_bytes(b"raw")
    composite.write_bytes(b"comp")

    manifest = session / "shot.generation_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "prompt": "portrait",
                "images": [str(image)],
                "raw_images": [str(raw)],
                "validation": [{"ok": True}],
            }
        ),
        encoding="utf-8",
    )

    result = output_index.delete_generation(str(manifest))
    assert result["ok"] is True
    assert not manifest.exists()
    assert not image.exists()
    assert not raw.exists()
    assert not composite.exists()


def test_delete_output_image_removes_last_image_and_manifest(tmp_path, monkeypatch):
    outputs = _patch_outputs_root(tmp_path, monkeypatch)
    session = outputs / "dreamforge"
    session.mkdir()

    image = session / "solo.png"
    raw = session / "solo_raw.png"
    image.write_bytes(b"img")
    raw.write_bytes(b"raw")

    manifest = session / "solo.generation_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "prompt": "solo",
                "images": [str(image)],
                "raw_images": [str(raw)],
            }
        ),
        encoding="utf-8",
    )

    result = output_index.delete_output_image(str(manifest), str(image))
    assert result["ok"] is True
    assert result.get("manifest_removed") is True
    assert not manifest.exists()
    assert not image.exists()
    assert not raw.exists()


def test_delete_output_image_updates_manifest_for_batch(tmp_path, monkeypatch):
    outputs = _patch_outputs_root(tmp_path, monkeypatch)
    session = outputs / "dreamforge"
    session.mkdir()

    first = session / "a.png"
    second = session / "b.png"
    second_raw = session / "b_raw.png"
    first.write_bytes(b"a")
    second.write_bytes(b"b")
    second_raw.write_bytes(b"br")

    manifest = session / "a.generation_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "prompt": "batch",
                "images": [str(first), str(second)],
                "raw_images": [str(first), str(second_raw)],
                "validation": [{"ok": True}, {"ok": True}],
                "lineage": {"output_images": [str(first), str(second)]},
            }
        ),
        encoding="utf-8",
    )

    result = output_index.delete_output_image(str(manifest), str(second))
    assert result["ok"] is True
    assert manifest.exists()
    assert first.exists()
    assert not second.exists()
    assert not second_raw.exists()

    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert data["images"] == [str(first)]
    assert data["raw_images"] == [str(first)]
    assert len(data["validation"]) == 1
    assert data["lineage"]["output_images"] == [str(first)]
