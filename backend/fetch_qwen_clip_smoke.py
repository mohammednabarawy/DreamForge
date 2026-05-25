"""Download Qwen-Image-Edit CLIP and run a local GPU smoke test.

Recommended (default): Unsloth Qwen2.5-VL GGUF (`qwen2vl` arch) — works with this Comfy GGUF loader.

The pathdb `pig-encoder` CLIP downloads but fails with:
  "This gguf file is incompatible with llama.cpp" (architecture: pig).

Usage:
  fetch-qwen-clip-smoke.bat
  fetch-qwen-clip-smoke.bat --clip-source unsloth
  fetch-qwen-clip-smoke.bat --clip-source pig --smoke-model Qwen_Image_Edit-Q3_K_M
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


from _paths import BACKEND_ROOT, PROJECT_ROOT, PYTHON_EXE, extend_sys_path

extend_sys_path()
SETTINGS_PATH = BACKEND_ROOT / "settings" / "settings.json"
CLIP_JSON = BACKEND_ROOT / "modules" / "pathdb" / "clip.json"
CLIP_DIR = BACKEND_ROOT / "models" / "clip"
DEFAULT_OUTPUT = PROJECT_ROOT / "outputs" / "eval" / "qwen_edit_smoke.png"
DEFAULT_INPUT = PROJECT_ROOT / "outputs" / "eval" / "qwen_smoke_input.png"

CLIP_SOURCES = {
    "unsloth": {
        "json_key": "clip/Qwen2.5-VL-7B-Instruct-Q4_K_S.gguf",
        "settings_key": "clip_qwen25",
        "smoke_model": "Qwen_Image_Edit-Q3_K_M",
        "note": "Recommended. qwen2vl-compatible GGUF text encoder.",
    },
    "pig": {
        "json_key": "clip/qwen_2.5_vl_7b_edit-q2_k.gguf",
        "settings_key": "clip_qwen25",
        "smoke_model": "Qwen_Image_Edit-Q3_K_M",
        "note": "Legacy pathdb default. Often fails: general.architecture=pig.",
    },
    "fp8": {
        "json_key": "clip/qwen_2.5_vl_7b_fp8_scaled.safetensors",
        "settings_key": "clip_qwen25",
        "smoke_model": "qwen_image_edit_2509_fp8_e4m3fn",
        "note": "Safetensors CLIP + safetensors edit UNet (experimental on this build).",
    },
}


def _clip_entry(key: str) -> tuple[str, str]:
    data = json.loads(CLIP_JSON.read_text(encoding="utf-8"))
    entry = data[key]
    return entry["url"], entry["filename"]


def _gguf_architecture(path: Path) -> str | None:
    try:
        import gguf
    except ImportError:
        return None
    try:
        reader = gguf.GGUFReader(str(path))
        for field in reader.fields.values():
            if field.name == "general.architecture":
                value = field.parts[field.data[-1]]
                if isinstance(value, bytes):
                    return value.decode("utf-8", errors="replace")
                if isinstance(value, (list, tuple)) and value and isinstance(value[0], int):
                    return bytes(value).decode("utf-8", errors="replace")
                return str(value)
    except Exception:
        return None
    return None


def _download(url: str, dest: Path, *, min_bytes: int = 1024 * 1024) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size >= min_bytes:
        print(f"CLIP already present: {dest} ({dest.stat().st_size / (1024**3):.2f} GB)")
        return dest

    partial = dest.with_suffix(dest.suffix + ".partial")
    headers = {"User-Agent": "DreamForge-qwen-clip-fetch/1.0"}
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    print(f"Downloading\n  {url}\nto\n  {dest}")
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=120) as response:
        total = int(response.headers.get("Content-Length", 0))
        downloaded = 0
        chunk_size = 1024 * 1024
        start = time.time()
        with partial.open("wb") as handle:
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                handle.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = downloaded * 100 / total
                    mb = downloaded / (1024 * 1024)
                    total_mb = total / (1024 * 1024)
                    elapsed = max(time.time() - start, 0.001)
                    print(
                        f"\r  {mb:.0f}/{total_mb:.0f} MB ({pct:.1f}%) "
                        f"{mb / elapsed:.1f} MB/s",
                        end="",
                        flush=True,
                    )
        print()

    partial.replace(dest)
    print(f"Saved {dest} ({dest.stat().st_size / (1024**3):.2f} GB)")
    return dest


def _ensure_clip_source(source: str, *, skip_download: bool) -> tuple[Path, str, str]:
    spec = CLIP_SOURCES[source]
    url, filename = _clip_entry(spec["json_key"])
    dest = CLIP_DIR / filename

    if source == "fp8":
        local = BACKEND_ROOT / "models" / "text_encoders" / filename
        if local.exists() and not dest.exists():
            print(f"Copying local text encoder to clip folder:\n  {local} -> {dest}")
            dest.parent.mkdir(parents=True, exist_ok=True)
            if not dest.exists():
                import shutil
                shutil.copy2(local, dest)

    if not skip_download:
        _download(url, dest)
    elif not dest.exists():
        raise FileNotFoundError(f"CLIP missing: {dest}")

    if dest.suffix == ".gguf":
        arch = _gguf_architecture(dest)
        print(f"GGUF architecture: {arch or 'unknown'}")
        if arch in {None, "pig", "cow"}:
            raise ValueError(
                f"CLIP {dest.name} uses architecture '{arch}' and is not supported for text encoding. "
                f"Re-run with --clip-source unsloth (recommended)."
            )

    return dest, spec["settings_key"], spec["smoke_model"]


def _apply_clip_setting(settings_key: str, filename: str) -> None:
    data = {}
    if SETTINGS_PATH.exists():
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    data[settings_key] = filename
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Updated {SETTINGS_PATH.name}: {settings_key} = {filename}")


def _ensure_smoke_input(path: Path) -> Path:
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (512, 512), (32, 36, 48))
    draw = ImageDraw.Draw(image)
    draw.rectangle((156, 120, 356, 392), fill=(220, 180, 40), outline=(255, 230, 120), width=4)
    draw.polygon([(256, 80), (296, 160), (216, 160)], fill=(220, 180, 40))
    draw.text((210, 430), "SMOKE TEST", fill=(200, 200, 210))
    image.save(path)
    print(f"Created smoke input: {path}")
    return path


def _dry_run_ready(model: str, vram_profile: str) -> bool:
    cmd = [
        str(PYTHON_EXE),
        "-s",
        str(BACKEND_ROOT / "dreamforge_cli_direct.py"),
        "--dry-run",
        "--json",
        "--model",
        model,
        "--vram-profile",
        vram_profile,
    ]
    result = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr or result.stdout)
        return False
    payload = json.loads(result.stdout)
    missing = payload.get("missing_dependencies") or []
    if missing:
        print("Missing dependencies:", json.dumps(missing, indent=2))
        return False
    print("Dry-run ready: model and files resolved.")
    return True


def _run_smoke(
    *,
    model: str,
    input_image: Path,
    output: Path,
    vram_profile: str,
    width: int,
    height: int,
    steps: int,
    timeout_s: int,
) -> int:
    output.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(PYTHON_EXE),
        "-s",
        str(BACKEND_ROOT / "dreamforge_cli_direct.py"),
        "--json",
        "--model",
        model,
        "--input-image",
        str(input_image.relative_to(PROJECT_ROOT)),
        "--prompt",
        "make the warning triangle icon brighter and more saturated, keep background unchanged",
        "--width",
        str(width),
        "--height",
        str(height),
        "--steps",
        str(steps),
        "--output",
        str(output.relative_to(PROJECT_ROOT)),
        "--validate-output",
        "--vram-profile",
        vram_profile,
    ]
    print("Running smoke test:")
    print(" ", " ".join(cmd[2:]))
    try:
        result = subprocess.run(
            cmd,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        print(f"Smoke test timed out after {timeout_s}s")
        return 2

    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()
    if stdout:
        tail = stdout[-12000:] if len(stdout) > 12000 else stdout
        print(tail)
    if stderr:
        print(stderr[-6000:], file=sys.stderr)

    if result.returncode != 0 and not stdout:
        return result.returncode

    try:
        payload = json.loads(stdout) if stdout else {}
    except json.JSONDecodeError:
        print("Smoke finished but stdout was not JSON.")
        return 1

    for item in payload.get("results") or [payload]:
        if item.get("status") == "success" and item.get("images"):
            print(f"Smoke test passed: {item['images']}")
            return 0
        if item.get("error"):
            print(f"Smoke error: {item['error']}")
            if item.get("missing_dependencies"):
                print(json.dumps(item["missing_dependencies"], indent=2))

    print("Smoke test did not produce images.")
    print(
        "Qwen-Image-Edit on this DreamForge build may need a matching encoder pair:\n"
        "  - GGUF UNet + pig all-in-one encoder (blocked: architecture 'pig' in text CLIP loader)\n"
        "  - Or safetensors UNet + qwen_2.5_vl_7b_fp8_scaled.safetensors (try --clip-source fp8)\n"
        "  - Unsloth instruct CLIP loads but can mismatch edit UNet tensor shapes\n"
        "Track upstream ComfyUI-GGUF / DreamForge Qwen-Image-Edit support."
    )
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch Qwen edit CLIP and run smoke test")
    parser.add_argument(
        "--clip-source",
        choices=list(CLIP_SOURCES),
        default="unsloth",
        help="CLIP variant to install (default: unsloth, compatible with GGUF loader)",
    )
    parser.add_argument("--skip-download", action="store_true")
    parser.add_argument("--skip-smoke", action="store_true")
    parser.add_argument("--smoke-model", default=None, help="Override diffusion model for smoke")
    parser.add_argument("--input-image", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--vram-profile", default="16gb", choices=["auto", "16gb", "8gb", "5gb"])
    parser.add_argument("--width", type=int, default=512)
    parser.add_argument("--height", type=int, default=512)
    parser.add_argument("--steps", type=int, default=8)
    parser.add_argument("--timeout", type=int, default=1200)
    args = parser.parse_args()

    print(f"CLIP source: {args.clip_source} — {CLIP_SOURCES[args.clip_source]['note']}")

    try:
        clip_path, settings_key, default_model = _ensure_clip_source(
            args.clip_source,
            skip_download=args.skip_download,
        )
    except Exception as exc:
        print(f"CLIP setup failed: {exc}")
        if args.clip_source != "unsloth":
            print("Try: fetch-qwen-clip-smoke.bat --clip-source unsloth")
        return 1

    _apply_clip_setting(settings_key, clip_path.name)

    if args.skip_smoke:
        print("CLIP ready (--skip-smoke).")
        return 0

    smoke_model = args.smoke_model or default_model
    if not _dry_run_ready(smoke_model, args.vram_profile):
        return 1

    return _run_smoke(
        model=smoke_model,
        input_image=_ensure_smoke_input(Path(args.input_image)),
        output=Path(args.output),
        vram_profile=args.vram_profile,
        width=args.width,
        height=args.height,
        steps=args.steps,
        timeout_s=args.timeout,
    )


if __name__ == "__main__":
    raise SystemExit(main())
