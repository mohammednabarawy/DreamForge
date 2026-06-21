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
from dreamforge_prompt.pipeline import (  # noqa: E402
    _qwen_edit_negative_guard,
    _qwen_edit_needs_quality_pass,
    _qwen_edit_prompt_guard,
    _qwen_edit_scene_change_requested,
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


    def test_qwen_edit_needs_quality_pass_for_global_editorial(self):
        prompt = (
            "cinematic editorial portrait in dark moody studio with smoke, "
            "slate luxury suit, hands in pockets"
        )
        self.assertTrue(_qwen_edit_needs_quality_pass(prompt))
        self.assertTrue(_qwen_edit_scene_change_requested(prompt))
        self.assertFalse(_qwen_edit_needs_quality_pass("change shirt to red"))



if __name__ == "__main__":
    unittest.main()
