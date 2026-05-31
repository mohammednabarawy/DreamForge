import sys
import unittest
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from dreamforge_prompt_pipeline import (  # noqa: E402
    _filter_modern_styles,
    _inject_prompt_enhancer_style,
    _normalize_enhancer,
)


class PromptPipelineTests(unittest.TestCase):
    def test_normalize_enhancer(self):
        self.assertEqual(_normalize_enhancer("Style: Flufferizer"), "flufferizer")
        self.assertEqual(_normalize_enhancer(None), "none")

    def test_inject_enhancer_style(self):
        styles = _inject_prompt_enhancer_style([], "flufferizer")
        self.assertIn("Flufferizer", styles)

    def test_filter_modern_styles(self):
        styles = [
            "Style: sai-photographic",
            "Flufferizer",
            "Artify: cinema",
        ]
        kept = _filter_modern_styles(styles)
        self.assertIn("Flufferizer", kept)
        self.assertIn("Artify: cinema", kept)
        self.assertNotIn("Style: sai-photographic", kept)


if __name__ == "__main__":
    unittest.main()
