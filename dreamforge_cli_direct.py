"""Repo-root launcher for backend/dreamforge_cli_direct.py."""
from __future__ import annotations

import importlib.util
import runpy
import sys
from pathlib import Path

_BACKEND_CLI = Path(__file__).resolve().parent / "backend" / "dreamforge_cli_direct.py"
_BACKEND_DIR = _BACKEND_CLI.parent

if __name__ == "__main__":
    sys.path.insert(0, str(_BACKEND_DIR))
    runpy.run_path(str(_BACKEND_CLI), run_name="__main__")
else:
    sys.path.insert(0, str(_BACKEND_DIR))
    _spec = importlib.util.spec_from_file_location("dreamforge_cli_direct", _BACKEND_CLI)
    if _spec is None or _spec.loader is None:
        raise ImportError(f"Cannot load backend CLI module at {_BACKEND_CLI}")
    _backend = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_backend)
    for _name, _value in _backend.__dict__.items():
        if _name.startswith("__"):
            continue
        globals()[_name] = _value
