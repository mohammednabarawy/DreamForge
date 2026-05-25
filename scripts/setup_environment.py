#!/usr/bin/env python3
"""First-time / repeatable DreamForge environment setup (clone → install → run)."""
from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_ROOT = PROJECT_ROOT / "backend"
EMBED_DIR = PROJECT_ROOT / "python_embeded"
VENV_DIR = PROJECT_ROOT / "venv"
DESKTOP_DIR = PROJECT_ROOT / "apps" / "desktop"
PTH_TEMPLATE = Path(__file__).resolve().parent / "python310._pth.template"

# Match the embedded runtime used by existing Windows bundles (3.10.x).
PYTHON_EMBED_URL = "https://www.python.org/ftp/python/3.10.11/python-3.10.11-embed-amd64.zip"
GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"

MODEL_DIRS = (
    "checkpoints",
    "loras",
    "vae",
    "vae_approx",
    "clip",
    "clip_vision",
    "controlnet",
    "diffusers",
    "diffusers_cache",
    "upscale_models",
    "faceswap",
    "llm",
    "inbox",
    "configs",
)


def log(msg: str) -> None:
    print(msg, flush=True)


def run(cmd: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    log(f"  $ {' '.join(cmd)}")
    subprocess.run(cmd, cwd=str(cwd or PROJECT_ROOT), env=env, check=True)


def find_python() -> Path | None:
    embed = EMBED_DIR / ("python.exe" if os.name == "nt" else "python")
    if embed.is_file():
        return embed
    if os.name == "nt":
        venv_py = VENV_DIR / "Scripts" / "python.exe"
    else:
        venv_py = VENV_DIR / "bin" / "python"
    if venv_py.is_file():
        return venv_py
    return None


def configure_embedded_pth() -> None:
    if not PTH_TEMPLATE.is_file():
        raise FileNotFoundError(f"Missing template: {PTH_TEMPLATE}")
    pth_files = list(EMBED_DIR.glob("python*._pth"))
    if not pth_files:
        raise FileNotFoundError(f"No python*._pth in {EMBED_DIR}")
    for pth in pth_files:
        pth.write_text(PTH_TEMPLATE.read_text(encoding="utf-8"), encoding="utf-8")
        log(f"Wrote {pth.relative_to(PROJECT_ROOT)}")


def bootstrap_embedded_windows() -> Path:
    if EMBED_DIR.exists() and any(EMBED_DIR.iterdir()):
        log(f"Using existing {EMBED_DIR}")
    else:
        EMBED_DIR.mkdir(parents=True, exist_ok=True)
        zip_path = PROJECT_ROOT / ".setup" / "python-embed.zip"
        zip_path.parent.mkdir(parents=True, exist_ok=True)
        log(f"Downloading embedded Python from {PYTHON_EMBED_URL}")
        urllib.request.urlretrieve(PYTHON_EMBED_URL, zip_path)
        log(f"Extracting to {EMBED_DIR}")
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(EMBED_DIR)
        zip_path.unlink(missing_ok=True)

    configure_embedded_pth()

    python_exe = EMBED_DIR / "python.exe"
    if not python_exe.is_file():
        raise FileNotFoundError(f"Embedded python.exe not found in {EMBED_DIR}")

    get_pip = EMBED_DIR / "get-pip.py"
    if not _pip_works(python_exe):
        log("Installing pip into embedded Python...")
        urllib.request.urlretrieve(GET_PIP_URL, get_pip)
        run([str(python_exe), str(get_pip)])
        get_pip.unlink(missing_ok=True)

    return python_exe


def _pip_works(python: Path) -> bool:
    try:
        subprocess.run(
            [str(python), "-m", "pip", "--version"],
            cwd=str(PROJECT_ROOT),
            check=True,
            capture_output=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def bootstrap_venv() -> Path:
    if VENV_DIR.exists() and find_python() == (VENV_DIR / ("Scripts/python.exe" if os.name == "nt" else "bin/python")):
        log(f"Using existing venv at {VENV_DIR}")
        return find_python()  # type: ignore[return-value]

    candidates: list[list[str]] = []
    if os.name == "nt":
        candidates.extend(
            [
                ["py", "-3.10", "-m", "venv", str(VENV_DIR)],
                ["py", "-3", "-m", "venv", str(VENV_DIR)],
            ]
        )
    candidates.append([sys.executable, "-m", "venv", str(VENV_DIR)])

    last_error: Exception | None = None
    for cmd in candidates:
        try:
            if cmd[0] == "py":
                subprocess.run([cmd[0], "-3.10", "--version"], check=True, capture_output=True)
            run(cmd)
            py = find_python()
            if py:
                return py
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            last_error = exc

    raise RuntimeError(
        "Could not create a Python virtual environment. "
        "Install Python 3.10+ or run setup with --embed (Windows)."
    ) from last_error


def ensure_directories() -> None:
    for name in MODEL_DIRS:
        (BACKEND_ROOT / "models" / name).mkdir(parents=True, exist_ok=True)
    (PROJECT_ROOT / "outputs").mkdir(parents=True, exist_ok=True)
    (BACKEND_ROOT / "cache").mkdir(parents=True, exist_ok=True)
    (BACKEND_ROOT / "repositories").mkdir(parents=True, exist_ok=True)
    (BACKEND_ROOT / "settings").mkdir(parents=True, exist_ok=True)
    log("Created model, output, and cache directories.")


def install_python_stack(python: Path, *, skip_torch: bool = False) -> None:
    run([str(python), "-m", "pip", "install", "--upgrade", "pip"])
    run(
        [str(python), "-m", "pip", "install", "-r", "requirements_versions.txt"],
        cwd=BACKEND_ROOT,
    )
    if skip_torch:
        log("Skipping full torch / ComfyUI bootstrap (--skip-torch).")
        return
    run([str(python), "launch.py", "--setup-only"], cwd=BACKEND_ROOT)


def install_desktop_deps() -> None:
    npm = shutil.which("npm")
    if not npm:
        log("npm not found — skipping desktop dependencies (install Node.js 20+ for the Tauri app).")
        return
    run([npm, "install"], cwd=DESKTOP_DIR)


def write_setup_marker() -> None:
    marker = PROJECT_ROOT / ".dreamforge_setup_ok"
    marker.write_text(platform.platform(), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Set up DreamForge after cloning the repository.")
    parser.add_argument(
        "--embed",
        action="store_true",
        help="Download Windows embedded Python into python_embeded/ (default on Windows when no Python exists).",
    )
    parser.add_argument(
        "--venv",
        action="store_true",
        help="Create/use a venv/ at repo root instead of embedded Python.",
    )
    parser.add_argument("--skip-python", action="store_true", help="Skip Python dependency installation.")
    parser.add_argument("--skip-torch", action="store_true", help="Install pip requirements only (no torch/ComfyUI bootstrap).")
    parser.add_argument("--skip-npm", action="store_true", help="Skip npm install for apps/desktop.")
    parser.add_argument("--skip-dirs", action="store_true", help="Skip creating model/output folders.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    log(f"DreamForge setup — {PROJECT_ROOT}")

    python = find_python()
    if python is None:
        if args.venv:
            python = bootstrap_venv()
        elif os.name == "nt" and not args.venv:
            python = bootstrap_embedded_windows()
        else:
            python = bootstrap_venv()
    else:
        log(f"Using Python: {python}")
        if EMBED_DIR in python.parents or python.parent == EMBED_DIR:
            configure_embedded_pth()

    if not args.skip_dirs:
        ensure_directories()

    if not args.skip_python:
        install_python_stack(python, skip_torch=args.skip_torch)

    if not args.skip_npm:
        install_desktop_deps()

    write_setup_marker()
    log("")
    log("Setup complete.")
    log(f"  Python:  {python}")
    log(f"  Backend: {BACKEND_ROOT}")
    log("")
    if os.name == "nt":
        log("Next: dreamforge.bat (desktop) or dreamforge-cli.bat --dry-run ...")
    else:
        log("Next: ./DreamForge.command or ./dreamforge.sh")
    log("Place model weights under backend/models/ before generating images.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
