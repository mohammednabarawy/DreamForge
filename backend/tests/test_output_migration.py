"""Tests for flattening legacy outputs into outputs/ root."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

import dreamforge_output_migration as migration


def _patch_common(monkeypatch, tmp_path, outputs: Path):
    previews = tmp_path / "temp" / "previews"
    staging = tmp_path / "temp" / "comfy-staging"
    monkeypatch.setattr(migration, "OUTPUTS_ROOT", outputs)
    monkeypatch.setattr(migration, "TARGET_DIR", outputs)
    monkeypatch.setattr(migration, "LEGACY_SESSION_DIR", outputs / "dreamforge")
    monkeypatch.setattr(migration, "LEGACY_NESTED_DIR", outputs / "dreamforge" / "comfy")
    monkeypatch.setattr(migration, "PREVIEWS_DIR", previews)
    monkeypatch.setattr(migration, "COMFY_STAGING_DIR", staging)
    monkeypatch.setattr(migration, "BACKEND_LEGACY_OUTPUTS", tmp_path / "backend" / "outputs")
    monkeypatch.setattr(migration, "CONFIG_PATH", tmp_path / "config.txt")


def test_migrate_flattens_nested_session_folder(tmp_path, monkeypatch):
    outputs = tmp_path / "outputs"
    dreamforge = outputs / "dreamforge"
    dreamforge.mkdir(parents=True)

    png = dreamforge / "gen_old.png"
    png.write_bytes(b"png")
    manifest = dreamforge / "gen_old.generation_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "prompt": "test",
                "images": [str(dreamforge / "gen_old.png")],
            }
        ),
        encoding="utf-8",
    )

    _patch_common(monkeypatch, tmp_path, outputs)
    result = migration.migrate_legacy_outputs()

    assert result["ok"] is True
    assert result["moved_count"] == 2
    assert not png.exists()
    assert (outputs / "gen_old.png").is_file()
    assert (outputs / "gen_old.generation_manifest.json").is_file()
    data = json.loads((outputs / "gen_old.generation_manifest.json").read_text(encoding="utf-8"))
    assert data["images"][0].replace("\\", "/").endswith("outputs/gen_old.png")


def test_migrate_flattens_comfy_subfolder(tmp_path, monkeypatch):
    outputs = tmp_path / "outputs"
    comfy = outputs / "dreamforge" / "comfy"
    comfy.mkdir(parents=True)

    png = comfy / "item.png"
    png.write_bytes(b"x")
    manifest = comfy / "item.generation_manifest.json"
    manifest.write_text(
        json.dumps({"images": [str(comfy / "item.png")]}),
        encoding="utf-8",
    )

    _patch_common(monkeypatch, tmp_path, outputs)
    result = migration.migrate_legacy_outputs()

    assert result["moved_count"] == 2
    assert (outputs / "item.png").is_file()
    assert not comfy.exists()


def test_migrate_moves_previews_to_temp(tmp_path, monkeypatch):
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    (outputs / "preview.jpg").write_bytes(b"j")
    (outputs / "preview-abc.jpg").write_bytes(b"j")

    _patch_common(monkeypatch, tmp_path, outputs)
    result = migration.migrate_legacy_outputs()

    assert result["moved_count"] == 0
    assert result["preview_migration"]["moved_count"] == 2
    previews = tmp_path / "temp" / "previews"
    assert (previews / "preview.jpg").is_file()
    assert (previews / "preview-abc.jpg").is_file()
    assert not (outputs / "preview.jpg").exists()


def test_migrate_imports_comfy_primary_outputs(tmp_path, monkeypatch):
    outputs = tmp_path / "outputs"
    outputs.mkdir(parents=True)
    comfy_out = tmp_path / "engines" / "comfyui" / "output"
    comfy_out.mkdir(parents=True)

    png = comfy_out / "DreamForge_00042_.png"
    png.write_bytes(b"png-data")
    (comfy_out / "DreamForge_00042_kontext_refs.png").write_bytes(b"skip")

    _patch_common(monkeypatch, tmp_path, outputs)
    monkeypatch.setattr(migration, "COMFY_OUTPUT_DIR", comfy_out)

    result = migration.migrate_legacy_outputs()

    assert result["comfy_import"]["imported_count"] == 1
    assert not png.exists()
    imported = list(outputs.glob("DreamForge_00042__*.png"))
    assert len(imported) == 1
    manifest = outputs / f"{imported[0].stem}.generation_manifest.json"
    assert manifest.is_file()
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert data["images"][0].replace("\\", "/").endswith(imported[0].name)
