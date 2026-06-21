"""Quick boot timing test for dreamforge_generation."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dreamforge_generation import boot_headless

t0 = time.time()


def progress(evt):
    msg = evt.get("message", "")
    print(f"[{time.time() - t0:5.1f}s] {msg}", flush=True)


info = boot_headless(["--offline", "--normalvram"], progress=progress)
print(f"DONE in {time.time() - t0:.1f}s:", info, flush=True)
