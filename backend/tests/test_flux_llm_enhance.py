import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from dreamforge_prompt.flux_llm_enhance import (  # noqa: E402
    _clean_llm_output,
    build_enhance_messages,
    normalize_enhance_strength,
    resolve_enhance_prefs,
    resolve_flux_enhance_purpose,
    run_flux_llm_enhance,
    should_skip_llm_enhance,
)
from dreamforge_prompt.studio_enhance import studio_enhancer_for_preview  # noqa: E402


class FluxLlmEnhanceTests(unittest.TestCase):
    def test_resolve_flux_generate(self):
        self.assertEqual(resolve_flux_enhance_purpose("generate", "flux"), "flux_generate")

    def test_resolve_kontext_edit(self):
        self.assertEqual(
            resolve_flux_enhance_purpose("edit", "flux_kontext"),
            "flux_kontext_edit",
        )

    def test_resolve_flux_inpaint(self):
        self.assertEqual(resolve_flux_enhance_purpose("inpaint", "flux"), "flux_inpaint")

    def test_resolve_skips_ideogram(self):
        self.assertIsNone(resolve_flux_enhance_purpose("generate", "ideogram4"))

    def test_resolve_qwen_edit(self):
        self.assertEqual(
            resolve_flux_enhance_purpose("edit", "qwen_image_edit"),
            "qwen_edit",
        )

    def test_build_enhance_messages_substitutes_prompt(self):
        _system, user = build_enhance_messages("flux_generate", "a red car")
        self.assertIn("a red car", user)

    def test_should_skip_balanced_rich_prompt(self):
        rich = " ".join(["word"] * 30)
        skip, reason = should_skip_llm_enhance(
            rich, "flux_generate", enhance_strength="balanced"
        )
        self.assertTrue(skip)
        self.assertEqual(reason, "prompt already detailed")

    def test_should_skip_rich_strength_never_skips_short(self):
        short = "a red car"
        skip, _reason = should_skip_llm_enhance(short, "flux_generate", enhance_strength="rich")
        self.assertFalse(skip)

    def test_should_skip_minimal_only_for_longer_prompts(self):
        medium = " ".join(["word"] * 30)
        skip, _reason = should_skip_llm_enhance(
            medium, "flux_generate", enhance_strength="minimal"
        )
        self.assertFalse(skip)
        long = " ".join(["word"] * 42)
        skip, reason = should_skip_llm_enhance(
            long, "flux_generate", enhance_strength="minimal"
        )
        self.assertTrue(skip)
        self.assertEqual(reason, "prompt already detailed")

    def test_build_enhance_messages_applies_rich_hint(self):
        system, _user = build_enhance_messages(
            "flux_generate", "a red car", enhance_strength="rich"
        )
        self.assertIn("STRENGTH: Rich", system)

    def test_normalize_enhance_strength_fallback(self):
        self.assertEqual(normalize_enhance_strength("bogus"), "balanced")
        self.assertEqual(normalize_enhance_strength("minimal"), "minimal")

    def test_studio_enhancer_sdxl_without_flufferizer(self):
        self.assertEqual(
            studio_enhancer_for_preview("generate", "sdxl", use_flufferizer=False),
            "none",
        )

    def test_clean_llm_output_strips_quotes_and_fences(self):
        self.assertEqual(_clean_llm_output('"hello world"'), "hello world")
        self.assertEqual(_clean_llm_output("```\nhello\n```"), "hello")

    @patch("dreamforge_brain.AiBrain")
    @patch("dreamforge_prompt.ideogram4._configure_brain_from_app_config")
    def test_run_flux_llm_enhance_success(self, _cfg, brain_cls):
        brain = MagicMock()
        brain.think.return_value = "A vivid red sports car under golden hour light."
        brain_cls.return_value = brain

        result = run_flux_llm_enhance("red car", purpose="flux_generate")
        self.assertTrue(result["ok"])
        self.assertIn("red sports car", result["prompt"])
        self.assertEqual(result["enhance_source"], "brain")

    @patch("dreamforge_brain.AiBrain")
    @patch("dreamforge_prompt.ideogram4._configure_brain_from_app_config")
    def test_run_flux_llm_enhance_brain_failure(self, _cfg, brain_cls):
        brain = MagicMock()
        brain.think.side_effect = RuntimeError("offline")
        brain_cls.return_value = brain

        result = run_flux_llm_enhance("red car", purpose="flux_generate")
        self.assertFalse(result["ok"])
        self.assertIn("Brain prompt enhancement failed", result["error"])

    def test_studio_enhancer_flux_generate_uses_flux_llm(self):
        self.assertEqual(studio_enhancer_for_preview("generate", "flux"), "flux_llm")

    def test_studio_enhancer_kontext_edit_uses_flux_llm(self):
        self.assertEqual(studio_enhancer_for_preview("edit", "flux_kontext"), "flux_llm")


if __name__ == "__main__":
    unittest.main()
