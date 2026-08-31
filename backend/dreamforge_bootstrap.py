"""First-run bootstrap: directories, ComfyUI, custom nodes (no Git required)."""

from __future__ import annotations

import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Callable

from dreamforge_bootstrap_markers import (
    COMFY_DEPS_MARKER,
    COMFY_PIN_FILE,
    RECIPE_BOUND_STEPS,
    bootstrap_recipe_fingerprint,
    clear_install_markers,
    comfy_deps_marker_valid,
    node_deps_marker_valid,
    write_comfy_deps_marker,
    write_node_deps_marker,
)
from dreamforge_krita_recipes import COMFY_INSTALL_RECIPE
from dreamforge_runtime_paths import (
    RuntimeConfig,
    build_runtime_layout,
    ensure_data_layout,
    ensure_model_subdirs,
    init_runtime_paths,
    load_runtime_config,
    save_runtime_config,
    system_info,
    validate_models_folder,
)

ProgressCallback = Callable[[str], None] | None

SETUP_STATE_NAME = "setup-state.json"
SETUP_STEPS: tuple[str, ...] = (
    "prepare_directories",
    "install_embedded_python",
    "install_dreamforge_stack",
    "install_comfyui",
    "install_comfy_deps",
    "install_custom_nodes",
    "configure_comfy_models",
    "verify_engine",
)

_COMFY_PIN_FILE = COMFY_PIN_FILE


def _report(progress: ProgressCallback, message: str) -> None:
    if progress:
        progress(message)


def _github_archive_url(repo_url: str, commit: str) -> str:
    slug = repo_url.rstrip("/").removesuffix(".git")
    if "github.com/" not in slug:
        raise ValueError(f"Unsupported repository URL: {repo_url}")
    owner_repo = slug.split("github.com/", 1)[1]
    return f"https://github.com/{owner_repo}/archive/{commit}.zip"


def _download_bytes(url: str, *, timeout: float = 120.0) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "DreamForgeBootstrap/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def _download_file(
    url: str,
    dest: Path,
    *,
    timeout: float = 300.0,
    progress: ProgressCallback = None,
) -> None:
    """Stream a URL to disk with timeout (avoids loading large archives into RAM)."""
    request = urllib.request.Request(url, headers={"User-Agent": "DreamForgeBootstrap/1.0"})
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        total = int(response.headers.get("Content-Length") or 0)
        read = 0
        chunk_size = 256 * 1024
        with dest.open("wb") as out:
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                out.write(chunk)
                read += len(chunk)
                if progress and total > 0 and read % (chunk_size * 4) < chunk_size:
                    _report(
                        progress,
                        f"Downloaded {read // (1024 * 1024)} / {max(total // (1024 * 1024), 1)} MB…",
                    )
    if progress:
        _report(progress, f"Saved {dest.name}")


def extract_github_zip(payload: bytes, dest: Path) -> None:
    """Validate GitHub archive paths and extract into a private staging directory."""
    dest = dest.resolve()
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        entries = [entry for entry in zf.infolist() if not entry.is_dir()]
        roots = {entry.filename.split("/", 1)[0] for entry in entries}
        if not entries or len(roots) != 1 or any("/" not in e.filename for e in entries):
            raise ValueError("Expected a non-empty GitHub repository archive")
        seen = set()
        for entry in entries:
            parts = PurePosixPath(entry.filename).parts
            if (entry.filename.startswith("/") or ".." in parts or "\\" in entry.filename
                    or ":" in entry.filename or stat.S_ISLNK(entry.external_attr >> 16)):
                raise ValueError(f"Unsafe archive entry: {entry.filename}")
            relative = Path(*parts[1:])
            if relative.parts[0].casefold() in {".git", ".dreamforge_archive_pin"}:
                raise ValueError(f"Reserved archive entry: {entry.filename}")
            key = str(relative).casefold()
            if key in seen or not (dest / relative).resolve().is_relative_to(dest):
                raise ValueError(f"Duplicate or unsafe archive entry: {entry.filename}")
            seen.add(key)
        dest.mkdir(parents=True, exist_ok=True)
        for entry in entries:
            target = dest.joinpath(*PurePosixPath(entry.filename).parts[1:])
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(entry) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)


