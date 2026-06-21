import os
import sys

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from dreamforge_prompt.ideogram4_layout import (  # noqa: E402
    caption_from_layout,
    ui_rect_to_bbox,
)


def test_ui_rect_to_bbox():
    assert ui_rect_to_bbox(0.1, 0.2, 0.3, 0.4) == [200, 100, 600, 400]


def test_caption_from_layout_minimal():
    caption = caption_from_layout(
        aspect_ratio="1:1",
        high_level_description="A red cat on a bench",
        background="sunny park",
        elements=[
            {
                "type": "obj",
                "bbox": [200, 100, 600, 400],
                "desc": "cat",
            }
        ],
    )
    assert "high_level_description" in caption
    assert "compositional_deconstruction" in caption
    assert "cat" in caption
