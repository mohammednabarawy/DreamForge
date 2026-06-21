import sys
import unittest
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from dreamforge_prompt.pipeline import (  # noqa: E402
    _inpaint_boost,
    _kontext_edit_boost,
    _modern_generate_boost,
    _upscale_boost,
)
from dreamforge_prompt.studio_enhance import studio_enhancer_for_preview  # noqa: E402


class StudioPromptEnhanceTests(unittest.TestCase):
    def test_studio_enhancer_sdxl_generate_uses_flufferizer(self):
        self.assertEqual(studio_enhancer_for_preview("generate", "sdxl"), "flufferizer")

    def test_studio_enhancer_flux_generate_skips_flufferizer(self):
        self.assertEqual(studio_enhancer_for_preview("generate", "flux"), "none")

    def test_studio_enhancer_qwen_edit_skips_flufferizer(self):
        self.assertEqual(studio_enhancer_for_preview("edit", "qwen_image_edit"), "none")

    def test_modern_generate_boost_adds_quality_clause(self):
        boosted = _modern_generate_boost("flux", "a red sports car")
        self.assertIn("Cinematic lighting", boosted)
        self.assertIn("red sports car", boosted)

    def test_kontext_edit_boost_adds_preservation(self):
        job = type("Job", (), {"input_image": "x.png", "edit_type": "kontext"})()
        boosted = _kontext_edit_boost(job, "flux_kontext", "make the jacket blue")
        self.assertIn("Preserve the subject identity", boosted)

    def test_inpaint_boost_wraps_masked_region(self):
        job = type("Job", (), {"inpaint_mask_path": "mask.png"})()
        boosted = _inpaint_boost(job, "inpaint", "add flowers")
        self.assertIn("masked region", boosted.lower())
        self.assertIn("add flowers", boosted)

    def test_upscale_empty_prompt_gets_restoration_wording(self):
        boosted = _upscale_boost("upscale", "")
        self.assertIn("detail", boosted.lower())


if __name__ == "__main__":
    unittest.main()
