"""Run CLI inventory smoke tests from the DreamForge project root."""

import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
runpy.run_path(str(ROOT / "engine" / "tests" / "test_cli_inventory.py"), run_name="__main__")
