from __future__ import annotations

import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from dreamforge_paths import resolve_image_path


def test_resolve_image_path_none_or_blank():
    assert resolve_image_path(None) is None
    assert resolve_image_path("") is None
    assert resolve_image_path("   ") is None
