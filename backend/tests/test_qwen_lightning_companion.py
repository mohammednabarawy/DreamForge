"""Qwen Edit Lightning LoRA companion dependency checks."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dreamforge_cli_inventory import (
    check_model_dependencies,
    qwen_lightning_lora_requested,
)


def test_qwen_lightning_lora_requested_for_speed_modes():
    assert qwen_lightning_lora_requested("Speed")
    assert qwen_lightning_lora_requested("Lightning")
    assert qwen_lightning_lora_requested("Lcm")
    assert not qwen_lightning_lora_requested("Quality")


def test_lightning_lora_listed_when_speed_performance(monkeypatch):
    monkeypatch.setattr(
        "dreamforge_cli_inventory.qwen_lightning_lora_present",
        lambda **kwargs: False,
    )
    monkeypatch.setattr(
        "dreamforge_cli_inventory.companion_file_present",
        lambda req, **kwargs: False,
    )
    model = {"family": "qwen_image_edit", "name": "qwen_image_edit_fp8_e4m3fn.safetensors"}
    missing = check_model_dependencies(model, performance="Speed")
    assert any(item.get("id") == "lora_qwen_edit_lightning_4step" for item in missing)
    assert missing[0].get("url")


def test_lightning_lora_not_required_for_quality(monkeypatch):
    monkeypatch.setattr(
        "dreamforge_cli_inventory.qwen_lightning_lora_present",
        lambda **kwargs: False,
    )
    monkeypatch.setattr(
        "dreamforge_cli_inventory.companion_file_present",
        lambda req, **kwargs: True,
    )
    model = {"family": "qwen_image_edit", "name": "qwen_image_edit_fp8_e4m3fn.safetensors"}
    missing = check_model_dependencies(model, performance="Quality")
    assert not any(item.get("id") == "lora_qwen_edit_lightning_4step" for item in missing)
