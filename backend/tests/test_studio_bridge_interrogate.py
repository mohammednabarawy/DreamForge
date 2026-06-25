"""Tests for describe / interrogate bridge command."""
from __future__ import annotations

import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


def test_cmd_interrogate_image_returns_caption(monkeypatch, tmp_path):
    import types

    from PIL import Image

    import dreamforge_studio_bridge as bridge

    img = tmp_path / "photo.png"
    Image.new("RGB", (16, 16), color=(200, 40, 40)).save(img)

    monkeypatch.setattr(
        "dreamforge_paths.resolve_image_path_or_raise",
        lambda _path: img,
    )
    monkeypatch.setattr("dreamforge_generation.boot_headless", lambda: None)

    def fake_look(_image, _hint, _gr):
        return "a studio portrait of a red cube"

    monkeypatch.setitem(
        sys.modules,
        "modules.interrogate",
        types.SimpleNamespace(look=fake_look),
    )

    result = bridge.cmd_interrogate_image({"path": str(img)})

    assert result["ok"] is True
    assert result["prompt"] == "a studio portrait of a red cube"


def test_cmd_interrogate_image_does_not_echo_input_prompt(monkeypatch, tmp_path):
    import types

    from PIL import Image

    import dreamforge_studio_bridge as bridge

    img = tmp_path / "photo.png"
    Image.new("RGB", (16, 16), color=(10, 10, 10)).save(img)

    monkeypatch.setattr(
        "dreamforge_paths.resolve_image_path_or_raise",
        lambda _path: img,
    )
    monkeypatch.setattr("dreamforge_generation.boot_headless", lambda: None)
    monkeypatch.setitem(
        sys.modules,
        "modules.interrogate",
        types.SimpleNamespace(
            look=lambda _image, _hint, _gr: "generated caption from vision model",
        ),
    )

    result = bridge.cmd_interrogate_image(
        {"path": str(img), "prompt": "existing user prompt text"},
    )

    assert result["ok"] is True
    assert result["prompt"] == "generated caption from vision model"
