"""Tests for the structured error codes used by the GPU worker."""
from __future__ import annotations

from pathlib import Path
import sys

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from dreamforge_errors import (
    build_failure_report,
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
    report = payload["failure_report"]
    assert report["auto_retry"] is False
    assert any(action["action"] == "reduce_resolution" for action in report["repair_actions"])
    assert any(action["action"] == "retry_with_safer_settings" and action["requires_approval"] for action in report["repair_actions"])


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


def test_missing_model_dependencies_carries_approval_repair_actions():
    payload = missing_model_dependencies(
        [{"name": "clip_l.safetensors", "kind": "text_encoder"}],
        actions=[
            {
                "action": "download_model_companions",
                "missing": [{"id": "clip_l_flux", "relative": "text_encoders/clip_l.safetensors"}],
            }
        ],
    )

    report = payload["failure_report"]

    assert report["requires_user_approval"] is True
    download = next(action for action in report["repair_actions"] if action["action"] == "download_model_companions")
    assert download["requires_approval"] is True
    assert download["missing"][0]["id"] == "clip_l_flux"


def test_disk_full_emits_details_when_available():
    payload = disk_full("No space left on device", path="D:/outputs/x.png")
    _is_error(payload, "disk_full")
    assert payload["details"]["path"] == "D:/outputs/x.png"
    assert payload["recoverable"] is True


def test_from_exception_maps_oom_string_to_out_of_memory():
    payload = from_exception(RuntimeError("CUDA out of memory: tried 8 GB"))
    _is_error(payload, "out_of_memory")
    assert "CUDA out of memory" in payload["details"]["exception"]


def test_from_exception_maps_missing_comfy_node_to_approval_install_action():
    class ComfyExecutionError(RuntimeError):
        def __init__(self):
            super().__init__("Node type 'IPAdapterModelLoader' does not exist")
            self.details = {
                "status": {
                    "messages": [
                        [
                            "execution_error",
                            {
                                "node_type": "IPAdapterModelLoader",
                                "exception_message": "missing node",
                            },
                        ]
                    ]
                }
            }

    payload = from_exception(ComfyExecutionError())

    _is_error(payload, "missing_custom_node_pack")
    report = payload["failure_report"]
    install = next(action for action in report["repair_actions"] if action["action"] == "install_custom_node_pack")
    replace = next(action for action in report["repair_actions"] if action["action"] == "replace_node_pattern")
    assert install["requires_approval"] is True
    assert replace["requires_approval"] is True
    assert "IPAdapterModelLoader" in install["nodes"]
    assert report["auto_retry"] is False


def test_from_exception_maps_unsupported_workflow_class_to_rebuild_actions():
    payload = from_exception(ValueError("unsupported workflow class: community_raw_graph"))

    _is_error(payload, "unsupported_workflow_class")
    report = payload["failure_report"]
    assert payload["details"]["workflow_class"] == "community_raw_graph"
    assert any(action["action"] == "replace_node_pattern" for action in report["repair_actions"])
    assert any(action["action"] == "rebuild_workflow_plan" for action in report["repair_actions"])


def test_from_exception_maps_windows_paging_file_to_virtual_memory_low():
    exc = OSError(1455, "The paging file is too small for this operation to complete.")
    if sys.platform == "win32":
        exc.winerror = 1455  # type: ignore[attr-defined]
    payload = from_exception(exc)
    _is_error(payload, "virtual_memory_low")
    assert payload["recoverable"] is True
    assert any("paging file" in s.lower() for s in payload["suggestions"])


def test_from_exception_maps_comfy_execution_paging_file_to_virtual_memory_low():
    class ComfyExecutionError(RuntimeError):
        pass

    payload = from_exception(
        ComfyExecutionError(
            "DualCLIPLoader: The paging file is too small for this operation to complete. (os error 1455)"
        )
    )
    _is_error(payload, "virtual_memory_low")


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


def test_build_failure_report_never_auto_retries_expensive_repairs():
    report = build_failure_report("comfy_server_crashed", "server went away", recoverable=True)

    assert report is not None
    assert report["auto_retry"] is False
    assert report["max_auto_retries"] == 0
    assert any(action["requires_approval"] for action in report["repair_actions"])
