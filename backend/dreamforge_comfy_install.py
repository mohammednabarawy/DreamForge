"""Ensure DreamForge's managed ComfyUI checkout and Krita recipe custom-node packs."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, Callable

from _paths import BACKEND_ROOT
from dreamforge_bootstrap_markers import (
    COMFY_DEPS_MARKER,
    COMFY_PIN_FILE,
    comfy_deps_marker_valid,
    node_deps_marker_valid,
    write_comfy_deps_marker,
    write_node_deps_marker,
)
from dreamforge_comfy_ideogram4 import IDEOGRAM4_COMFY_VERSION
from dreamforge_krita_recipes import COMFY_INSTALL_RECIPE

ProgressCallback = Callable[[str], None] | None

_COMFY_PIN_FILE = COMFY_PIN_FILE


def _report(progress: ProgressCallback, message: str) -> None:
    if progress:
        progress(message)


def _git_checkout(url: str, dest: Path, name: str, commit: str) -> None:
    """Clone or checkout a pinned commit."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.is_dir() or not (dest / ".git").is_dir():
        subprocess.check_call(["git", "clone", url, str(dest)])
    else:
        subprocess.check_call(["git", "-C", str(dest), "remote", "set-url", "origin", url])
    subprocess.check_call(["git", "-C", str(dest), "fetch", "origin", "--tags"])
    if commit:
        subprocess.check_call(["git", "-C", str(dest), "reset", "--hard"])
        try:
            subprocess.check_call(["git", "-C", str(dest), "checkout", commit])
        except subprocess.CalledProcessError:
            subprocess.check_call(["git", "-C", str(dest), "fetch", "origin", commit])
            subprocess.check_call(["git", "-C", str(dest), "checkout", commit])
    else:
        subprocess.check_call(["git", "-C", str(dest), "pull", "--ff-only"])


def ensure_comfyui_checkout(*, progress: ProgressCallback = None) -> Path:
    """Clone or checkout the pinned ComfyUI commit (includes Ideogram 4 core nodes)."""
    import _paths

    comfy_dir = Path(_paths.COMFY_ROOT)
    target = COMFY_INSTALL_RECIPE.get("comfy_version") or IDEOGRAM4_COMFY_VERSION
    current = _COMFY_PIN_FILE.read_text(encoding="utf-8").strip() if _COMFY_PIN_FILE.is_file() else ""

    if comfy_dir.is_dir() and any(comfy_dir.iterdir()) and current == target:
        pin_marker = comfy_dir / ".dreamforge_archive_pin"
        if pin_marker.is_file() or _git_repo_is_at_commit(comfy_dir, str(target)):
            return comfy_dir

    _report(progress, f"Updating ComfyUI to {target[:12]}…")
    try:
        _git_checkout(COMFY_INSTALL_RECIPE["comfy_url"], comfy_dir, "ComfyUI", str(target))
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as exc:
        _report(progress, f"Git unavailable ({exc}); downloading ComfyUI archive…")
        from dreamforge_bootstrap import checkout_github_commit

        checkout_github_commit(
            str(COMFY_INSTALL_RECIPE["comfy_url"]),
            str(target),
            comfy_dir,
            progress=progress,
            label="ComfyUI",
        )
    if not comfy_dir.is_dir() or not any(comfy_dir.iterdir()):
        raise RuntimeError("ComfyUI checkout failed after install.")

    _COMFY_PIN_FILE.write_text(f"{target}\n", encoding="utf-8")
    if COMFY_DEPS_MARKER.is_file():
        COMFY_DEPS_MARKER.unlink()
    return comfy_dir


def ensure_comfyui_python_deps(*, progress: ProgressCallback = None) -> None:
    import _paths

    comfy_dir = Path(_paths.COMFY_ROOT)
    req_file = comfy_dir / "requirements.txt"
    if comfy_deps_marker_valid(comfy_dir):
        return
    if not req_file.is_file():
        return
    _report(progress, "Installing ComfyUI Python dependencies…")
    python = Path(_paths.PYTHON_EXE)
    kwargs: dict = {}
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.check_call(
        [str(python), "-m", "pip", "install", "--quiet", "-r", str(req_file)],
        **kwargs,
    )
    write_comfy_deps_marker(comfy_dir)


