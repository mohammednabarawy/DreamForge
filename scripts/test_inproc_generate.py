"""Run run_generation in-process after boot (same as worker, no pipes)."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dreamforge_generation import boot_headless, run_generation

events: list[dict] = []


def sink(evt: dict) -> None:
    events.append(evt)
    print(json.dumps(evt, ensure_ascii=False)[:240], flush=True)


def main() -> int:
    print("BOOT...", flush=True)
    boot_headless(["--offline", "--normalvram"], progress=lambda e: print(json.dumps(e)[:120], flush=True))
    base = SimpleNamespace(
        prompt="red cube on white",
        model="flux1-schnell-fp8.safetensors",
        vram_profile="16gb",
        aspect_ratio="1024x1024",
        styles=[],
        performance="Speed",
        image_number=1,
        output="outputs/test_inproc.png",
        validate_output=False,
        json=True,
    )
    print("GENERATE...", flush=True)
    t0 = time.time()
    result = run_generation(base, stream_sink=sink, job_id="inproc")
    print("DONE", time.time() - t0, result.get("status"), flush=True)
    return 0 if result.get("status") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
