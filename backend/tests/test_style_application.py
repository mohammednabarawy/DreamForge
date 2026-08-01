import sys
import types


prompt_expansion = types.ModuleType("modules.prompt_expansion")
prompt_expansion.PromptExpansion = type("PromptExpansion", (), {"expand_prompt": lambda self, prompt: prompt})
prompt_expansion.Erniehancer = type("Erniehancer", (), {"execute": lambda self, prompt: prompt})
random_prompt = types.ModuleType("random_prompt")
random_prompt.build_dynamic_prompt = types.SimpleNamespace(
    one_button_superprompt=lambda prompt: prompt,
    artify_prompt=lambda prompt, artists: prompt,
)
sys.modules.setdefault("modules.prompt_expansion", prompt_expansion)
sys.modules.setdefault("random_prompt", random_prompt)

from modules import sdxl_styles


def test_fooocus_style_template_keeps_prompt_position_and_negative(monkeypatch):
    monkeypatch.setitem(sdxl_styles.styles, "Test Style", ("cinematic {prompt}, detailed", "blurry"))
    positive, negative = sdxl_styles.apply_style(["Test Style"], "a red fox", "watermark", "")
    assert "cinematic a red fox, detailed" in positive
    assert "blurry" in negative
    assert "watermark" in negative
