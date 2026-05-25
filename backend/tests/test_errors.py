"""Tests for the structured error codes used by the GPU worker."""
from __future__ import annotations

from pathlib import Path
import sys

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from dreamforge_errors import (
    disk_full,
    from_exception,
    invalid_input_image,
    missing_input_image,
    missing_model_dependencies,
    out_of_memory,
)


def _is_error(payload: dict, code: str) -> None:
    assert payload["type"] == "error"
    assert payload["code"] == code
    # Legacy alias preserved for older Tauri readers.
    assert payload["error"] == code
    assert isinstance(payload["message"], str)
    assert payload["message"]


def test_out_of_memory_carries_details_and_suggestions():
    payload = out_of_memory(free_gb=0.42, vram_profile="low", job_id="abc")
    _is_error(payload, "out_of_memory")
    assert payload["details"]["free_gb"] == 0.42
    assert payload["details"]["vram_profile"] == "low"
    assert payload["recoverable"] is True
    assert payload["job_id"] == "abc"
    assert any("VRAM" in s or "memory" in s.lower() for s in payload["suggestions"])


def test_missing_input_image_is_recoverable():
    payload = missing_input_image(job_id="job-1")
    _is_error(payload, "missing_input_image")
    assert payload["recoverable"] is True
    assert payload["job_id"] == "job-1"
    assert payload["suggestions"]


def test_invalid_input_image_includes_path_in_details():
    payload = invalid_input_image("file gone", path="C:/missing.png")
    _is_error(payload, "invalid_input_image")
    assert payload["details"]["path"] == "C:/missing.png"


def test_missing_model_dependencies_summarises_names():
    payload = missing_model_dependencies(
        [
            {"name": "clip_l.safetensors", "kind": "text_encoder"},
            {"name": "ae.safetensors", "kind": "vae"},
        ]
    )
    _is_error(payload, "missing_model_dependencies")
    assert "clip_l.safetensors" in payload["message"]
    assert "ae.safetensors" in payload["message"]
    assert payload["details"]["missing"]


def test_disk_full_emits_details_when_available():
    payload = disk_full("No space left on device", path="D:/outputs/x.png")
    _is_error(payload, "disk_full")
    assert payload["details"]["path"] == "D:/outputs/x.png"
    assert payload["recoverable"] is True


def test_from_exception_maps_oom_string_to_out_of_memory():
    payload = from_exception(RuntimeError("CUDA out of memory: tried 8 GB"))
    _is_error(payload, "out_of_memory")
    assert "CUDA out of memory" in payload["details"]["exception"]


def test_from_exception_maps_enospc_to_disk_full():
    err = OSError(28, "No space left on device", "C:/outputs/x.png")
    payload = from_exception(err)
    _is_error(payload, "disk_full")
    assert "C:/outputs/x.png" in payload["details"]["path"]


def test_from_exception_falls_back_to_generation_failed():
    payload = from_exception(ValueError("bad seed"))
    _is_error(payload, "generation_failed")
    assert "bad seed" in payload["message"]
    assert payload["details"]["exception"].startswith("ValueError:")
