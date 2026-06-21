"""Versioned markers for resumable bootstrap installs."""

from __future__ import annotations

import hashlib
from pathlib import Path

from dreamforge_krita_recipes import COMFY_INSTALL_RECIPE

BACKEND_ROOT = Path(__file__).resolve().parent

# Bump when ComfyUI pin, custom nodes, or bootstrap steps change materially.
SETUP_RECIPE_VERSION = 1

PYTHON_STACK_MARKER = BACKEND_ROOT / ".dreamforge_python_stack_ok"
COMFY_DEPS_MARKER = BACKEND_ROOT / ".dreamforge_comfy_deps_ok"
COMFY_PIN_FILE = BACKEND_ROOT / ".dreamforge_comfy_pin"


def file_fingerprint(path: Path) -> str:
    if not path.is_file():
        return "missing"
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()[:16]


def bootstrap_recipe_fingerprint() -> str:
    parts = [
        str(SETUP_RECIPE_VERSION),
        str(COMFY_INSTALL_RECIPE.get("comfy_version") or ""),
    ]
    for entry in COMFY_INSTALL_RECIPE.get("required_custom_nodes") or []:
        parts.append(f"{entry.get('id')}:{entry.get('version') or ''}")
    return hashlib.sha256(":".join(parts).encode("utf-8")).hexdigest()[:16]


def python_stack_marker_token() -> str:
    req = BACKEND_ROOT / "requirements_versions.txt"
    return f"v{SETUP_RECIPE_VERSION}:{file_fingerprint(req)}"


def python_stack_marker_valid() -> bool:
    if not PYTHON_STACK_MARKER.is_file():
        return False
    text = PYTHON_STACK_MARKER.read_text(encoding="utf-8").strip()
    return text == f"ok:{python_stack_marker_token()}"


def write_python_stack_marker() -> None:
    PYTHON_STACK_MARKER.write_text(f"ok:{python_stack_marker_token()}\n", encoding="utf-8")


def comfy_deps_marker_token(comfy_dir: Path) -> str:
    req = comfy_dir / "requirements.txt"
    return (
        f"v{SETUP_RECIPE_VERSION}:"
        f"{comfy_dir.resolve()}:"
        f"{file_fingerprint(req)}"
    )


def comfy_deps_marker_valid(comfy_dir: Path) -> bool:
    if not COMFY_DEPS_MARKER.is_file():
        return False
    try:
        recorded = COMFY_DEPS_MARKER.read_text(encoding="utf-8").strip()
    except OSError:
        return False
    return recorded == comfy_deps_marker_token(comfy_dir)


def write_comfy_deps_marker(comfy_dir: Path) -> None:
    COMFY_DEPS_MARKER.write_text(f"{comfy_deps_marker_token(comfy_dir)}\n", encoding="utf-8")


def node_deps_marker_path(pack_dir: Path) -> Path:
    return pack_dir / ".dreamforge_deps_ok"


def node_deps_marker_token(pack_dir: Path, version: str) -> str:
    req = pack_dir / "requirements.txt"
    req_fp = file_fingerprint(req) if req.is_file() else "none"
    return f"v{SETUP_RECIPE_VERSION}:{version}:{req_fp}"


def node_deps_marker_valid(pack_dir: Path, version: str) -> bool:
    marker = node_deps_marker_path(pack_dir)
    if not marker.is_file():
        return False
    try:
        return marker.read_text(encoding="utf-8").strip() == node_deps_marker_token(pack_dir, version)
    except OSError:
        return False


def write_node_deps_marker(pack_dir: Path, version: str) -> None:
    node_deps_marker_path(pack_dir).write_text(
        f"{node_deps_marker_token(pack_dir, version)}\n",
        encoding="utf-8",
    )


def clear_install_markers() -> list[str]:
    """Remove bootstrap skip markers so repair re-runs pip/checkout steps."""
    cleared: list[str] = []
    for path in (PYTHON_STACK_MARKER, COMFY_DEPS_MARKER):
        if path.is_file():
            path.unlink(missing_ok=True)
            cleared.append(path.name)
    return cleared


# Steps invalidated when the recipe fingerprint changes.
RECIPE_BOUND_STEPS: frozenset[str] = frozenset(
    {
        "install_dreamforge_stack",
        "install_comfyui",
        "install_comfy_deps",
        "install_custom_nodes",
        "configure_comfy_models",
        "verify_engine",
    }
)
