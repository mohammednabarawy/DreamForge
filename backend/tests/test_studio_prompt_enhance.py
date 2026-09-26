import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from dreamforge_prompt.pipeline import (  # noqa: E402
    _inpaint_boost,
    _kontext_edit_boost,
    _modern_generate_boost,
    _upscale_boost,
)
from dreamforge_prompt.studio_enhance import (  # noqa: E402
    _check_qwen21_rewrite,
    enhance_studio_prompt,
    studio_enhancer_for_preview,
)


class StudioPromptEnhanceTests(unittest.TestCase):
    def test_qwen21_rewrite_keeps_references_text_and_alpha(self):
        original = 'Make people from image 1 and image 2 together, sign reads "HELLO", transparent PNG'
        rewritten, error = _check_qwen21_rewrite(
            original, 'The people from <image1> and <image2> stand beside a sign reading "HELLO".', 2
        )
        self.assertFalse(error)
        self.assertIn("<image1>", rewritten)
        self.assertIn("<image2>", rewritten)
        self.assertIn("RGBA image with transparency", rewritten)
        self.assertIn("alpha channel", rewritten)
        _, error = _check_qwen21_rewrite(original, 'One person beside a sign reading "HELLO".', 2)
        self.assertIn("<image1>", error)

    @patch("dreamforge_prompt.flux_llm_enhance.run_flux_llm_enhance")
    @patch("dreamforge_cli_direct._compile_job")
    def test_qwen21_enhance_routes_create_and_edit(self, compile_job, brain):
        model = {"family": "qwen_image_2.1"}
        brain.return_value = {"ok": True, "prompt": "Put <image1> and <image2> together."}
        for mode in ("generate", "edit"):
            job = SimpleNamespace(model="qwen_image_2.1.safetensors", references=[
                {"path": "first.png", "role": "image_prompt"},
                {"path": "second.png", "role": "image_prompt"},
            ])
            compile_job.return_value = (job, model, "Put image 1 and image 2 together", "", 1024, 1024, None)
            result = enhance_studio_prompt({"prompt": "Put image 1 and image 2 together", "studio_mode": mode})
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["prompt"], "Put <image1> and <image2> together.")
            self.assertEqual(brain.call_args.kwargs["purpose"], "qwen_generate" if mode == "generate" else "qwen_edit")
            self.assertIn("<image2>", brain.call_args.kwargs["context"])

    def test_studio_enhancer_flux2_uses_flux_llm(self):
        self.assertEqual(studio_enhancer_for_preview("generate", "flux2"), "flux_llm")

    def test_studio_enhancer_krea2_uses_flux_llm(self):
        self.assertEqual(studio_enhancer_for_preview("generate", "krea2"), "flux_llm")

    def test_studio_enhancer_z_image_uses_flux_llm(self):
        self.assertEqual(studio_enhancer_for_preview("generate", "z_image"), "flux_llm")

    def test_studio_enhancer_hunyuan_uses_flux_llm(self):
        self.assertEqual(studio_enhancer_for_preview("generate", "hunyuan"), "flux_llm")

    def test_studio_enhancer_ideogram4_uses_none(self):
        self.assertEqual(studio_enhancer_for_preview("generate", "ideogram4"), "none")

    def test_studio_enhancer_sdxl_generate_uses_flufferizer(self):
        self.assertEqual(studio_enhancer_for_preview("generate", "sdxl"), "flufferizer")

    def test_studio_enhancer_sdxl_respects_flufferizer_toggle(self):
        self.assertEqual(
            studio_enhancer_for_preview("generate", "sdxl", use_flufferizer=False),
            "none",
        )

    def test_studio_enhancer_flux_generate_uses_flux_llm(self):
        self.assertEqual(studio_enhancer_for_preview("generate", "flux"), "flux_llm")

    def test_studio_enhancer_flux_inpaint_uses_flux_llm(self):
        self.assertEqual(studio_enhancer_for_preview("inpaint", "flux"), "flux_llm")

    def test_studio_enhancer_kontext_edit_uses_flux_llm(self):
        self.assertEqual(studio_enhancer_for_preview("edit", "flux_kontext"), "flux_llm")

    def test_studio_enhancer_qwen_edit_uses_flux_llm(self):
        self.assertEqual(studio_enhancer_for_preview("edit", "qwen_image_edit"), "flux_llm")

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
