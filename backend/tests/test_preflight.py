"""Tests for dreamforge_preflight."""
from __future__ import annotations

import os
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

import dreamforge_preflight as pf
from dreamforge_preflight import run_preflight


def _write_fake_safetensors(path: Path, header_len: int = 16) -> None:
    """Write a minimal safetensors with a sane 8-byte LE header length.

    We don't need a parseable JSON body for the preflight: it only sniffs the
    first 8 bytes for the length, then trusts the rest.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as fh:
        fh.write(header_len.to_bytes(8, "little"))
        fh.write(b"{" + b" " * (header_len - 2) + b"}")


def test_model_not_found_returns_error(tmp_path, monkeypatch):
    monkeypatch.setattr(pf, "MODELS_ROOT", tmp_path / "models")
    monkeypatch.setattr(pf, "DEFAULT_OUTPUT_ROOT", tmp_path / "outputs")
    result = run_preflight({"name": "missing_model.safetensors", "category": "checkpoints"})
    assert result.has_errors
    assert result.errors[0]["code"] == "model_not_found"


def test_disk_full_error_when_under_floor(tmp_path, monkeypatch):
    models_dir = tmp_path / "models" / "checkpoints"
    _write_fake_safetensors(models_dir / "model.safetensors")
    monkeypatch.setattr(pf, "MODELS_ROOT", tmp_path / "models")
    monkeypatch.setattr(pf, "DEFAULT_OUTPUT_ROOT", tmp_path / "outputs")
    monkeypatch.setattr(pf, "_disk_free_gb", lambda _p: 0.1)
    model = {"name": "model.safetensors", "category": "checkpoints", "family": "sdxl"}
    result = run_preflight(model)
    assert result.has_errors
    assert result.errors[0]["code"] == "disk_full"
    detail = result.errors[0].get("details", {}).get("detail", "")
    assert "0.10" in detail or "0.1" in detail


def test_low_disk_emits_warning_but_not_error(tmp_path, monkeypatch):
    models_dir = tmp_path / "models" / "checkpoints"
    _write_fake_safetensors(models_dir / "model.safetensors")
    monkeypatch.setattr(pf, "MODELS_ROOT", tmp_path / "models")
    monkeypatch.setattr(pf, "DEFAULT_OUTPUT_ROOT", tmp_path / "outputs")
    monkeypatch.setattr(pf, "_disk_free_gb", lambda _p: 1.0)
    monkeypatch.setattr(pf, "_free_vram_gb", lambda: None)
    model = {"name": "model.safetensors", "category": "checkpoints", "family": "sdxl", "size_mb": 6500}
    result = run_preflight(model)
    assert not result.has_errors
    codes = [w["code"] for w in result.warnings]
    assert "low_disk_space" in codes


def test_flux_fp8_16gb_gpu_no_false_vram_warning(tmp_path, monkeypatch):
    """16 GB cards with ~15 GB free should run fp8 Flux without VRAM noise."""
    models_dir = tmp_path / "models" / "checkpoints"
    _write_fake_safetensors(models_dir / "flux1-schnell-fp8.safetensors")
    monkeypatch.setattr(pf, "MODELS_ROOT", tmp_path / "models")
    monkeypatch.setattr(pf, "DEFAULT_OUTPUT_ROOT", tmp_path / "outputs")
    monkeypatch.setattr(pf, "_disk_free_gb", lambda _p: 50.0)
    monkeypatch.setattr(pf, "_free_vram_gb", lambda: 14.8)
    monkeypatch.setattr(
        pf,
        "_memory_status",
        lambda: {
            "total_phys_gb": 28.0,
            "avail_phys_gb": 9.0,
            "commit_limit_gb": 57.0,
            "avail_commit_gb": 40.0,
        },
    )
    model = {
        "name": "flux1-schnell-fp8.safetensors",
        "category": "checkpoints",
        "family": "flux",
        "size_mb": 16_400,
    }
    result = run_preflight(model)
    assert not result.has_errors
    codes = [w["code"] for w in result.warnings]
    assert "vram_headroom_low" not in codes
    assert "low_system_ram" not in codes


def test_insufficient_commit_budget_blocks_generation(tmp_path, monkeypatch):
    models_dir = tmp_path / "models" / "diffusion_models"
    _write_fake_safetensors(models_dir / "flux1-dev-kontext_fp8_scaled.safetensors")
    monkeypatch.setattr(pf, "MODELS_ROOT", tmp_path / "models")
    monkeypatch.setattr(pf, "DEFAULT_OUTPUT_ROOT", tmp_path / "outputs")
    monkeypatch.setattr(pf, "_disk_free_gb", lambda _p: 50.0)
    monkeypatch.setattr(pf, "_free_vram_gb", lambda: 14.8)
    monkeypatch.setattr(
        pf,
        "_memory_status",
        lambda: {
            "total_phys_gb": 28.0,
            "avail_phys_gb": 5.7,
            "commit_limit_gb": 57.0,
            "avail_commit_gb": 5.7,
        },
    )
    model = {
        "name": "flux1-dev-kontext_fp8_scaled.safetensors",
        "category": "diffusion_models",
        "family": "flux_kontext",
        "size_mb": 11_353,
    }
    result = run_preflight(model)
    assert result.has_errors
    assert result.errors[0]["code"] == "virtual_memory_low"


def test_vram_warning_when_estimate_exceeds_free(tmp_path, monkeypatch):
    models_dir = tmp_path / "models" / "diffusion_models"
    _write_fake_safetensors(models_dir / "flux1-dev-fp8.safetensors")
    monkeypatch.setattr(pf, "MODELS_ROOT", tmp_path / "models")
    monkeypatch.setattr(pf, "DEFAULT_OUTPUT_ROOT", tmp_path / "outputs")
    monkeypatch.setattr(pf, "_disk_free_gb", lambda _p: 50.0)
    monkeypatch.setattr(pf, "_free_vram_gb", lambda: 4.0)
    model = {
        "name": "flux1-dev-fp8.safetensors",
        "category": "diffusion_models",
        "family": "flux",
        "size_mb": 11_000,
    }
    result = run_preflight(model)
    assert not result.has_errors
    codes = [w["code"] for w in result.warnings]
    assert "vram_headroom_low" in codes
    warn = next(w for w in result.warnings if w["code"] == "vram_headroom_low")
    assert warn["type"] == "warning"
    assert warn["details"]["estimated_vram_gb"] > warn["details"]["free_vram_gb"]


def test_unreadable_safetensors_returns_error(tmp_path, monkeypatch):
    models_dir = tmp_path / "models" / "checkpoints"
    models_dir.mkdir(parents=True)
    # Write a stub with header length too small (truncated).
    (models_dir / "bad.safetensors").write_bytes(b"\x00\x00\x00")
    monkeypatch.setattr(pf, "MODELS_ROOT", tmp_path / "models")
    monkeypatch.setattr(pf, "DEFAULT_OUTPUT_ROOT", tmp_path / "outputs")
    result = run_preflight({"name": "bad.safetensors", "category": "checkpoints"})
    assert result.has_errors
    assert result.errors[0]["code"] == "model_file_unreadable"


def test_run_preflight_dict_payload_is_serialisable(tmp_path, monkeypatch):
    models_dir = tmp_path / "models" / "checkpoints"
    _write_fake_safetensors(models_dir / "model.safetensors")
    monkeypatch.setattr(pf, "MODELS_ROOT", tmp_path / "models")
    monkeypatch.setattr(pf, "DEFAULT_OUTPUT_ROOT", tmp_path / "outputs")
    monkeypatch.setattr(pf, "_disk_free_gb", lambda _p: 50.0)
    monkeypatch.setattr(pf, "_free_vram_gb", lambda: 24.0)
    model = {"name": "model.safetensors", "category": "checkpoints", "family": "sdxl", "size_mb": 6500}
    result = run_preflight(model)
    payload = result.as_dict()
    import json
    json.dumps(payload)  # must not raise
    assert payload["info"]["model_path"].endswith("model.safetensors")
