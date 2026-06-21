import os
import sys

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

os.environ["DREAMFORGE_SKIP_RUNTIME_PATHS"] = "1"

from dreamforge_bootstrap import _normalize_setup_state  # noqa: E402
from dreamforge_bootstrap_markers import (  # noqa: E402
    bootstrap_recipe_fingerprint,
    node_deps_marker_token,
    python_stack_marker_token,
)


def test_bootstrap_recipe_fingerprint_stable():
    assert len(bootstrap_recipe_fingerprint()) == 16


def test_normalize_setup_state_clears_recipe_bound_steps():
    state = {
        "completed_steps": ["prepare_directories", "install_comfyui", "verify_engine"],
        "recipe_fingerprint": "stale-fingerprint",
    }
    normalized = _normalize_setup_state(state)
    assert "prepare_directories" in normalized["completed_steps"]
    assert "install_comfyui" not in normalized["completed_steps"]
    assert normalized["recipe_fingerprint"] == bootstrap_recipe_fingerprint()


def test_node_deps_marker_token_includes_version(tmp_path):
    pack = tmp_path / "pack"
    pack.mkdir()
    (pack / "requirements.txt").write_text("torch\n", encoding="utf-8")
    token = node_deps_marker_token(pack, "abc123")
    assert "abc123" in token
    assert token.startswith("v")


def test_python_stack_marker_token():
    token = python_stack_marker_token()
    assert token.startswith("v")
