"""Repo-root launcher for backend/dreamforge_cli_direct.py."""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

_BACKEND_CLI = Path(__file__).resolve().parent / "backend" / "dreamforge_cli_direct.py"
sys.path.insert(0, str(_BACKEND_CLI.parent))
runpy.run_path(str(_BACKEND_CLI), run_name="__main__")