def checkout_github_commit(
    repo_url: str, commit: str, dest: Path, *,
    progress: ProgressCallback = None, label: str | None = None,
) -> Path:
    """Stage archives, preserve user data, and roll back failed file replacements."""
    dest = dest.resolve()
    name = label or dest.name
    marker = dest / ".dreamforge_archive_pin"
    if marker.is_file() and marker.read_text(encoding="utf-8").strip() == commit:
        return dest
    # Never overlay a Git checkout after a failed fetch/checkout or a dirty-tree error.
    if (dest / ".git").exists():
        raise RuntimeError(f"Git update failed for {name}; existing checkout preserved. Repair Git and retry.")
    _report(progress, f"Downloading {name} ({commit[:12]})…")
    try:
        payload = _download_bytes(_github_archive_url(repo_url, commit), timeout=300.0)
    except (urllib.error.HTTPError, urllib.error.URLError) as exc:
        raise RuntimeError(f"Download failed for {name}: {exc}") from exc
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{dest.name}-update-", dir=dest.parent) as folder:
        stage = Path(folder).resolve()
        extract_github_zip(payload, stage)
        files = sorted(path.relative_to(stage) for path in stage.rglob("*") if path.is_file())
        is_comfy = repo_url.rstrip("/").removesuffix(".git").lower().endswith("/comfyui")
        if is_comfy and not (stage / "main.py").is_file():
            raise ValueError("ComfyUI archive has no main.py")
        protected = {"models", "custom_nodes", "input", "output", "user", "temp"}
        files = [path for path in files if not (is_comfy and
                 ((path.parts[0] in protected and (dest / path.parts[0]).exists())
                  or (path.name.startswith("extra_model_paths") and (dest / path).exists())))]
        (stage / ".dreamforge_archive_pin").write_text(commit + "\n", encoding="utf-8")
        files.append(Path(".dreamforge_archive_pin"))
        backup = dest.parent / ".dreamforge-backups" / f"{dest.name}-{time.time_ns()}"
        changed: list[tuple[Path, bool]] = []
        created_dirs: list[Path] = []
        # Validate every destination before replacing any file (including junctions).
        for relative in files:
            target = dest / relative
            if target.resolve() != target or not target.resolve().is_relative_to(dest) or target.is_dir():
                raise ValueError(f"Unsafe update destination: {target}")
        try:
            for relative in files:
                target, saved = dest / relative, backup / relative
                existed = target.is_file()
                if existed:
                    saved.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(target, saved)
                missing_dirs = []
                parent = target.parent
                while not parent.exists():
                    missing_dirs.append(parent)
                    parent = parent.parent
                for parent in reversed(missing_dirs):
                    parent.mkdir()
                    created_dirs.append(parent)
                changed.append((relative, existed))
                os.replace(stage / relative, target)
        except Exception:
            for relative, existed in reversed(changed):
                target = dest / relative
                if existed:
                    os.replace(backup / relative, target)
                else:
                    target.unlink(missing_ok=True)
            for directory in reversed(created_dirs):
                directory.rmdir()
            raise
        if backup.exists():
            _report(progress, f"Previous replaced files retained at {backup}")
    _report(progress, f"Installed {name}.")
    return dest


def setup_state_path(layout=None) -> Path:
    resolved = layout or build_runtime_layout()
    return resolved.runtime_dir / SETUP_STATE_NAME


def _normalize_setup_state(state: dict[str, Any]) -> dict[str, Any]:
    fp = bootstrap_recipe_fingerprint()
    if state.get("recipe_fingerprint") != fp:
        completed = [
            step
            for step in (state.get("completed_steps") or [])
            if step not in RECIPE_BOUND_STEPS
        ]
        state["completed_steps"] = completed
        state["recipe_fingerprint"] = fp
    state.setdefault("log_lines", [])
    state.setdefault("current_message", "")
    return state


def load_setup_state(layout=None) -> dict[str, Any]:
    path = setup_state_path(layout)
    if not path.is_file():
        return _normalize_setup_state(
            {"completed_steps": [], "current_step": "", "error": "", "log_lines": []}
        )
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            return _normalize_setup_state(raw)
    except (OSError, json.JSONDecodeError):
        pass
    return _normalize_setup_state(
        {"completed_steps": [], "current_step": "", "error": "", "log_lines": []}
    )


def _append_setup_log(layout, message: str) -> None:
    state = load_setup_state(layout)
    lines = state.setdefault("log_lines", [])
    if not lines or lines[-1] != message:
        lines.append(message)
    state["log_lines"] = lines[-200:]
    state["current_message"] = message
    save_setup_state(state, layout)


