"""Shared DreamForge backend path constants."""
from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_ROOT.parent
REPOS_ROOT = BACKEND_ROOT / "repositories"
OUTPUTS_ROOT = PROJECT_ROOT / "outputs"
TEMP_ROOT = PROJECT_ROOT / "temp"
PREVIEWS_DIR = TEMP_ROOT / "previews"
COMFY_STAGING_DIR = TEMP_ROOT / "comfy-staging"
MODELS_ROOT = PROJECT_ROOT / "models"


def resolve_install_root() -> Path:
    try:
        from dreamforge_runtime_paths import resolve_install_root as _runtime_install_root

        return _runtime_install_root()
    except Exception:
        raw = os.environ.get("DREAMFORGE_INSTALL_ROOT", "").strip()
        if raw:
            return Path(raw)
        backend = os.environ.get("DREAMFORGE_BACKEND_ROOT") or os.environ.get("DREAMFORGE_ROOT")
        if backend:
            return Path(backend).resolve().parent
        return BACKEND_ROOT.parent


def resolve_comfy_root() -> Path:
    """Resolve ComfyUI engine directory (prefer env, then data-root managed path)."""
    env_root = os.environ.get("DREAMFORGE_COMFY_ROOT")
    if env_root:
        return Path(env_root)
    data_root = os.environ.get("DREAMFORGE_DATA_ROOT")
    if data_root:
        managed = Path(data_root) / "engines" / "comfyui"
        legacy = BACKEND_ROOT / "repositories" / "ComfyUI"
        if managed.is_dir() and any(managed.iterdir()):
            return managed.resolve()
        if legacy.is_dir() and any(legacy.iterdir()) and not managed.is_dir():
            return legacy.resolve()
        return managed.resolve()
    install = resolve_install_root()
    for candidate in (
        install / "engines" / "comfyui",
        install / "ComfyUI",
        BACKEND_ROOT / "repositories" / "ComfyUI",
    ):
        if candidate.is_dir() and any(candidate.iterdir()):
            return candidate.resolve()
    return (install / "engines" / "comfyui").resolve()


COMFY_ROOT = resolve_comfy_root()


def resolve_models_root() -> Path:
    env_root = os.environ.get("DREAMFORGE_MODELS_ROOT")
    if env_root:
        return Path(env_root)
    data_root = os.environ.get("DREAMFORGE_DATA_ROOT")
    if data_root and (Path(data_root) / "models").is_dir():
        return Path(data_root) / "models"
    legacy = PROJECT_ROOT / "models"
    if legacy.is_dir():
        return legacy
    if data_root:
        return Path(data_root) / "models"
    return legacy


def resolve_project_root() -> Path:
    data_root = os.environ.get("DREAMFORGE_DATA_ROOT")
    if data_root:
        return Path(data_root)
    return BACKEND_ROOT.parent


def resolve_outputs_root() -> Path:
    data_root = os.environ.get("DREAMFORGE_DATA_ROOT")
    if data_root:
        return Path(data_root) / "outputs"
    return PROJECT_ROOT / "outputs"


def resolve_temp_root() -> Path:
    data_root = os.environ.get("DREAMFORGE_DATA_ROOT")
    if data_root:
        return Path(data_root) / "temp"
    return PROJECT_ROOT / "temp"


def resolve_previews_dir() -> Path:
    return resolve_temp_root() / "previews"


def resolve_comfy_staging_dir() -> Path:
    return resolve_temp_root() / "comfy-staging"


def resolve_python_exe() -> Path:
    """``python_embeded`` at install root, then venv, then current interpreter."""
    install = resolve_install_root()
    embedded_env = os.environ.get("DREAMFORGE_EMBEDDED_PYTHON", "").strip()
    if embedded_env:
        candidate = Path(embedded_env)
        if candidate.is_file():
            return candidate
    if os.name == "nt":
        candidates = (
            install / "python_embeded" / "python.exe",
            install / "venv" / "Scripts" / "python.exe",
        )
    else:
        candidates = (
            Path("/opt/anaconda3/envs/dreamforge/bin/python"),
            install / "venv" / "bin" / "python",
        )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    data_root = os.environ.get("DREAMFORGE_DATA_ROOT")
    if data_root:
        venv = Path(data_root) / "venv" / (
            "Scripts/python.exe" if os.name == "nt" else "bin/python"
        )
        if venv.is_file():
            return venv
    return Path(sys.executable)


PYTHON_EXE = resolve_python_exe()


def refresh_path_constants(layout: object | None = None) -> None:
    """Refresh module-level path constants after runtime layout changes."""
    global PROJECT_ROOT, OUTPUTS_ROOT, TEMP_ROOT, PREVIEWS_DIR, COMFY_STAGING_DIR
    global MODELS_ROOT, COMFY_ROOT, PYTHON_EXE, BACKEND_ROOT

    if layout is not None:
        from dreamforge_runtime_paths import RuntimeLayout

        if isinstance(layout, RuntimeLayout):
            BACKEND_ROOT = layout.backend_root
            PROJECT_ROOT = layout.data_root
            OUTPUTS_ROOT = layout.outputs_root
            TEMP_ROOT = layout.temp_root
            PREVIEWS_DIR = layout.previews_dir
            COMFY_STAGING_DIR = layout.comfy_staging_dir
            MODELS_ROOT = layout.models_root
            COMFY_ROOT = layout.comfy_root
            if layout.embedded_python_exe.is_file():
                PYTHON_EXE = layout.embedded_python_exe
            else:
                PYTHON_EXE = resolve_python_exe()
            return

    backend_env = os.environ.get("DREAMFORGE_BACKEND_ROOT") or os.environ.get("DREAMFORGE_ROOT")
    if backend_env:
        BACKEND_ROOT = Path(backend_env)
    PROJECT_ROOT = resolve_project_root()
    OUTPUTS_ROOT = resolve_outputs_root()
    TEMP_ROOT = resolve_temp_root()
    PREVIEWS_DIR = resolve_previews_dir()
    COMFY_STAGING_DIR = resolve_comfy_staging_dir()
    MODELS_ROOT = resolve_models_root()
    COMFY_ROOT = resolve_comfy_root()
    PYTHON_EXE = resolve_python_exe()


def bootstrap_paths() -> None:
    """Initialize runtime paths from env/config (call from app entrypoints)."""
    if os.environ.get("DREAMFORGE_SKIP_RUNTIME_PATHS") == "1":
        return
    try:
        from dreamforge_runtime_paths import init_runtime_paths

        init_runtime_paths()
    except Exception:
        refresh_path_constants()


def extend_sys_path() -> None:
    for path in (str(BACKEND_ROOT), str(COMFY_ROOT), str(REPOS_ROOT)):
        if path not in sys.path:
            sys.path.insert(0, path)