def _git_repo_is_at_commit(dest: Path, commit: str) -> bool:
    if not dest.is_dir() or not (dest / ".git").is_dir():
        return False
    if not commit:
        return False
    try:
        out = subprocess.check_output(
            ["git", "-C", str(dest), "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        if out == commit:
            return True
        if len(commit) >= 7 and out.startswith(commit):
            return True
        if len(out) >= 7 and commit.startswith(out):
            return True
        return False
    except Exception:
        return False


def ensure_custom_node_pack(entry: dict[str, Any], *, progress: ProgressCallback = None) -> None:
    import _paths

    pack_id = str(entry["id"])
    custom_nodes = Path(_paths.COMFY_ROOT) / "custom_nodes"
    custom_nodes.mkdir(parents=True, exist_ok=True)
    dest = custom_nodes / pack_id
    version = str(entry.get("version") or "")
    if _git_repo_is_at_commit(dest, version):
        _install_custom_node_requirements(dest, progress=progress)
        return
    pin_marker = dest / ".dreamforge_archive_pin"
    if pin_marker.is_file() and pin_marker.read_text(encoding="utf-8").strip() == version:
        _install_custom_node_requirements(dest, progress=progress)
        return
    _report(progress, f"Installing custom node pack {pack_id}…")
    try:
        _git_checkout(str(entry["url"]), dest, pack_id, version)
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        from dreamforge_bootstrap import checkout_github_commit

        checkout_github_commit(
            str(entry["url"]),
            version,
            dest,
            progress=progress,
            label=pack_id,
        )
    _install_custom_node_requirements(dest, progress=progress)


def _install_custom_node_requirements(dest: Path, *, progress: ProgressCallback = None) -> None:
    from dreamforge_bootstrap import _bootstrap_python, _pip_install
    from dreamforge_runtime_paths import init_runtime_paths

    version = ""
    pin = dest / ".dreamforge_archive_pin"
    if pin.is_file():
        version = pin.read_text(encoding="utf-8").strip()
    req = dest / "requirements.txt"
    if not req.is_file() or node_deps_marker_valid(dest, version):
        return
    layout = init_runtime_paths()
    python = _bootstrap_python(layout)
    _report(progress, f"Installing Python dependencies for {dest.name}…")
    _pip_install(python, ["-r", str(req)], progress=progress)
    write_node_deps_marker(dest, version)


def ensure_krita_custom_nodes(*, progress: ProgressCallback = None, optional: bool = False) -> None:
    from dreamforge_comfy_manager import install_packs_via_manager, resolve_pack_install_strategy

    packs = list(COMFY_INSTALL_RECIPE.get("required_custom_nodes") or [])
    if optional:
        packs.extend(COMFY_INSTALL_RECIPE.get("optional_custom_nodes") or [])
    manager_ids: list[str] = []
    for entry in packs:
        pack_id = str(entry.get("id") or "")
        if resolve_pack_install_strategy(entry, pack_id) == "manager":
            manager_ids.append(pack_id)
        else:
            ensure_custom_node_pack(entry, progress=progress)
    if manager_ids:
        result = install_packs_via_manager(manager_ids, progress=progress)
        if result.errors:
            failed = ", ".join(item.get("pack_id", "?") for item in result.errors)
            raise RuntimeError(f"ComfyUI-Manager install failed for: {failed}")


def ensure_dreamforge_comfy_backend(*, progress: ProgressCallback = None, optional_nodes: bool = False) -> None:
    """ComfyUI checkout, pip deps, and required custom-node packs."""
    ensure_comfyui_checkout(progress=progress)
    ensure_comfyui_python_deps(progress=progress)
    ensure_krita_custom_nodes(progress=progress, optional=optional_nodes)