def _make_progress_logger(layout, progress: ProgressCallback = None) -> ProgressCallback:
    def log(message: str) -> None:
        _append_setup_log(layout, message)
        _report(progress, message)

    return log


def save_setup_state(state: dict[str, Any], layout=None) -> None:
    resolved = layout or build_runtime_layout()
    path = setup_state_path(resolved)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def get_setup_progress() -> dict[str, Any]:
    layout = init_runtime_paths()
    state = load_setup_state(layout)
    completed = list(state.get("completed_steps") or [])
    total = len(SETUP_STEPS)
    return {
        "ok": True,
        "steps": list(SETUP_STEPS),
        "completed_steps": completed,
        "current_step": state.get("current_step") or "",
        "current_message": state.get("current_message") or "",
        "log_lines": list(state.get("log_lines") or []),
        "error": state.get("error") or "",
        "progress_pct": round(100.0 * len(completed) / total, 1) if total else 0.0,
        "setup_complete": bool(layout.config.setup_complete),
        "recipe_fingerprint": state.get("recipe_fingerprint") or bootstrap_recipe_fingerprint(),
    }


def _mark_step(state: dict[str, Any], step: str) -> None:
    completed = state.setdefault("completed_steps", [])
    if step not in completed:
        completed.append(step)
    state["current_step"] = step
    state["error"] = ""


def _bootstrap_python(layout=None):
    from dreamforge_runtime_paths import build_runtime_layout

    resolved = layout or build_runtime_layout()
    if resolved.embedded_python_exe.is_file():
        return resolved.embedded_python_exe
    env = os.environ.get("DREAMFORGE_EMBEDDED_PYTHON", "").strip()
    if env and Path(env).is_file():
        return Path(env)
    try:
        from _paths import PYTHON_EXE

        if Path(PYTHON_EXE).is_file():
            return Path(PYTHON_EXE)
    except Exception:
        pass
    return Path(sys.executable)


def _pip_install(
    python: Path,
    args: list[str],
    *,
    cwd: Path | None = None,
    progress: ProgressCallback = None,
) -> None:
    _report(progress, f"pip install {' '.join(args)}")
    cmd = [str(python), "-m", "pip", "install", *args]
    kwargs: dict = {}
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    from dreamforge_embedded_python import protected_gpu_install
    with protected_gpu_install(python) as env:
        subprocess.check_call([*cmd, "--dry-run"], cwd=str(cwd) if cwd else None, env=env, **kwargs)
        subprocess.check_call(cmd, cwd=str(cwd) if cwd else None, env=env, **kwargs)


