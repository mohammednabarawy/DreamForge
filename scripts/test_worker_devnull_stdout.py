"""Worker generate test with stdout=DEVNULL (events file only)."""
from __future__ import annotations

import json
import subprocess
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = ROOT.parent / "python_embeded" / "python.exe"
EVENTS = ROOT.parent / "outputs" / "dreamforge" / "logs" / "worker.events"


def main() -> int:
    proc = subprocess.Popen(
        [str(PY), "-u", "-s", str(ROOT / "dreamforge_desktop_worker.py")],
        cwd=str(ROOT),
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert proc.stdin and proc.stderr
    ready = threading.Event()

    def wait_ready() -> None:
        deadline = time.time() + 180
        while time.time() < deadline:
            if EVENTS.is_file() and '"type": "ready"' in EVENTS.read_text(encoding="utf-8"):
                ready.set()
                return
            time.sleep(0.5)

    def drain_stderr() -> None:
        for line in proc.stderr:
            print("LOG", line.rstrip()[:200], flush=True)

    threading.Thread(target=drain_stderr, daemon=True).start()
    threading.Thread(target=wait_ready, daemon=True).start()
    if not ready.wait(180):
        print("BOOT TIMEOUT", flush=True)
        proc.kill()
        return 1

    req = {
        "cmd": "generate",
        "job_id": "devnull-job",
        "params": {
            "prompt": "a red cube on white background",
            "model": "flux1-schnell-fp8.safetensors",
            "vram_profile": "16gb",
            "aspect_ratio": "1024x1024",
            "styles": ["Style: sai-enhance"],
            "performance": "Speed",
            "use_case": "product_ad",
            "image_number": 1,
            "output": "outputs/test_devnull.png",
            "validate_output": False,
            "json": True,
        },
    }
    proc.stdin.write(json.dumps(req) + "\n")
    proc.stdin.flush()
    print("SENT generate", flush=True)

    deadline = time.time() + 180
    while time.time() < deadline:
        if proc.poll() is not None:
            print(f"EXIT {proc.returncode}", flush=True)
            return 1 if proc.returncode else 0
        if EVENTS.is_file():
            tail = EVENTS.read_text(encoding="utf-8")[-12000:]
            if '"type": "finished"' in tail and "devnull-job" in tail:
                print("FINISHED OK", flush=True)
                return 0
        time.sleep(0.5)

    print("GEN TIMEOUT", flush=True)
    proc.kill()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
