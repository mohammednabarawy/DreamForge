"""Deterministic hardware policy benchmark (no image generation by default).

This is deliberately a policy harness: it validates every supported hardware
bucket without pretending a fixture run is a real GPU benchmark. Use
``--run-generation`` only on the host being measured.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import platform
import tempfile
from functools import lru_cache
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


def run_generation_benchmark(*, model: str | None = None, runs: int = 5, steps: int = 4, width: int = 512, height: int = 512, compare_attention: bool = False, attention_backend: str | None = None, input_image: str | None = None) -> dict:
    """Run one warm-up plus measured generations on the detected host."""
    from dreamforge_generation import run_generation
    from dreamforge_comfy_launch import comfy_launch_extra_args
    from dreamforge_gpu_detect import detect_gpu

    if compare_attention:
        return run_attention_benchmark(model=model, runs=runs, steps=steps, width=width,
                                       height=height, input_image=input_image)
    model_name = _benchmark_model(model)
    if not model_name:
        return {"generation_executed": False, "error": "no_installed_generation_model"}
    runs = max(1, min(int(runs), 20))
    args = SimpleNamespace(
        model=model_name, prompt="a studio portrait, high quality", negative_prompt="",
        width=width, height=height, aspect_ratio=f"{width}x{height}", steps=steps,
        cfg_scale=5.0, sampler="euler", scheduler="normal", seed=424242,
        vram_profile="auto", performance="Custom...", style="none", styles=[],
        prompt_enhancer="none", use_comfy_server=True, user_picked_model=True,
        batch_size=1, output_dir=None, output=None, edit_type="auto" if input_image else "txt2img",
        input_image=input_image, workflow_mode="edit" if input_image else "generate",
        studio_mode="edit" if input_image else "generate", _benchmark_attention=attention_backend,
    )
    samples: list[dict] = []
    peaks = {"vram_mb": 0, "ram_mb": 0}

    def run_once(label: str) -> dict:
        # Distinct seeds force actual sampling; both backends use the same sequence.
        args.seed = 424242 + (int(label) if label.isdigit() else 0)
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
            result = run_generation(args, {"model": model_name, "prompt": args.prompt, "width": width, "height": height, "steps": steps, "seed": args.seed}, stream_sink=telemetry.append, job_id=f"hardware-benchmark-{attention_backend or 'auto'}-{time.time_ns()}-{label}")
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
        actual_attention = result.get("settings", {}).get("attention_backend") if isinstance(result, dict) else None
        valid_backend = attention_backend is None or actual_attention == attention_backend
        return {"label": label, "elapsed_s": round(elapsed, 4), "status": result.get("status") if isinstance(result, dict) else "error",
                "output_valid": bool(paths) and all(valid) and valid_backend, "outputs": paths,
                "attention_backend": actual_attention, "seed": args.seed, "events": len(telemetry),
                "error": (result.get("message") or result.get("error")) if result.get("status") != "success" else None}

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



def _attention_cache_path() -> Path:
    from dreamforge_runtime_paths import build_runtime_layout
    return build_runtime_layout().runtime_dir / "attention-benchmarks.json"



@lru_cache(maxsize=1)
def _attention_driver_version() -> str:
    try:
        result = subprocess.run(["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
                                capture_output=True, text=True, timeout=5,
                                **({"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}))
        return result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"

def _attention_key(model: dict, mode: str, width: int, height: int) -> str:
    import torch
    from _paths import COMFY_ROOT
    from dreamforge_preflight import _resolve_model_path
    index = int(os.environ.get("DREAMFORGE_COMFY_DEVICE_INDEX") or 0)
    props = torch.cuda.get_device_properties(index)
    path = _resolve_model_path(model)
    if path is None:
        raise ValueError("Benchmark model file is missing")
    packages = {name: importlib.metadata.version(name) for name in ("torch", "comfy-kitchen", "comfy-aimdo")}
    core = Path(COMFY_ROOT)
    files = {name: (core / name).stat().st_mtime_ns for name in (
        "main.py", "requirements.txt", "comfy/ldm/modules/attention.py",
    )}
    payload = [platform.platform(), platform.python_version(), index, props.name,
               str(getattr(props, "uuid", "")), props.total_memory, torch.version.cuda, _attention_driver_version(),
               packages, files, str(path.resolve()), path.stat().st_size, path.stat().st_mtime_ns,
               mode, int(width), int(height),
               {name: os.environ.get(name) for name in (
                   "DREAMFORGE_DISABLE_DYNAMIC_VRAM", "DREAMFORGE_COMFY_FAST",
               )}]
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def measured_attention_backend(model: dict, mode: str, width: int, height: int) -> str | None:
    path = _attention_cache_path()
    if not path.is_file():
        return None
    try:
        record = json.loads(path.read_text(encoding="utf-8")).get(_attention_key(model, mode, width, height), {})
        backend = record.get("backend")
        return backend if backend in {"pytorch", "kitchen"} else None
    except (OSError, ValueError, TypeError, AttributeError, RuntimeError, importlib.metadata.PackageNotFoundError):
        return None


def run_attention_benchmark(*, model: str | None, runs: int, steps: int,
                            width: int, height: int, input_image: str | None = None) -> dict:
    from dreamforge_comfy_server import get_default_comfy_server
    from dreamforge_comfy_launch import _kitchen_attention_usable
    from dreamforge_cli_inventory import resolve_generation_model
    server = get_default_comfy_server()
    if server._attached_external:
        raise RuntimeError("Attention optimization requires DreamForge's managed ComfyUI.")
    index = int(os.environ.get("DREAMFORGE_COMFY_DEVICE_INDEX") or 0)
    if not _kitchen_attention_usable(index):
        raise RuntimeError("Kitchen attention is unavailable on this GPU/runtime; keeping the existing policy.")
    model_name = _benchmark_model(model)
    selected = resolve_generation_model(model_name) if model_name else None
    if not selected:
        raise ValueError("Select an installed model to benchmark")
    if input_image and selected.get("family") != "krea2":
        raise ValueError("Edit attention benchmarking currently supports Krea 2; use text-to-image for other models.")
    mode = "krea2_edit" if input_image else "txt2img"
    key = _attention_key(selected, mode, width, height)
    results = {}
    for backend in ("pytorch", "kitchen"):
        result = run_generation_benchmark(model=model_name, runs=max(3, runs), steps=steps,
                                         width=width, height=height, attention_backend=backend,
                                         input_image=input_image)
        results[backend] = result
        if (result.get("error") or not result.get("summary", {}).get("all_outputs_valid")
                or not result.get("warmup", {}).get("output_valid")):
            return {"generation_executed": True, "error": f"{backend}_benchmark_failed", "backends": results}
    if _attention_key(selected, mode, width, height) != key:
        raise RuntimeError("Runtime/model changed during benchmarking; results were not applied.")
    pt = results["pytorch"]["summary"]["median_s"]
    ck = results["kitchen"]["summary"]["median_s"]
    winner = "kitchen" if ck < pt * 0.95 else "pytorch"
    # Require a measured >5% win; ties keep full-precision SDPA.
    record = {"backend": winner, "model": model_name, "mode": mode, "width": width, "height": height,
              "pytorch_median_s": pt, "kitchen_median_s": ck, "created_at": time.time(), "backends": results}
    path = _attention_cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        records = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        records = {}
    if not isinstance(records, dict):
        records = {}
    records[key] = record
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(records, handle, indent=2)
    try:
        os.replace(handle.name, path)
    finally:
        Path(handle.name).unlink(missing_ok=True)
    return {"generation_executed": True, "model": model_name, "selected_attention": winner,
            "summary": {"all_outputs_valid": True, "pytorch_median_s": pt, "kitchen_median_s": ck},
            "backends": results}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", help="write JSON results to a file")
    parser.add_argument("--run-generation", action="store_true", help="run one warm-up and measured generations on this host")
    parser.add_argument("--compare-attention", action="store_true", help="measure and save Kitchen/PyTorch selection")
    parser.add_argument("--input-image", help="source for Krea edit benchmarking")
    parser.add_argument("--model")
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--steps", type=int, default=4)
    parser.add_argument("--width", type=int, default=512)
    parser.add_argument("--height", type=int, default=512)
    args = parser.parse_args()
    if (args.run_generation or args.compare_attention) and os.environ.get("DREAMFORGE_BENCHMARK_REEXEC") != "1":
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
    if args.run_generation or args.compare_attention:
        from dreamforge_comfy_launch import apply_runtime_optimization_env
        from dreamforge_comfy_server import register_managed_comfy_shutdown
        apply_runtime_optimization_env()
        register_managed_comfy_shutdown()
        payload_data = {"results": results, "generation": run_generation_benchmark(model=args.model, runs=args.runs, steps=args.steps, width=args.width, height=args.height, compare_attention=args.compare_attention, input_image=args.input_image)}
    else:
        payload_data = {"results": results}
    payload = json.dumps(payload_data, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(payload + "\n")
    print(payload)


if __name__ == "__main__":
    main()
