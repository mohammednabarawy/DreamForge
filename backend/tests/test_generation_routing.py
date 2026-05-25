"""Unit tests for input-image routing rules (no GPU)."""

from __future__ import annotations

import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


def _route_input(
    *,
    input_path: str | None,
    cn_selection: str = "None",
    cn_type: str = "None",
    edit_type: str = "auto",
    model_family: str = "",
    upscale_image: str | None = None,
) -> tuple[str, str, str]:
    """Mirror dreamforge_generation.py routing without loading the engine."""
    cn_sel = cn_selection
    cn_t = cn_type
    ed = edit_type

    if not input_path:
        if cn_sel == "Custom...":
            cn_sel = "None"
            cn_t = "None"
        if ed in ("kontext", "inpaint", "img2img", "qwen_edit"):
            ed = "auto"
    elif cn_sel == "None" and upscale_image:
        cn_sel = "Custom..."
        cn_t = "upscale"
    elif cn_sel == "None" and input_path:
        if ed == "kontext" or model_family == "flux_kontext":
            cn_sel = "None"
            cn_t = "None"
        else:
            cn_sel = "Custom..."
            cn_t = ed if ed not in ("auto", "None", None, "") else "img2img"
    elif input_path and cn_sel == "Custom...":
        if upscale_image:
            cn_t = "upscale"
        elif ed == "kontext" or model_family == "flux_kontext":
            cn_sel = "None"
            cn_t = "None"
        elif ed not in ("auto", "None", None, ""):
            cn_t = ed

    return cn_sel, cn_t, ed


def test_txt2img_clears_custom_cn():
    sel, typ, ed = _route_input(input_path=None)
    assert sel == "None"
    assert typ == "None"
    assert ed == "auto"


def test_reference_enables_img2img():
    sel, typ, _ = _route_input(input_path="/tmp/a.png", cn_selection="None")
    assert sel == "Custom..."
    assert typ == "img2img"


def test_flux_kontext_keeps_cn_none():
    sel, typ, _ = _route_input(
        input_path="/tmp/a.png",
        edit_type="kontext",
        model_family="flux_kontext",
    )
    assert sel == "None"
    assert typ == "None"
