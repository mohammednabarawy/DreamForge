import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from dreamforge_prompt.flux_llm_enhance import (  # noqa: E402
    FAMILY_PROMPT_PURPOSES,
    PURPOSE_FILES,
    _clean_llm_output,
    build_enhance_messages,
    family_prompt_profile_label,
    load_enhance_template,
    normalize_enhance_strength,
    resolve_enhance_prefs,
    resolve_flux_enhance_purpose,
    run_flux_llm_enhance,
    should_skip_llm_enhance,
)
from dreamforge_prompt.studio_enhance import studio_enhancer_for_preview  # noqa: E402


class FluxLlmEnhanceTests(unittest.TestCase):
    def test_family_prompt_purposes_cover_new_families(self):
        expected = {
            "flux2": "flux2_generate",
            "qwen": "qwen_generate",
            "qwen_image": "qwen_generate",
            "hidream": "hidream_generate",
            "hidream_o1": "hidream_generate",
            "krea2": "krea2_generate",
            "z_image": "z_image_generate",
            "hunyuan": "hunyuan_generate",
            "flux_fill": "flux_generate",
        }
        for family, purpose in expected.items():
            self.assertEqual(FAMILY_PROMPT_PURPOSES[family], purpose)

    def test_resolve_flux2_generate(self):
        self.assertEqual(resolve_flux_enhance_purpose("generate", "flux2"), "flux2_generate")

    def test_resolve_qwen_generate(self):
        self.assertEqual(resolve_flux_enhance_purpose("generate", "qwen_image"), "qwen_generate")

    def test_resolve_hidream_generate(self):
        self.assertEqual(
            resolve_flux_enhance_purpose("generate", "hidream_o1"),
            "hidream_generate",
        )

    def test_resolve_krea2_generate(self):
        self.assertEqual(resolve_flux_enhance_purpose("generate", "krea2"), "krea2_generate")

    def test_resolve_z_image_generate(self):
        self.assertEqual(resolve_flux_enhance_purpose("generate", "z_image"), "z_image_generate")

    def test_resolve_hunyuan_generate(self):
        self.assertEqual(resolve_flux_enhance_purpose("generate", "hunyuan"), "hunyuan_generate")

    def test_resolve_flux_fill_generate(self):
        self.assertEqual(resolve_flux_enhance_purpose("generate", "flux_fill"), "flux_generate")

    def test_all_purpose_templates_load_with_sections(self):
        for purpose in PURPOSE_FILES:
            system, user = load_enhance_template(purpose)
            self.assertTrue(system.strip(), f"{purpose} missing [SYSTEM]")
            self.assertTrue(user.strip(), f"{purpose} missing [USER]")

    def test_family_prompt_profile_label(self):
        self.assertEqual(family_prompt_profile_label("z_image"), "Z-Image")
        self.assertEqual(family_prompt_profile_label("krea2"), "Krea 2")
        self.assertEqual(family_prompt_profile_label("hunyuan"), "HunyuanImage")

    def test_should_not_skip_short_qwen_generate(self):
        short = "a red car in the rain"
        skip, _reason = should_skip_llm_enhance(short, "qwen_generate", enhance_strength="balanced")
        self.assertFalse(skip)

    def test_should_not_skip_short_z_image_generate(self):
        short = "portrait of a woman"
        skip, _reason = should_skip_llm_enhance(short, "z_image_generate", enhance_strength="balanced")
        self.assertFalse(skip)

    def test_should_skip_long_hidream_generate(self):
        long = " ".join(["word"] * 52) + " with warm lighting and a natural scene atmosphere"
        skip, reason = should_skip_llm_enhance(
            long, "hidream_generate", enhance_strength="balanced"
        )
        self.assertTrue(skip)
        self.assertEqual(reason, "prompt already detailed")

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
