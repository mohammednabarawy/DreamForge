"""Tests for smart inpaint mask selection."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image


def _solid_png(path: Path, color: tuple[int, int, int], size: tuple[int, int] = (128, 128)) -> Path:
    Image.new("RGB", size, color).save(path)
    return path


def test_tap_object_selects_local_region(tmp_path: Path):
    from dreamforge_inpaint_selection import generate_inpaint_selection_mask

    image = _solid_png(tmp_path / "scene.png", (240, 240, 240))
    # Paint a red square to tap inside.
    img = Image.open(image)
    pixels = img.load()
    for y in range(40, 88):
        for x in range(40, 88):
            pixels[x, y] = (220, 40, 40)
    img.save(image)

    result = generate_inpaint_selection_mask(
        str(image),
        "tap_object",
        tap_x=0.5,
        tap_y=0.5,
    )
    assert result["ok"] is True
    mask = np.array(Image.open(result["mask_path"]).convert("L"))
    assert np.count_nonzero(mask > 127) > 100
    assert np.count_nonzero(mask > 127) < mask.size * 0.6


def test_background_inverts_subject(monkeypatch, tmp_path: Path):
    from dreamforge_inpaint_selection import generate_inpaint_selection_mask

    image = _solid_png(tmp_path / "portrait.png", (180, 180, 180))

    subject = np.zeros((128, 128), dtype=np.uint8)
    subject[30:98, 40:88] = 255

    monkeypatch.setattr(
        "dreamforge_inpaint_selection._rembg_subject_mask",
        lambda _img: (subject.copy(), "mock_rembg"),
    )

    result = generate_inpaint_selection_mask(str(image), "background")
    assert result["ok"] is True
    mask = np.array(Image.open(result["mask_path"]).convert("L"))
    assert mask[30, 40] < 128
    assert mask[0, 0] > 127


def test_invalid_selection_rejected(tmp_path: Path):
    from dreamforge_inpaint_selection import generate_inpaint_selection_mask

    image = _solid_png(tmp_path / "x.png", (10, 10, 10))
    result = generate_inpaint_selection_mask(str(image), "not_a_tool")
    assert result["ok"] is False
    assert "selection_invalid" in result["error"]


def test_bridge_command_roundtrip(tmp_path: Path, monkeypatch):
    from dreamforge_desktop_bridge import cmd_generate_inpaint_selection_mask

    image = _solid_png(tmp_path / "scene.png", (200, 200, 200))
    subject = np.zeros((128, 128), dtype=np.uint8)
    subject[20:108, 30:98] = 255
    monkeypatch.setattr(
        "dreamforge_inpaint_selection._rembg_subject_mask",
        lambda _img: (subject.copy(), "mock_rembg"),
    )

    out = cmd_generate_inpaint_selection_mask(
        {
            "image_path": str(image),
            "selection": "subject",
        }
    )
    assert out["ok"] is True
    assert Path(out["mask_path"]).is_file()
