"""Tests for GPU detection and system repair modules."""

from dreamforge_gpu_detect import detect_gpu
from dreamforge_repair import run_system_repair


def test_detect_gpu_returns_dict():
    info = detect_gpu()
    assert isinstance(info, dict)
    assert "vendor" in info
    assert "recommended_profile" in info
    assert "vram_mb" in info


def test_run_system_repair_executes():
    res = run_system_repair(clear_cache=True, reset_config=False, reverify_nodes=True)
    assert res["status"] == "success"
    assert isinstance(res["actions_taken"], list)
    assert isinstance(res["logs"], list)
