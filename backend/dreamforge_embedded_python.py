"""Windows embedded Python bootstrap for DreamForge (``python_embeded/``).

DreamForge keeps the portable CPython tree at the install root, e.g.
``D:\\DreamForge\\python_embeded\\python.exe`` — the same layout used by
``setup.bat`` and ComfyUI-style portable bundles.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Callable

ProgressCallback = Callable[[str], None] | None

# Intentional project spelling (matches setup.bat, dreamforge_env.bat, README).
EMBED_DIR_NAME = "python_embeded"

BACKEND_ROOT = Path(__file__).resolve().parent
DEFAULT_INSTALL_ROOT = BACKEND_ROOT.parent
SCRIPTS_ROOT = DEFAULT_INSTALL_ROOT / "scripts"
PTH_TEMPLATE = SCRIPTS_ROOT / "python310._pth.template"

PYTHON_EMBED_URL = "https://www.python.org/ftp/python/3.10.11/python-3.10.11-embed-amd64.zip"
GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"
DOWNLOAD_TIMEOUT_S = 300.0

from dreamforge_bootstrap_markers import (  # noqa: E402
    python_stack_marker_valid,
    write_python_stack_marker,
)


def _report(progress: ProgressCallback, message: str) -> None:
    if progress:
        progress(message)


def resolve_install_root() -> Path:
    from dreamforge_runtime_paths import resolve_install_root as _runtime_install_root

    return _runtime_install_root()


def embedded_python_dir(install_root: Path | None = None) -> Path:
    root = (install_root or resolve_install_root()).resolve()
    return root / EMBED_DIR_NAME


def embedded_python_exe(install_root: Path | None = None) -> Path:
    root = embedded_python_dir(install_root)
    name = "python.exe" if os.name == "nt" else "python"
    return root / name


def embedded_python_ready(install_root: Path | None = None) -> bool:
    return embedded_python_exe(install_root).is_file()


def configure_embedded_pth(
    embed_dir: Path,
    *,
    install_root: Path | None = None,
    comfy_root: Path | None = None,
) -> None:
    """Write ``python*._pth`` so embedded Python sees backend + ComfyUI."""
    install = (install_root or resolve_install_root()).resolve()
    backend = BACKEND_ROOT if BACKEND_ROOT.is_dir() else (install / "backend")
    embed_parent = embed_dir.parent

    def _path_entry(target: Path) -> str:
        try:
            return os.path.relpath(target.resolve(), embed_parent)
        except ValueError:
            return str(target.resolve())

    lines: list[str] = []
    if backend.is_dir():
        lines.append(_path_entry(backend))
    resolved_comfy = Path(comfy_root).resolve() if comfy_root else None
    if resolved_comfy and resolved_comfy.is_dir():
        lines.append(_path_entry(resolved_comfy))
    else:
        for candidate in (
            install / "engines" / "comfyui",
            install / "ComfyUI",
            backend / "repositories" / "ComfyUI",
        ):
            if candidate.is_dir():
                lines.append(_path_entry(candidate))
                break
    lines.extend(["python310.zip", ".", "", "#import site", "import site"])
    body = "\n".join(lines) + "\n"

    pth_files = list(embed_dir.glob("python*._pth"))
    if not pth_files:
        raise FileNotFoundError(f"No python*._pth in {embed_dir}")
    for pth in pth_files:
        pth.write_text(body, encoding="utf-8")


def refresh_embedded_python_paths(layout=None) -> None:
    """Refresh ``._pth`` after ComfyUI moves to the data root."""
    from dreamforge_runtime_paths import build_runtime_layout

    resolved = layout or build_runtime_layout()
    embed_dir = resolved.embedded_python_dir
    if not embed_dir.is_dir():
        return
    configure_embedded_pth(
        embed_dir,
        install_root=resolved.install_root,
        comfy_root=resolved.comfy_root,
    )


def _download_file(url: str, dest: Path, *, progress: ProgressCallback = None) -> None:
    from dreamforge_bootstrap import _download_file as bootstrap_download

    bootstrap_download(url, dest, timeout=DOWNLOAD_TIMEOUT_S, progress=progress)


def _subprocess_kwargs(**extra: object) -> dict:
    kwargs = dict(extra)
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return kwargs


def _pip_works(python: Path) -> bool:
    try:
        subprocess.run(
            [str(python), "-m", "pip", "--version"],
            check=True,
            capture_output=True,
            **_subprocess_kwargs(),
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def _run(cmd: list[str], *, cwd: Path | None = None, progress: ProgressCallback = None) -> None:
    _report(progress, f"Running: {' '.join(cmd)}")
    subprocess.run(
        cmd,
        cwd=str(cwd or DEFAULT_INSTALL_ROOT),
        check=True,
        **_subprocess_kwargs(),
    )


def _install_pip_into_embed(
    python_exe: Path,
    embed_dir: Path,
    *,
    progress: ProgressCallback = None,
) -> None:
    get_pip = embed_dir / "get-pip.py"
    _download_file(GET_PIP_URL, get_pip, progress=progress)
    py = os.path.normpath(str(python_exe))
    script = os.path.normpath(str(get_pip))
    _report(progress, f"Running: {py} {script}")
    result = subprocess.run(
        [py, script],
        cwd=os.path.normpath(str(embed_dir.parent)),
        capture_output=True,
        text=True,
        **_subprocess_kwargs(),
    )
    get_pip.unlink(missing_ok=True)
    if result.returncode == 0 and _pip_works(python_exe):
        return
    detail = (result.stderr or result.stdout or "").strip()
    raise RuntimeError(
        "Failed to install pip into python_embeded"
        + (f": {detail[-800:]}" if detail else "")
    )


def ensure_embedded_python(
    install_root: Path | None = None,
    *,
    progress: ProgressCallback = None,
    download: bool = True,
) -> Path:
    """Ensure ``{install_root}/python_embeded/python.exe`` exists and has pip."""
    if os.name != "nt":
        raise RuntimeError(
            "Embedded python_embeded is Windows-only. On macOS/Linux use setup.sh / venv."
        )

    root = (install_root or resolve_install_root()).resolve()
    embed_dir = embedded_python_dir(root)
    python_exe = embedded_python_exe(root)

    if embed_dir.is_dir() and python_exe.is_file():
        _report(progress, f"Using existing {embed_dir}")
    elif embed_dir.is_dir() and any(embed_dir.iterdir()) and not python_exe.is_file():
        _report(progress, f"Repairing incomplete {EMBED_DIR_NAME} install…")
        shutil.rmtree(embed_dir, ignore_errors=True)

    if not python_exe.is_file():
        if not download:
            raise FileNotFoundError(
                f"Embedded Python not found at {python_exe}. Run setup.bat or the first-run wizard."
            )
        embed_dir.mkdir(parents=True, exist_ok=True)
        cache_dir = root / ".setup"
        cache_dir.mkdir(parents=True, exist_ok=True)
        zip_path = cache_dir / "python-embed.zip"
        _report(progress, f"Downloading embedded Python to {embed_dir}…")
        _download_file(PYTHON_EMBED_URL, zip_path, progress=progress)
        _report(progress, f"Extracting {EMBED_DIR_NAME}…")
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(embed_dir)
        zip_path.unlink(missing_ok=True)

    if not python_exe.is_file():
        raise FileNotFoundError(f"python.exe not found in {embed_dir}")

    configure_embedded_pth(embed_dir)

    if not _pip_works(python_exe):
        _report(progress, "Installing pip into python_embeded…")
        _install_pip_into_embed(python_exe, embed_dir, progress=progress)

    return python_exe


def install_dreamforge_python_stack(
    python: Path,
    *,
    progress: ProgressCallback = None,
    skip_torch_bootstrap: bool = False,
) -> None:
    """Install DreamForge pip requirements and optional torch/Comfy bootstrap."""
    python = Path(python).resolve()
    if python_stack_marker_valid():
        _report(progress, "DreamForge Python stack already installed.")
        return

    _report(progress, "Upgrading pip in python_embeded…")
    _run([str(python), "-m", "pip", "install", "--upgrade", "pip"], progress=progress)

    req_file = BACKEND_ROOT / "requirements_versions.txt"
    if req_file.is_file():
        _report(progress, "Installing DreamForge Python requirements…")
        _run(
            [str(python), "-m", "pip", "install", "-r", str(req_file)],
            cwd=BACKEND_ROOT,
            progress=progress,
        )

    if skip_torch_bootstrap:
        return

    try:
        subprocess.run(
            [str(python), "-c", "import torch"],
            check=True,
            capture_output=True,
            **_subprocess_kwargs(),
        )
        has_torch = True
    except (subprocess.CalledProcessError, FileNotFoundError):
        has_torch = False

    if not has_torch:
        _report(progress, "Bootstrapping PyTorch and ComfyUI prerequisites (may take several minutes)…")
        _run([str(python), "launch.py", "--setup-only"], cwd=BACKEND_ROOT, progress=progress)

    write_python_stack_marker()


def embedded_python_status(install_root: Path | None = None) -> dict[str, str | bool]:
    root = (install_root or resolve_install_root()).resolve()
    embed_dir = embedded_python_dir(root)
    exe = embedded_python_exe(root)
    return {
        "install_root": str(root),
        "embedded_dir": str(embed_dir),
        "embedded_python": str(exe),
        "ready": exe.is_file(),
        "dir_name": EMBED_DIR_NAME,
    }