def _verify_python_import(python: Path, module: str) -> None:
    kwargs: dict = {"capture_output": True}
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    result = subprocess.run(
        [str(python), "-c", f"import {module}"],
        **kwargs,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Python module not available after setup: {module}")


def step_install_embedded_python(*, progress: ProgressCallback = None) -> None:
    layout = init_runtime_paths()
    if os.name != "nt":
        _report(progress, "Skipping python_embeded on this platform (use venv from setup.sh).")
        return
    from dreamforge_embedded_python import ensure_embedded_python, embedded_python_status

    _report(progress, f"Ensuring {embedded_python_status(layout.install_root)['embedded_dir']}…")
    ensure_embedded_python(layout.install_root, progress=progress)
    init_runtime_paths()


def step_install_dreamforge_stack(*, progress: ProgressCallback = None) -> None:
    layout = init_runtime_paths()
    python = _bootstrap_python(layout)
    if os.name == "nt" and not layout.embedded_python_exe.is_file():
        step_install_embedded_python(progress=progress)
        layout = init_runtime_paths()
        python = _bootstrap_python(layout)
    from dreamforge_embedded_python import install_dreamforge_python_stack

    install_dreamforge_python_stack(python, progress=progress)
    init_runtime_paths()


def step_prepare_directories(*, progress: ProgressCallback = None) -> None:
    layout = init_runtime_paths()
    _report(progress, "Creating DreamForge folders…")
    ensure_data_layout(layout)
    created = ensure_model_subdirs(layout.models_root)
    if created:
        _report(progress, f"Created model subfolders: {', '.join(created[:6])}{'…' if len(created) > 6 else ''}")
    from dreamforge_comfy_server import write_dreamforge_extra_model_paths_config

    write_dreamforge_extra_model_paths_config(layout.comfy_root)


def step_install_comfyui(*, progress: ProgressCallback = None) -> None:
    layout = init_runtime_paths()
    target = COMFY_INSTALL_RECIPE.get("comfy_version") or ""
    checkout_github_commit(
        str(COMFY_INSTALL_RECIPE["comfy_url"]),
        str(target),
        layout.comfy_root,
        progress=progress,
        label="ComfyUI",
    )
    _COMFY_PIN_FILE.write_text(f"{target}\n", encoding="utf-8")
    if COMFY_DEPS_MARKER.is_file():
        COMFY_DEPS_MARKER.unlink(missing_ok=True)
    if os.name == "nt" and layout.embedded_python_exe.is_file():
        from dreamforge_embedded_python import refresh_embedded_python_paths

        refresh_embedded_python_paths(layout)


def step_install_comfy_deps(*, progress: ProgressCallback = None) -> None:
    layout = init_runtime_paths()
    req_file = layout.comfy_root / "requirements.txt"
    python = _bootstrap_python(layout)
    from dreamforge_embedded_python import runtime_identity_for_python

    runtime_identity = runtime_identity_for_python(python)
    if comfy_deps_marker_valid(layout.comfy_root, runtime_identity):
        _report(progress, "ComfyUI Python dependencies already installed.")
        return
    if not req_file.is_file():
        _report(progress, "No ComfyUI requirements.txt — skipping.")
        return
    _report(progress, "Installing ComfyUI Python dependencies…")
    _pip_install(python, ["-r", str(req_file)], progress=progress)
    write_comfy_deps_marker(layout.comfy_root, runtime_identity)


def step_install_custom_nodes(*, progress: ProgressCallback = None) -> None:
    layout = init_runtime_paths()
    custom_nodes = layout.comfy_root / "custom_nodes"
    custom_nodes.mkdir(parents=True, exist_ok=True)
    for entry in COMFY_INSTALL_RECIPE.get("required_custom_nodes") or []:
        pack_id = str(entry["id"])
        version = str(entry.get("version") or "")
        dest = custom_nodes / pack_id
        checkout_github_commit(
            str(entry["url"]),
            version,
            dest,
            progress=progress,
            label=pack_id,
        )
        req = dest / "requirements.txt"
        if req.is_file() and not node_deps_marker_valid(dest, version):
            _report(progress, f"Installing dependencies for {pack_id}…")
            _pip_install(_bootstrap_python(layout), ["-r", str(req)], progress=progress)
            write_node_deps_marker(dest, version)


def step_configure_comfy_models(*, progress: ProgressCallback = None) -> None:
    _report(progress, "Configuring ComfyUI model paths…")
    layout = init_runtime_paths()
    from dreamforge_comfy_server import write_dreamforge_extra_model_paths_config

    write_dreamforge_extra_model_paths_config(layout.comfy_root)


def step_verify_engine(*, progress: ProgressCallback = None) -> None:
    layout = init_runtime_paths()
    python = _bootstrap_python(layout)
    if os.name == "nt" and not layout.embedded_python_exe.is_file():
        raise RuntimeError(
            f"Embedded Python missing at {layout.embedded_python_dir}\\python.exe"
        )
    if not layout.comfy_root.is_dir() or not any(layout.comfy_root.iterdir()):
        raise RuntimeError("ComfyUI engine folder is empty after setup.")
    main_py = layout.comfy_root / "main.py"
    if not main_py.is_file():
        raise RuntimeError(f"ComfyUI main.py not found under {layout.comfy_root}")

    custom_nodes = layout.comfy_root / "custom_nodes"
    for entry in COMFY_INSTALL_RECIPE.get("required_custom_nodes") or []:
        pack_id = str(entry["id"])
        version = str(entry.get("version") or "")
        dest = custom_nodes / pack_id
        if not dest.is_dir() or not any(dest.iterdir()):
            raise RuntimeError(f"Required custom node pack missing: {pack_id}")
        pin = dest / ".dreamforge_archive_pin"
        if pin.is_file() and pin.read_text(encoding="utf-8").strip() != version:
            raise RuntimeError(f"Custom node pack pin mismatch: {pack_id}")
        req = dest / "requirements.txt"
        if req.is_file() and not node_deps_marker_valid(dest, version):
            raise RuntimeError(f"Custom node dependencies not installed: {pack_id}")

    _report(progress, "Verifying Python stack…")
    _verify_python_import(python, "pip")
    for module in ("PIL", "yaml"):
        _verify_python_import(python, module)
    try:
        _verify_python_import(python, "torch")
    except RuntimeError:
        _report(progress, "PyTorch not importable yet (optional until first GPU run).")

    if comfy_deps_marker_valid(layout.comfy_root):
        _report(progress, "ComfyUI dependency marker OK.")
    elif (layout.comfy_root / "requirements.txt").is_file():
        raise RuntimeError("ComfyUI Python dependencies were not installed.")

    validation = validate_models_folder(layout.models_root, create=False)
    if validation.get("errors"):
        raise RuntimeError(
            "Models folder validation failed: "
            + "; ".join(validation.get("errors") or ["unknown error"])
        )
    _report(progress, "Engine verification passed.")


_STEP_HANDLERS = {
    "prepare_directories": step_prepare_directories,
    "install_embedded_python": step_install_embedded_python,
    "install_dreamforge_stack": step_install_dreamforge_stack,
    "install_comfyui": step_install_comfyui,
    "install_comfy_deps": step_install_comfy_deps,
    "install_custom_nodes": step_install_custom_nodes,
    "configure_comfy_models": step_configure_comfy_models,
    "verify_engine": step_verify_engine,
}


def run_bootstrap_step(step: str, *, progress: ProgressCallback = None) -> dict[str, Any]:
    if step not in SETUP_STEPS:
        return {"ok": False, "error": f"Unknown setup step: {step}"}
    layout = init_runtime_paths()
    state = load_setup_state(layout)
    handler = _STEP_HANDLERS.get(step)
    if handler is None:
        return {"ok": False, "error": f"No handler for step: {step}"}
    state["current_step"] = step
    state["error"] = ""
    save_setup_state(state, layout)
    combined = _make_progress_logger(layout, progress)
    try:
        handler(progress=combined)
    except Exception as exc:
        state = load_setup_state(layout)
        state["error"] = str(exc)
        _append_setup_log(layout, f"Error: {exc}")
        save_setup_state(state, layout)
        return {"ok": False, "error": str(exc), "step": step, "progress": get_setup_progress()}
    state = load_setup_state(layout)
    _mark_step(state, step)
    save_setup_state(state, layout)
    return {"ok": True, "step": step, "progress": get_setup_progress()}


def run_full_bootstrap(*, progress: ProgressCallback = None) -> dict[str, Any]:
    for step in SETUP_STEPS:
        result = run_bootstrap_step(step, progress=progress)
        if not result.get("ok"):
            return result
    return finalize_setup()


def finalize_setup(config: RuntimeConfig | None = None) -> dict[str, Any]:
    from dreamforge_runtime_paths import LEGACY_SETUP_MARKER

    layout = init_runtime_paths()
    cfg = config or layout.config
    cfg.setup_complete = True
    cfg.setup_version = max(cfg.setup_version, 1)
    cfg.data_root = str(layout.data_root)
    cfg.models_root = str(layout.models_root)
    cfg.comfy_root = str(layout.comfy_root)
    save_runtime_config(cfg, layout.data_root)
    apply = init_runtime_paths()
    for marker_root in (apply.data_root, apply.install_root):
        try:
            (marker_root / LEGACY_SETUP_MARKER).write_text("ok\n", encoding="utf-8")
        except OSError:
            pass
    state = load_setup_state(apply)
    state["error"] = ""
    save_setup_state(state, apply)
    return {
        "ok": True,
        "setup_complete": True,
        "config": cfg.to_dict(),
        "paths": {
            "models_root": str(apply.models_root),
            "data_root": str(apply.data_root),
            "comfy_root": str(apply.comfy_root),
        },
    }


def apply_runtime_preferences(
    *,
    data_root: str | None = None,
    models_root: str | None = None,
    models_source: str = "managed",
    setup_complete: bool | None = None,
) -> dict[str, Any]:
    """Persist user folder choices before or during the setup wizard."""
    current = load_runtime_config(
        Path(data_root).expanduser().resolve() if data_root else None
    )
    root = Path(current.data_root or data_root or build_runtime_layout().data_root).resolve()
    current.data_root = str(root)

    source = str(models_source or current.models_source).lower()
    if source not in {"managed", "external"}:
        source = "managed"
    current.models_source = source  # type: ignore[assignment]

    if source == "managed":
        current.models_root = str(root / "models")
    elif models_root:
        current.models_root = str(Path(models_root).expanduser().resolve())

    if setup_complete is not None:
        current.setup_complete = setup_complete

    current.comfy_root = str((root / "engines" / "comfyui").resolve())
    save_runtime_config(current, root)
    layout = init_runtime_paths()
    validation = validate_models_folder(layout.models_root, create=source == "managed")
    if source == "managed":
        ensure_model_subdirs(layout.models_root)
    return {
        "ok": not bool(validation.get("errors")),
        "config": layout.config.to_dict(),
        "models_validation": validation,
        "paths": {
            "data_root": str(layout.data_root),
            "models_root": str(layout.models_root),
            "comfy_root": str(layout.comfy_root),
        },
    }


def bootstrap_system_info() -> dict[str, Any]:
    layout = build_runtime_layout()
    return {
        "ok": True,
        "system": system_info(layout.data_root),
        "paths": {
            "default_data_root": str(layout.data_root),
            "default_models_root": str(layout.data_root / "models"),
        },
    }


def reset_setup_state(*, clear_markers: bool = False) -> dict[str, Any]:
    """Clear bootstrap progress so setup steps can run again."""
    layout = init_runtime_paths()
    cleared_markers: list[str] = []
    if clear_markers:
        cleared_markers = clear_install_markers()
        custom_nodes = layout.comfy_root / "custom_nodes"
        if custom_nodes.is_dir():
            for pack_dir in custom_nodes.iterdir():
                marker = pack_dir / ".dreamforge_deps_ok"
                if marker.is_file():
                    marker.unlink(missing_ok=True)
                    cleared_markers.append(f"{pack_dir.name}/.dreamforge_deps_ok")
    state = {
        "completed_steps": [],
        "current_step": "",
        "error": "",
        "log_lines": [],
        "current_message": "",
        "recipe_fingerprint": bootstrap_recipe_fingerprint(),
    }
    save_setup_state(state, layout)
    return {
        "ok": True,
        "cleared_markers": cleared_markers,
        "progress": get_setup_progress(),
    }


def repair_installation(*, clear_markers: bool = False) -> dict[str, Any]:
    """Re-run all bootstrap steps (optionally clearing pip/checkout skip markers)."""
    reset_setup_state(clear_markers=clear_markers)
    return run_full_bootstrap()


SETUP_MARKER_PATH = Path(__file__).resolve().parents[1] / ".dreamforge_setup_ok"


def check_first_run_setup() -> dict[str, Any]:
    """Interactive / automated first-run setup wizard triggered when setup marker is absent."""
    if SETUP_MARKER_PATH.exists():
        try:
            with open(SETUP_MARKER_PATH, "r", encoding="utf-8") as f:
                return {"is_first_run": False, **json.load(f)}
        except Exception:
            pass

    from dreamforge_gpu_detect import detect_gpu

    gpu_info = detect_gpu()
    recommended_profile = gpu_info.get("recommended_profile", "16gb")
    os.environ.setdefault("DREAMFORGE_VRAM_PROFILE", recommended_profile)

    layout = init_runtime_paths()

    setup_info = {
        "is_first_run": True,
        "gpu": gpu_info,
        "vram_profile": recommended_profile,
        "models_root": str(layout.models_root),
        "comfy_root": str(layout.comfy_root),
        "setup_time": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    try:
        SETUP_MARKER_PATH.write_text(json.dumps(setup_info, indent=2), encoding="utf-8")
    except Exception:
        pass

    return setup_info


def check_github_updates(current_version: str = "2.0.0") -> dict[str, Any]:
    """Check for latest release on GitHub asynchronously / without blocking."""
    try:
        req = urllib.request.Request(
            "https://api.github.com/repos/mohammednabarawy/DreamForge/releases/latest",
            headers={"User-Agent": "DreamForge-UpdateCheck/1.0"},
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            tag_name = data.get("tag_name", "").lstrip("v")
            return {
                "update_available": tag_name != "" and tag_name != current_version,
                "latest_version": tag_name,
                "current_version": current_version,
                "release_url": data.get("html_url", ""),
            }
    except Exception:
        return {
            "update_available": False,
            "latest_version": current_version,
            "current_version": current_version,
        }

