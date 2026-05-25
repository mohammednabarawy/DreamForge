"""Shared DreamForge backend path constants."""
from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_ROOT.parent
COMFY_ROOT = BACKEND_ROOT / "repositories" / "ComfyUI"
REPOS_ROOT = BACKEND_ROOT / "repositories"
OUTPUTS_ROOT = PROJECT_ROOT / "outputs"


def resolve_python_exe() -> Path:
    """Embedded Python, then venv, then current interpreter."""
    if os.name == "nt":
        candidates = (
            PROJECT_ROOT / "python_embeded" / "python.exe",
            PROJECT_ROOT / "venv" / "Scripts" / "python.exe",
        )
    else:
        candidates = (
            Path("/opt/anaconda3/envs/dreamforge/bin/python"),
            PROJECT_ROOT / "venv" / "bin" / "python",
        )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return Path(sys.executable)


PYTHON_EXE = resolve_python_exe()


def extend_sys_path() -> None:
    for path in (str(BACKEND_ROOT), str(COMFY_ROOT), str(REPOS_ROOT)):
        if path not in sys.path:
            sys.path.insert(0, path)
