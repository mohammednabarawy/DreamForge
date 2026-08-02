"""Deterministic hardware policy benchmark (no image generation by default).

This is deliberately a policy harness: it validates every supported hardware
bucket without pretending a fixture run is a real GPU benchmark. Use
``--run-generation`` only on the host being measured.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import os
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from dreamforge_vram_profiles import hardware_class


@dataclass(frozen=True)
class HardwareFixture:
    name: str
    vendor: str
    backend: str
    vram_gb: float
    os_name: str = "Windows"
    mps: bool = False


FIXTURES = (
    HardwareFixture("cpu_only", "CPU", "cpu", 0),
    HardwareFixture("nvidia_4_6gb", "NVIDIA", "cuda", 6),
    HardwareFixture("nvidia_8gb", "NVIDIA", "cuda", 8),
    HardwareFixture("nvidia_12gb", "NVIDIA", "cuda", 12),
    HardwareFixture("nvidia_16gb", "NVIDIA", "cuda", 16),
    HardwareFixture("nvidia_24gb_plus", "NVIDIA", "cuda", 24),
    HardwareFixture("nvidia_32gb_plus", "NVIDIA", "cuda", 32),
    HardwareFixture("amd_4_8gb", "AMD", "rocm", 6),
    HardwareFixture("amd_8_12gb", "AMD", "rocm", 12),
    HardwareFixture("amd_16gb_plus", "AMD", "rocm", 16),
    HardwareFixture("amd_rocm_linux_16gb_plus", "AMD", "rocm", 16, "Linux"),
    HardwareFixture("apple_silicon_8gb", "Apple", "mps", 8, "Darwin", True),
    HardwareFixture("apple_silicon_16gb", "Apple", "mps", 16, "Darwin", True),
    HardwareFixture("apple_silicon_24gb_plus", "Apple", "mps", 24, "Darwin", True),
    HardwareFixture("apple_silicon_32gb_plus", "Apple", "mps", 32, "Darwin", True),
)


def snapshot(fixture: HardwareFixture) -> dict:
    started = time.perf_counter()
    if fixture.vram_gb >= 30: profile = "32gb"
    elif fixture.vram_gb >= 22: profile = "24gb"
    elif fixture.vram_gb >= 14: profile = "16gb"
    elif fixture.vram_gb >= 10.5: profile = "12gb"
    elif fixture.vram_gb >= 7: profile = "8gb"
    elif fixture.vram_gb: profile = "5gb"
    else: profile = "no_gpu"
    if fixture.mps:
        profile = f"mps_{profile}"
    return {
        "fixture": fixture.name,
        "hardware_class": hardware_class(
            vendor=fixture.vendor, backend=fixture.backend,
            vram_gb=fixture.vram_gb, os_name=fixture.os_name, mps=fixture.mps,
        ),
        "backend": fixture.backend,
        "profile": profile,
        "launch_policy_ms": round((time.perf_counter() - started) * 1000, 3),
        "generation_executed": False,
    }


def run_policy_benchmark() -> list[dict]:
    return [snapshot(fixture) for fixture in FIXTURES]


def _benchmark_model(explicit: str | None = None) -> str | None:
    from dreamforge_cli_inventory import list_model_inventory, recommended_generation_models

    if explicit:
        return explicit
    inventory = list_model_inventory()
    candidates = inventory.get("categories", {}).get("checkpoints", [])
    if not candidates:
        candidates = [item for category in ("diffusion_models", "unet") for item in inventory.get("categories", {}).get(category, [])]
    if not candidates:
        return None
    preferred = next((item for item in candidates if "dreamshaper" in str(item.get("name", "")).lower()), candidates[0])
    return str(preferred.get("name") or preferred.get("filename"))


def _p95(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)]


def _sample_peak_memory(stop: threading.Event, peaks: dict[str, int]) -> None:
    from dreamforge_gpu_detect import detect_gpu

    while not stop.is_set():
        gpu = detect_gpu()
        total = int(gpu.get("vram_mb") or 0)
        free = gpu.get("free_vram_mb")
        if free is not None:
            peaks["vram_mb"] = max(peaks["vram_mb"], total - int(free))
        try:
            import psutil

            memory = psutil.virtual_memory()
            peaks["ram_mb"] = max(
                peaks["ram_mb"],
                int(memory.total - memory.available) // (1024 * 1024),
            )
        except Exception:
            pass
        stop.wait(0.1)


def run_generation_benchmark(*, model: str | None = None, runs: int = 5, steps: int = 4, width: int = 512, height: int = 512) -> dict:
    """Run one warm-up plus measured generations on the detected host."""
    from dreamforge_generation import run_generation
    from dreamforge_comfy_launch import comfy_launch_extra_args
    from dreamforge_gpu_detect import detect_gpu

    model_name = _benchmark_model(model)
    if not model_name:
        return {"generation_executed": False, "error": "no_installed_generation_model"}
    runs = max(1, min(int(runs), 20))
    args = SimpleNamespace(
        model=model_name, prompt="a studio portrait, high quality", negative_prompt="",
        width=width, height=height, aspect_ratio=f"{width}x{height}", steps=steps,
        cfg_scale=5.0, sampler="euler", scheduler="normal", seed=424242,
        vram_profile="auto", performance="Custom...", style="none", styles=[],
        batch_size=1, output_dir=None, output=None, edit_type="txt2img",
    )
    samples: list[dict] = []
    peaks = {"vram_mb": 0, "ram_mb": 0}

    def run_once(label: str) -> dict:
        telemetry: list[dict] = []
        stop_sampling = threading.Event()
        sampler = threading.Thread(
            target=_sample_peak_memory,
            args=(stop_sampling, peaks),
            daemon=True,
        )
        started = time.perf_counter()
        sampler.start()
        try:
            result = run_generation(args, {"model": model_name, "prompt": args.prompt, "width": width, "height": height, "steps": steps, "seed": args.seed}, stream_sink=telemetry.append, job_id=f"hardware-benchmark-{label}")
        except Exception as exc:
            result = {"status": "error", "error": str(exc)}
        finally:
            stop_sampling.set()
            sampler.join(timeout=1.0)
        elapsed = time.perf_counter() - started
        paths = []
        for item in result.get("images", []) if isinstance(result, dict) else []:
            path = item.get("path") if isinstance(item, dict) else item
            if path:
                paths.append(str(path))
        valid = []
        for path in paths:
            try:
                with Image.open(path) as image:
                    valid.append(image.size == (width, height) and image.getbbox() is not None)
            except (OSError, ValueError):
                valid.append(False)
        return {"label": label, "elapsed_s": round(elapsed, 4), "status": result.get("status") if isinstance(result, dict) else "error", "output_valid": bool(paths) and all(valid), "outputs": paths, "events": len(telemetry)}

    warmup = run_once("warmup")
    if warmup.get("status") != "success":
        return {"generation_executed": True, "model": model_name, "hardware": detect_gpu(), "warmup": warmup, "runs": [], "error": "warmup_failed"}
    for index in range(runs):
        samples.append(run_once(str(index + 1)))
    elapsed = [float(item["elapsed_s"]) for item in samples]
    return {
        "generation_executed": True, "model": model_name, "hardware": detect_gpu(),
        "warmup": warmup, "runs": samples, "policy_args": list(comfy_launch_extra_args()), "peak_vram_mb": peaks["vram_mb"], "peak_ram_mb": peaks["ram_mb"],
        "summary": {"count": len(elapsed), "median_s": round(statistics.median(elapsed), 4), "p95_s": round(_p95(elapsed), 4), "all_outputs_valid": all(item["output_valid"] for item in samples)},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", help="write JSON results to a file")
    parser.add_argument("--run-generation", action="store_true", help="run one warm-up and measured generations on this host")
    parser.add_argument("--model")
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--steps", type=int, default=4)
    parser.add_argument("--width", type=int, default=512)
    parser.add_argument("--height", type=int, default=512)
    args = parser.parse_args()
    if args.run_generation and os.environ.get("DREAMFORGE_BENCHMARK_REEXEC") != "1":
        try:
            from _paths import PYTHON_EXE

            if PYTHON_EXE.is_file() and Path(sys.executable).resolve() != PYTHON_EXE.resolve():
                env = dict(os.environ)
                env["DREAMFORGE_BENCHMARK_REEXEC"] = "1"
                completed = subprocess.run([str(PYTHON_EXE), "-m", "dreamforge_hardware_benchmark", *sys.argv[1:]], cwd=str(Path(__file__).resolve().parent), env=env, text=True, capture_output=True)
                if completed.stdout:
                    print(completed.stdout, end="")
                if completed.stderr:
                    print(completed.stderr, end="", file=sys.stderr)
                raise SystemExit(completed.returncode)
        except (ImportError, OSError):
            pass
    results = run_policy_benchmark()
    if args.run_generation:
        payload_data = {"results": results, "generation": run_generation_benchmark(model=args.model, runs=args.runs, steps=args.steps, width=args.width, height=args.height)}
    else:
        payload_data = {"results": results}
    payload = json.dumps(payload_data, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(payload + "\n")
    print(payload)


if __name__ == "__main__":
    main()
