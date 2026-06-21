import os
import sys

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from dreamforge_prompt.ideogram4 import ideogram4_scheduler_params  # noqa: E402
from dreamforge_prompt.ideogram4_templates import (  # noqa: E402
    list_ideogram4_caption_templates,
    render_ideogram4_caption_template,
)


def test_list_ideogram4_caption_templates():
    templates = list_ideogram4_caption_templates()
    assert len(templates) >= 3
    assert any(t["id"] == "product_hero" for t in templates)


def test_render_ideogram4_caption_template():
    out = render_ideogram4_caption_template("transparent_cutout")
    assert out["ok"] is True
    assert "transparent background" in (out.get("caption") or "")


def test_ideogram4_scheduler_advanced_overrides():
    sched = ideogram4_scheduler_params(
        {
            "ideogram4_mode": "default",
            "ideogram4_mu_override": 0.25,
            "ideogram4_std_override": 1.5,
            "ideogram4_steps_override": 24,
            "ideogram4_dual_cfg_override": 6.5,
        },
        width=1024,
        height=1024,
        vram_tier="16gb",
    )
    assert sched["mu"] == 0.25
    assert sched["std"] == 1.5
    assert sched["steps"] == 24
    assert sched["dual_cfg"] == 6.5
