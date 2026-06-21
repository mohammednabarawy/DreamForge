import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from dreamforge_comfy_workflows import _apply_user_lora_stack  # noqa: E402
from dreamforge_prompt.loras import merge_generation_loras  # noqa: E402
from dreamforge_prompt.shift_attention import shift_attention  # noqa: E402


class PromptLoraTests(unittest.TestCase):
    def test_merge_generation_loras_job_and_tags(self):
        job = SimpleNamespace(lora=["detail:0.8"])
        parsed = [{"name": "lightning.safetensors", "weight": 1.0}]
        merged = merge_generation_loras(job, parsed)
        names = {item["name"] for item in merged}
        self.assertIn("detail.safetensors", names)
        self.assertIn("lightning.safetensors", names)

    def test_shift_attention_interpolates_span(self):
        text = "hero (armor:0.2~1.0)"
        mid = shift_attention(text, 0.5)
        self.assertNotEqual(mid, text)
        self.assertNotIn("~", mid)

    def test_apply_user_lora_stack_model_only(self):
        g: dict = {}
        model_out = ["30", 0]
        clip_out = ["31", 0]
        model_out, clip_out, next_id = _apply_user_lora_stack(
            g,
            model_out,
            clip_out,
            [{"name": "test_lora.safetensors", "weight": 0.75}],
            40,
            clip_lora=False,
        )
        self.assertEqual(next_id, 41)
        self.assertIn("40", g)
        self.assertEqual(g["40"]["class_type"], "LoraLoaderModelOnly")
        self.assertEqual(g["40"]["inputs"]["strength_model"], 0.75)
        self.assertEqual(model_out, ["40", 0])
        self.assertEqual(clip_out, ["31", 0])

    def test_apply_user_lora_stack_checkpoint(self):
        g: dict = {}
        model_out, clip_out, next_id = _apply_user_lora_stack(
            g,
            ["10", 0],
            ["10", 1],
            [{"name": "style.safetensors", "weight": 1.0}],
            11,
            clip_lora=True,
        )
        self.assertEqual(next_id, 12)
        self.assertEqual(g["11"]["class_type"], "LoraLoader")
        self.assertEqual(model_out, ["11", 0])
        self.assertEqual(clip_out, ["11", 1])


if __name__ == "__main__":
    unittest.main()
