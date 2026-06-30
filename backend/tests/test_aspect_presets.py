import os
import sys

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__)))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from dreamforge_aspect_presets import (  # noqa: E402
    list_aspect_ratio_presets,
    normalize_aspect_preset,
)


def test_list_aspect_ratio_presets_includes_resolutions_and_hidream(monkeypatch):
    class MockResolutionSettings:
        def __init__(self):
            self.aspect_ratios = {"1:1": (1024, 1024)}

    import sys
    from types import ModuleType
    mock_modules = ModuleType("modules")
    mock_resolutions = ModuleType("modules.resolutions")
    mock_resolutions.ResolutionSettings = MockResolutionSettings
    sys.modules["modules"] = mock_modules
    sys.modules["modules.resolutions"] = mock_resolutions

    presets = list_aspect_ratio_presets()
    assert "1024x1024" in presets
    assert "1536x1536" in presets
    assert "2048x2048" in presets
    assert "1728x2304" in presets
    assert len(presets) >= 15


def test_normalize_aspect_preset_strips_label():
    assert normalize_aspect_preset("1344×768 (16:9 Large)") == "1344x768"
    assert normalize_aspect_preset("2048x2048") == "2048x2048"
