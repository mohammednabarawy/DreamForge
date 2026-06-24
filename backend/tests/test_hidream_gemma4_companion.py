"""HiDream O1 Gemma4 companion dependency checks."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dreamforge_cli_inventory import (  # noqa: E402
    check_model_dependencies,
    hidream_o1_gemma4_requested,
)

MODEL = {"family": "hidream_o1", "name": "hidream_o1_image_dev_mxfp8.safetensors"}


def test_hidream_gemma4_requested_for_quality_only():
    assert hidream_o1_gemma4_requested("Quality")
    assert hidream_o1_gemma4_requested("quality")
    assert not hidream_o1_gemma4_requested("Speed")
    assert not hidream_o1_gemma4_requested("Lightning")
    assert hidream_o1_gemma4_requested("Speed", hidream_prompt_refinement=True)


def test_gemma4_listed_when_quality_performance(monkeypatch):
    monkeypatch.setattr(
        "dreamforge_cli_inventory.companion_file_present",
        lambda req, **kwargs: False,
    )
    missing = check_model_dependencies(MODEL, performance="Quality")
    assert any(item.get("id") == "gemma4_prompt_refine" for item in missing)
    gemma = next(item for item in missing if item.get("id") == "gemma4_prompt_refine")
    assert "Comfy-Org/gemma-4" in gemma["url"]
    assert gemma["relative"].endswith("gemma4_e4b_it_fp8_scaled.safetensors")


def test_gemma4_not_required_for_speed(monkeypatch):
    monkeypatch.setattr(
        "dreamforge_cli_inventory.companion_file_present",
        lambda req, **kwargs: False,
    )
    missing = check_model_dependencies(MODEL, performance="Speed")
    assert not any(item.get("id") == "gemma4_prompt_refine" for item in missing)


def test_gemma4_skipped_when_present(monkeypatch):
    monkeypatch.setattr(
        "dreamforge_cli_inventory.companion_file_present",
        lambda req, **kwargs: req.get("id") == "gemma4_prompt_refine",
    )
    missing = check_model_dependencies(MODEL, performance="Quality")
    assert not missing
