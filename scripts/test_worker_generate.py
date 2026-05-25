"""Send a generate command to the desktop worker and print streamed events."""
from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = ROOT.parent / "python_embeded" / "python.exe"
SCRIPT = ROOT / "dreamforge_desktop_worker.py"


def main() -> int:
    proc = subprocess.Popen(
        [str(PY), "-u", "-s", str(SCRIPT)],
        cwd=str(ROOT),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    assert proc.stdin and proc.stdout

    ready = threading.Event()

    def read_stdout() -> None:
        for line in proc.stdout:
            line = line.rstrip()
            print("OUT", line[:240], flush=True)
            if '"type": "ready"' in line:
                ready.set()

    threading.Thread(target=read_stdout, daemon=True).start()

    if not ready.wait(timeout=180):
        print("TIMEOUT waiting for ready", flush=True)
        proc.kill()
        return 1

    req = {
        "cmd": "generate",
        "job_id": "test-job",
        "params": {
            "prompt": "a red cube on white background",
            "model": "flux1-schnell-fp8.safetensors",
            "vram_profile": "16gb",
            "aspect_ratio": "1024x1024",
            "styles": [],
            "performance": "Speed",
            "image_number": 1,
            "output": "outputs/test_gen.png",
            "validate_output": False,
            "json": True,
        },
    }
    line = json.dumps(req) + "\n"
    print("SENDING generate (with flush)...", flush=True)
    proc.stdin.write(line)
    proc.stdin.flush()

    events_path = ROOT.parent / "outputs" / "dreamforge" / "logs" / "worker.events"
    deadline = time.time() + 180
    while time.time() < deadline:
        if proc.poll() is not None:
            print(f"EXIT code={proc.returncode}", flush=True)
            break
        try:
            chunk = proc.stdout.readline()
        except SystemError:
            chunk = ""
        if chunk:
            print("EVT", chunk.rstrip()[:240], flush=True)
            if '"type": "finished"' in chunk:
                break
            if '"type": "error"' in chunk and "test-job" in chunk:
                break
        if events_path.is_file():
            tail = events_path.read_text(encoding="utf-8")[-4096:]
            if '"type": "finished"' in tail and "test-job" in tail:
                print("FINISHED (events file)", flush=True)
                break
        time.sleep(0.2)

    err = proc.stderr.read() if proc.stderr else ""
    if err.strip():
        print("STDERR_TAIL", err[-4000:], flush=True)

    proc.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
