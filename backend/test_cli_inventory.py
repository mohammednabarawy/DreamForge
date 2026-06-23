"""Run CLI inventory smoke tests from the DreamForge backend directory."""

import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

if __name__ == "__main__":
    runpy.run_path(str(ROOT / "tests" / "test_cli_inventory.py"), run_name="__main__")
