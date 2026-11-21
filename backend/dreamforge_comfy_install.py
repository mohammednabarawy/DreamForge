"""Manage DreamForge's ComfyUI installation, Python dependencies, custom nodes, and updates.

Cross-platform (Windows ``python_embeded`` + macOS ARM / Linux ``venv``):
- Inspects real on-disk ComfyUI state (git HEAD / tag / dirty status or archive pin)
  instead of relying solely on a potentially stale ``.dreamforge_comfy_pin``.
- Audits ``requirements.txt`` against the active Python interpreter and reports
  missing packages + installed key-package versions.
- Protects compiled GPU wheels (``torch``, ``torchvision``, ``torchaudio``,
  ``xformers``, ``triton``, ``sageattention``, ``nunchaku``) via constraints when
  syncing ComfyUI and custom-node Python dependencies.
- Supports channel-based updates (``recommended``, ``latest_release``,
  ``latest_master``) with pre-update server stop, rollback ref
  (``refs/dreamforge/previous``), and automatic rollback on failure.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import urllib.error
import urllib.request
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
from dreamforge_comfy_ideogram4 import (
    DREAMFORGE_COMFY_VERSION,
    DREAMFORGE_COMFY_VERSION_LABEL,
    IDEOGRAM4_COMFY_VERSION,
)
from dreamforge_krita_recipes import COMFY_INSTALL_RECIPE

ProgressCallback = Callable[[str], None] | None

_COMFY_PIN_FILE = COMFY_PIN_FILE

_GPU_PROTECTED_PACKAGES = frozenset(
    {
        "torch",
        "torchvision",
        "torchaudio",
        "torchsde",
        "xformers",
        "triton",
        "triton-windows",
        "sageattention",
        "nunchaku",
    }
)

_KEY_COMFY_PACKAGES = (
    "torch",
    "comfyui-frontend-package",
    "comfyui-workflow-templates",
    "transformers",
    "safetensors",
    "accelerate",
    "aiohttp",
    "einops",
    "kornia",
    "spandrel",
)


def _report(progress: ProgressCallback, message: str) -> None:
    if progress:
        progress(message)


def _subprocess_kwargs(**extra: Any) -> dict[str, Any]:
    kwargs = dict(extra)
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return kwargs


def _ssl_context():
    try:
        from dreamforge_provider_base import default_ssl_context

        return default_ssl_context()
    except Exception:
        return None


def _run_git(args: list[str], *, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    cmd = ["git", *args]
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        check=check,
        **_subprocess_kwargs(),
    )


def _git_head_sha(dest: Path) -> str:
    if not dest.is_dir() or not (dest / ".git").exists():
        return ""
    try:
        res = _run_git(["-C", str(dest), "rev-parse", "HEAD"], check=True)
        return res.stdout.strip()
    except Exception:
        return ""


def _git_describe_label(dest: Path) -> str:
    if not dest.is_dir() or not (dest / ".git").exists():
        return ""
    try:
        res = _run_git(["-C", str(dest), "describe", "--tags", "--exact-match"], check=False)
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
        res = _run_git(["-C", str(dest), "describe", "--tags", "--always"], check=False)
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass
    return ""


def _git_dirty_files(dest: Path) -> list[str]:
    if not dest.is_dir() or not (dest / ".git").exists():
        return []
    try:
        res = _run_git(
            ["-C", str(dest), "status", "--porcelain", "--untracked-files=no"],
            check=False,
        )
        if res.returncode != 0:
            return []
        return [line.strip() for line in res.stdout.splitlines() if line.strip()]
    except Exception:
        return []


def _git_has_rollback_ref(dest: Path) -> bool:
    if not dest.is_dir() or not (dest / ".git").exists():
        return False
    try:
        res = _run_git(
            ["-C", str(dest), "rev-parse", "--verify", "refs/dreamforge/previous"],
            check=False,
        )
        return res.returncode == 0 and bool(res.stdout.strip())
    except Exception:
        return False


def _git_rollback_sha(dest: Path) -> str:
    if not _git_has_rollback_ref(dest):
        return ""
    try:
        res = _run_git(["-C", str(dest), "rev-parse", "refs/dreamforge/previous"], check=False)
        return res.stdout.strip() if res.returncode == 0 else ""
    except Exception:
        return ""


def _git_checkout(
    url: str,
    dest: Path,
    name: str,
    commit: str,
    *,
    auto_stash_dirty: bool = False,
    progress: ProgressCallback = None,
) -> None:
    """Clone or checkout a pinned commit, recording ``refs/dreamforge/previous``."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.is_dir() or not (dest / ".git").exists():
        _report(progress, f"Cloning {name}…")
        subprocess.check_call(["git", "clone", url, str(dest)], **_subprocess_kwargs())
    else:
        subprocess.check_call(["git", "-C", str(dest), "remote", "set-url", "origin", url], **_subprocess_kwargs())

    dirty = _git_dirty_files(dest)
    if dirty:
        if auto_stash_dirty:
            _report(progress, f"Stashing {len(dirty)} local change(s) in {name} before update…")
            subprocess.check_call(
                ["git", "-C", str(dest), "stash", "push", "-m", "dreamforge-pre-update"],
                **_subprocess_kwargs(),
            )
        else:
            raise RuntimeError(
                f"{name} has {len(dirty)} local modification(s); update stopped without overwriting them."
            )

    _report(progress, f"Fetching updates for {name}…")
    subprocess.check_call(["git", "-C", str(dest), "fetch", "origin", "--tags"], **_subprocess_kwargs())
    if commit:
        subprocess.check_call(
            ["git", "-C", str(dest), "update-ref", "refs/dreamforge/previous", "HEAD"],
            **_subprocess_kwargs(),
        )
        try:
            subprocess.check_call(["git", "-C", str(dest), "checkout", commit], **_subprocess_kwargs())
        except subprocess.CalledProcessError:
            subprocess.check_call(["git", "-C", str(dest), "fetch", "origin", commit], **_subprocess_kwargs())
            subprocess.check_call(["git", "-C", str(dest), "checkout", commit], **_subprocess_kwargs())
    else:
        subprocess.check_call(
            ["git", "-C", str(dest), "update-ref", "refs/dreamforge/previous", "HEAD"],
            **_subprocess_kwargs(),
        )
        subprocess.check_call(["git", "-C", str(dest), "pull", "--ff-only"], **_subprocess_kwargs())


def _git_repo_is_at_commit(dest: Path, commit: str) -> bool:
    if not dest.is_dir() or not (dest / ".git").exists():
        return False
    if not commit:
        return False
    out = _git_head_sha(dest)
    if not out:
        return False
    if out == commit:
        return True
    if len(commit) >= 7 and out.startswith(commit):
        return True
    if len(out) >= 7 and commit.startswith(out):
        return True
    return False


def _active_python_exe() -> Path:
    import _paths
    from dreamforge_bootstrap import _bootstrap_python
    from dreamforge_runtime_paths import build_runtime_layout

    try:
        py = _bootstrap_python(build_runtime_layout())
        if py.is_file():
            return py
    except Exception:
        pass
    return Path(_paths.PYTHON_EXE)


def _normalize_pkg_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name.strip().lower())


def _parse_requirement_names(req_file: Path) -> list[tuple[str, str]]:
    """Parse ``requirements.txt`` into ``(normalized_pkg_name, raw_spec)`` pairs."""
    if not req_file.is_file():
        return []
    entries: list[tuple[str, str]] = []
    for raw_line in req_file.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or line.startswith(("-", "--", "git+", "http://", "https://")):
            continue
        # Strip inline environment markers for quick presence check (evaluated properly in probe).
        base = line.split(";", 1)[0].strip()
        match = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)", base)
        if not match:
            continue
        entries.append((_normalize_pkg_name(match.group(1)), line))
    return entries


_DEPS_AUDIT_SCRIPT = r"""
import importlib.metadata as md, json, re, sys
req_lines = json.loads(sys.argv[1])
key_pkgs = json.loads(sys.argv[2])

def norm(n):
    return re.sub(r"[-_.]+", "-", n.strip().lower())

installed = {}
for dist in md.distributions():
    name = dist.metadata.get("Name") or ""
    if name:
        installed[norm(name)] = dist.version

try:
    from packaging.requirements import Requirement
    has_packaging = True
except Exception:
    has_packaging = False

missing = []
for raw in req_lines:
    if has_packaging:
        try:
            req = Requirement(raw)
            if req.marker and not req.marker.evaluate():
                continue
            pkg = norm(req.name)
            if pkg not in installed:
                missing.append(raw)
                continue
            if req.specifier and installed[pkg]:
                if not req.specifier.contains(installed[pkg], prereleases=True):
                    missing.append(f"{req.name} (installed {installed[pkg]}, need {req.specifier})")
            continue
        except Exception:
            pass
    base = raw.split(";", 1)[0].strip()
    m = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)", base)
    if m and norm(m.group(1)) not in installed:
        missing.append(raw)

key_versions = {k: installed.get(norm(k), "") for k in key_pkgs}
print(json.dumps({"missing": missing, "key_packages": key_versions, "total_installed": len(installed)}))
"""


def audit_comfyui_python_deps(comfy_dir: Path, python: Path | None = None) -> dict[str, Any]:
    """Audit ``COMFY_ROOT/requirements.txt`` against the active Python runtime."""
    py = python or _active_python_exe()
    req_file = comfy_dir / "requirements.txt"
    parsed = _parse_requirement_names(req_file)
    raw_lines = [raw for _, raw in parsed]

    if not py.is_file():
        return {
            "ok": False,
            "deps_synced": False,
            "marker_valid": False,
            "missing_deps": ["Python runtime not found"],
            "key_packages": {},
            "requirements_count": len(raw_lines),
            "python_exe": str(py),
        }

    marker_ok = False
    try:
        from dreamforge_embedded_python import runtime_identity_for_python

        runtime_id = runtime_identity_for_python(py)
        marker_ok = comfy_deps_marker_valid(comfy_dir, runtime_id)
    except Exception:
        marker_ok = comfy_deps_marker_valid(comfy_dir)

    missing: list[str] = []
    key_packages: dict[str, str] = {}
    try:
        res = subprocess.run(
            [
                str(py),
                "-c",
                _DEPS_AUDIT_SCRIPT,
                json.dumps(raw_lines),
                json.dumps(list(_KEY_COMFY_PACKAGES)),
            ],
            capture_output=True,
            text=True,
            timeout=25,
            **_subprocess_kwargs(),
        )
        if res.returncode == 0 and res.stdout.strip():
            payload = json.loads(res.stdout.strip().splitlines()[-1])
            missing = list(payload.get("missing") or [])
            key_packages = dict(payload.get("key_packages") or {})
    except Exception:
        pass

    return {
        "ok": True,
        "deps_synced": (not missing) and (marker_ok or not req_file.is_file()),
        "marker_valid": marker_ok,
        "missing_deps": missing,
        "key_packages": key_packages,
        "requirements_count": len(raw_lines),
        "python_exe": str(py),
    }


def _fetch_github_json(url: str, *, timeout: float = 10.0) -> Any:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "DreamForge-ComfyManager/1.0",
            "Accept": "application/vnd.github+json",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_upstream_comfyui_info() -> dict[str, Any]:
    """Query GitHub for the latest ComfyUI stable release tag + commit SHA."""
    result: dict[str, Any] = {
        "ok": False,
        "latest_tag": "",
        "latest_release_sha": "",
        "published_at": "",
        "latest_master_sha": "",
        "error": "",
    }
    try:
        rel = _fetch_github_json("https://api.github.com/repos/Comfy-Org/ComfyUI/releases/latest")
        tag = str(rel.get("tag_name") or "").strip()
        result["latest_tag"] = tag
        result["published_at"] = str(rel.get("published_at") or "")
        if tag:
            ref = _fetch_github_json(
                f"https://api.github.com/repos/Comfy-Org/ComfyUI/git/ref/tags/{tag}"
            )
            obj = ref.get("object") or {}
            if obj.get("type") == "tag" and obj.get("url"):
                obj = (_fetch_github_json(str(obj["url"])) or {}).get("object") or {}
            result["latest_release_sha"] = str(obj.get("sha") or "")
        master = _fetch_github_json("https://api.github.com/repos/Comfy-Org/ComfyUI/commits/master")
        result["latest_master_sha"] = str(master.get("sha") or "")
        result["ok"] = bool(result["latest_release_sha"] or result["latest_master_sha"])
    except Exception as exc:
        result["error"] = str(exc)
    return result


def inspect_custom_nodes(comfy_dir: Path) -> list[dict[str, Any]]:
    """Inspect all required and installed ComfyUI custom-node packs."""
    custom_nodes_dir = comfy_dir / "custom_nodes"
    required_entries = {
        str(entry["id"]): dict(entry)
        for entry in (COMFY_INSTALL_RECIPE.get("required_custom_nodes") or [])
    }
    optional_entries = {
        str(entry["id"]): dict(entry)
        for entry in (COMFY_INSTALL_RECIPE.get("optional_custom_nodes") or [])
    }
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []

    def _inspect_one(pack_id: str, entry: dict[str, Any] | None, *, required: bool) -> dict[str, Any]:
        dest = custom_nodes_dir / pack_id
        installed = dest.is_dir() and any(dest.iterdir())
        target = str((entry or {}).get("version") or "")
        current = _git_head_sha(dest)
        if not current:
            pin_file = dest / ".dreamforge_archive_pin"
            if pin_file.is_file():
                current = pin_file.read_text(encoding="utf-8").strip()
        req_file = dest / "requirements.txt"
        has_req = req_file.is_file()
        dep_ver = target or current or "unpinned"
        deps_ok = (not has_req) or node_deps_marker_valid(dest, dep_ver) or (
            bool(current) and node_deps_marker_valid(dest, current)
        )
        needs_update = False
        if required and not installed:
            needs_update = True
        elif installed and target and current and not (
            current == target or current.startswith(target[:7]) or target.startswith(current[:7])
        ):
            needs_update = True
        return {
            "id": pack_id,
            "required": required,
            "installed": installed,
            "current": current[:12] if current else "",
            "target": target[:12] if target else "",
            "needs_update": needs_update,
            "has_requirements": has_req,
            "deps_ok": deps_ok if installed else False,
        }

    for pack_id, entry in required_entries.items():
        seen.add(pack_id)
        rows.append(_inspect_one(pack_id, entry, required=True))

    if custom_nodes_dir.is_dir():
        for child in sorted(custom_nodes_dir.iterdir(), key=lambda p: p.name.lower()):
            if not child.is_dir() or child.name.startswith((".", "__")):
                continue
            if child.name in seen:
                continue
            seen.add(child.name)
            rows.append(_inspect_one(child.name, optional_entries.get(child.name), required=False))

    return rows


def inspect_comfyui_installation(*, check_upstream: bool = False) -> dict[str, Any]:
    """Return a rich, truthful diagnostic snapshot of ComfyUI, deps, and custom nodes."""
    import _paths

    comfy_dir = Path(_paths.COMFY_ROOT)
    target = str(COMFY_INSTALL_RECIPE.get("comfy_version") or DREAMFORGE_COMFY_VERSION)
    target_label = str(COMFY_INSTALL_RECIPE.get("comfy_version_label") or DREAMFORGE_COMFY_VERSION_LABEL)

    installed = comfy_dir.is_dir() and (comfy_dir / "main.py").is_file()
    is_git = installed and (comfy_dir / ".git").exists()
    archive_pin_file = comfy_dir / ".dreamforge_archive_pin"

    actual_sha = _git_head_sha(comfy_dir) if is_git else ""
    actual_label = _git_describe_label(comfy_dir) if is_git else ""
    if not actual_sha and archive_pin_file.is_file():
        actual_sha = archive_pin_file.read_text(encoding="utf-8").strip()
    if not actual_sha and _COMFY_PIN_FILE.is_file() and installed:
        actual_sha = _COMFY_PIN_FILE.read_text(encoding="utf-8").strip()

    if not actual_label and actual_sha:
        if actual_sha == target or actual_sha.startswith(target[:12]):
            actual_label = target_label
        else:
            actual_label = actual_sha[:12]

    dirty_files = _git_dirty_files(comfy_dir) if is_git else []
    at_target = bool(
        installed
        and actual_sha
        and (
            actual_sha == target
            or actual_sha.startswith(target[:12])
            or target.startswith(actual_sha[:12])
        )
    )

    deps = audit_comfyui_python_deps(comfy_dir) if installed else {
        "ok": True,
        "deps_synced": False,
        "marker_valid": False,
        "missing_deps": [],
        "key_packages": {},
        "requirements_count": 0,
        "python_exe": str(_active_python_exe()),
    }
    custom_nodes = inspect_custom_nodes(comfy_dir) if installed else []
    required_nodes = [n for n in custom_nodes if n.get("required")]
    nodes_needing_action = [
        n for n in custom_nodes if (n.get("required") and (not n.get("installed") or n.get("needs_update"))) or (n.get("installed") and not n.get("deps_ok"))
    ]

    upstream = fetch_upstream_comfyui_info() if check_upstream else None
    can_rollback = _git_has_rollback_ref(comfy_dir)
    rollback_sha = _git_rollback_sha(comfy_dir) if can_rollback else ""

    needs_update = (not installed) or (not at_target)
    needs_deps_sync = installed and not bool(deps.get("deps_synced"))

    return {
        "ok": True,
        "installed": installed,
        "needs_update": needs_update,
        "needs_deps_sync": needs_deps_sync,
        "current": actual_sha,
        "current_short": actual_sha[:12] if actual_sha else "",
        "current_label": actual_label or (actual_sha[:12] if actual_sha else "Not installed"),
        "target": target,
        "target_short": target[:12],
        "target_label": target_label,
        "install_mode": "git" if is_git else ("archive" if installed else "missing"),
        "comfy_root": str(comfy_dir),
        "python_exe": str(deps.get("python_exe") or _active_python_exe()),
        "dirty": bool(dirty_files),
        "dirty_count": len(dirty_files),
        "deps_synced": bool(deps.get("deps_synced")),
        "missing_deps": list(deps.get("missing_deps") or []),
        "key_packages": dict(deps.get("key_packages") or {}),
        "requirements_count": int(deps.get("requirements_count") or 0),
        "custom_nodes": custom_nodes,
        "required_nodes_ready": sum(1 for n in required_nodes if n.get("installed") and n.get("deps_ok")),
        "required_nodes_total": len(required_nodes),
        "nodes_needing_action": len(nodes_needing_action),
        "can_rollback": can_rollback,
        "rollback_target": rollback_sha[:12] if rollback_sha else "",
        "upstream": upstream,
    }


def _safe_pip_install_requirements(
    python: Path,
    req_file: Path,
    *,
    upgrade_if_needed: bool = True,
    progress: ProgressCallback = None,
) -> None:
    """Install a ``requirements.txt`` while strictly protecting installed GPU wheels."""
    from dreamforge_embedded_python import gpu_stack_snapshot, protected_gpu_install

    if not req_file.is_file():
        return

    # Filter out torch/torchvision/torchaudio lines when a working torch install already exists
    # so pip never attempts to replace a CUDA/ROCm/MPS wheel with a mismatched index build.
    filtered_path: Path | None = None
    try:
        snapshot = gpu_stack_snapshot(python)
        has_working_torch = bool(snapshot.get("working", {}).get("torch"))
    except Exception:
        has_working_torch = False

    install_req = req_file
    tmp_dir: tempfile.TemporaryDirectory[str] | None = None
    if has_working_torch:
        kept_lines: list[str] = []
        skipped: list[str] = []
        for raw_line in req_file.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = raw_line.split("#", 1)[0].strip()
            match = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)", stripped.split(";", 1)[0].strip()) if stripped else None
            if match and _normalize_pkg_name(match.group(1)) in {"torch", "torchvision", "torchaudio"}:
                skipped.append(match.group(1))
                continue
            kept_lines.append(raw_line)
        if skipped:
            tmp_dir = tempfile.TemporaryDirectory(prefix="dreamforge-req-")
            filtered_path = Path(tmp_dir.name) / req_file.name
            filtered_path.write_text("\n".join(kept_lines) + "\n", encoding="utf-8")
            install_req = filtered_path
            _report(progress, f"Preserving active PyTorch stack (skipped {', '.join(sorted(set(skipped)))}).")

    try:
        pip_args = ["-m", "pip", "install", "--disable-pip-version-check"]
        if upgrade_if_needed:
            pip_args.extend(["--upgrade", "--upgrade-strategy", "only-if-needed"])
        pip_args.extend(["-r", str(install_req)])

        _report(progress, f"Installing dependencies from {req_file.name}…")
        with protected_gpu_install(python) as env:
            dry = subprocess.run(
                [str(python), *pip_args, "--dry-run"],
                capture_output=True,
                text=True,
                env=env,
                **_subprocess_kwargs(),
            )
            if dry.returncode != 0:
                detail = (dry.stderr or dry.stdout or "").strip()[-800:]
                raise RuntimeError(f"Dependency resolution failed before install: {detail}")
            run = subprocess.run(
                [str(python), *pip_args],
                capture_output=True,
                text=True,
                env=env,
                **_subprocess_kwargs(),
            )
            if run.returncode != 0:
                detail = (run.stderr or run.stdout or "").strip()[-800:]
                raise RuntimeError(f"pip install failed for {req_file.name}: {detail}")
    finally:
        if tmp_dir is not None:
            tmp_dir.cleanup()


def ensure_comfyui_checkout(
    *,
    progress: ProgressCallback = None,
    target_commit: str | None = None,
    auto_stash_dirty: bool = False,
) -> Path:
    """Clone or checkout the target ComfyUI commit (default: DreamForge recommended pin)."""
    import _paths

    comfy_dir = Path(_paths.COMFY_ROOT)
    target = str(target_commit or COMFY_INSTALL_RECIPE.get("comfy_version") or IDEOGRAM4_COMFY_VERSION)
    current = _COMFY_PIN_FILE.read_text(encoding="utf-8").strip() if _COMFY_PIN_FILE.is_file() else ""

    if comfy_dir.is_dir() and (comfy_dir / "main.py").is_file() and current == target:
        pin_marker = comfy_dir / ".dreamforge_archive_pin"
        if (pin_marker.is_file() and pin_marker.read_text(encoding="utf-8").strip() == target) or _git_repo_is_at_commit(comfy_dir, target):
            return comfy_dir

    _report(progress, f"Updating ComfyUI to {target[:12]}…")
    try:
        _git_checkout(
            str(COMFY_INSTALL_RECIPE["comfy_url"]),
            comfy_dir,
            "ComfyUI",
            target,
            auto_stash_dirty=auto_stash_dirty,
            progress=progress,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as exc:
        _report(progress, f"Git unavailable ({exc}); downloading ComfyUI archive…")
        from dreamforge_bootstrap import checkout_github_commit

        checkout_github_commit(
            str(COMFY_INSTALL_RECIPE["comfy_url"]),
            target,
            comfy_dir,
            progress=progress,
            label="ComfyUI",
        )
    if not comfy_dir.is_dir() or not (comfy_dir / "main.py").is_file():
        raise RuntimeError("ComfyUI checkout failed after install (main.py missing).")

    actual = _git_head_sha(comfy_dir) or target
    _COMFY_PIN_FILE.write_text(f"{actual}\n", encoding="utf-8")
    if COMFY_DEPS_MARKER.is_file():
        COMFY_DEPS_MARKER.unlink(missing_ok=True)
    return comfy_dir


def ensure_comfyui_python_deps(
    *,
    progress: ProgressCallback = None,
    force: bool = False,
) -> None:
    import _paths
    from dreamforge_embedded_python import runtime_identity_for_python

    comfy_dir = Path(_paths.COMFY_ROOT)
    req_file = comfy_dir / "requirements.txt"
    python = _active_python_exe()
    runtime_identity = runtime_identity_for_python(python)

    if not force and comfy_deps_marker_valid(comfy_dir, runtime_identity):
        audit = audit_comfyui_python_deps(comfy_dir, python)
        if not audit.get("missing_deps"):
            return
        _report(
            progress,
            f"Detected {len(audit['missing_deps'])} missing ComfyUI package(s); syncing dependencies…",
        )
    if not req_file.is_file():
        return
    _report(progress, "Installing ComfyUI Python dependencies…")
    _safe_pip_install_requirements(python, req_file, upgrade_if_needed=True, progress=progress)
    write_comfy_deps_marker(comfy_dir, runtime_identity)


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
        _git_checkout(str(entry["url"]), dest, pack_id, version, progress=progress)
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


def _install_custom_node_requirements(
    dest: Path,
    *,
    progress: ProgressCallback = None,
    force: bool = False,
) -> None:
    version = _git_head_sha(dest)
    if not version:
        pin = dest / ".dreamforge_archive_pin"
        if pin.is_file():
            version = pin.read_text(encoding="utf-8").strip()
    version = version or "unpinned"
    req = dest / "requirements.txt"
    if not req.is_file() or (not force and node_deps_marker_valid(dest, version)):
        return
    python = _active_python_exe()
    _report(progress, f"Installing Python dependencies for {dest.name}…")
    _safe_pip_install_requirements(python, req, upgrade_if_needed=False, progress=progress)
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


def sync_comfyui_dependencies(
    *,
    include_custom_nodes: bool = True,
    force: bool = False,
    progress: ProgressCallback = None,
) -> dict[str, Any]:
    """Sync ComfyUI + installed custom-node Python dependencies without changing commits."""
    import _paths

    logs: list[str] = []

    def _log(msg: str) -> None:
        logs.append(msg)
        _report(progress, msg)

    comfy_dir = Path(_paths.COMFY_ROOT)
    if not comfy_dir.is_dir() or not (comfy_dir / "main.py").is_file():
        return {"ok": False, "error": "ComfyUI is not installed yet.", "logs": logs}

    _stop_comfy_if_running(_log)
    try:
        ensure_comfyui_python_deps(progress=_log, force=force)
        synced_nodes: list[str] = []
        if include_custom_nodes:
            custom_nodes = comfy_dir / "custom_nodes"
            if custom_nodes.is_dir():
                for pack_dir in sorted(custom_nodes.iterdir(), key=lambda p: p.name.lower()):
                    if not pack_dir.is_dir() or pack_dir.name.startswith((".", "__")):
                        continue
                    if (pack_dir / "requirements.txt").is_file():
                        _install_custom_node_requirements(pack_dir, progress=_log, force=force)
                        synced_nodes.append(pack_dir.name)
        _refresh_windows_pth_if_needed(_log)
        status = inspect_comfyui_installation(check_upstream=False)
        _log("ComfyUI Python dependencies are synchronized.")
        return {
            "ok": True,
            "needs_comfy_restart": True,
            "synced_nodes": synced_nodes,
            "logs": logs,
            "status": status,
        }
    except Exception as exc:
        _log(f"Error: {exc}")
        return {"ok": False, "error": str(exc), "logs": logs}


def _stop_comfy_if_running(progress: ProgressCallback = None) -> None:
    try:
        from dreamforge_comfy_server import stop_managed_comfy_server

        _report(progress, "Stopping running ComfyUI engine before applying changes…")
        stop_managed_comfy_server(timeout_s=10.0)
    except Exception:
        pass


def _refresh_windows_pth_if_needed(progress: ProgressCallback = None) -> None:
    if os.name != "nt":
        return
    try:
        from dreamforge_embedded_python import refresh_embedded_python_paths
        from dreamforge_runtime_paths import build_runtime_layout

        layout = build_runtime_layout()
        if layout.embedded_python_exe.is_file():
            refresh_embedded_python_paths(layout)
            _report(progress, "Refreshed Windows python_embeded path configuration.")
    except Exception:
        pass


def update_comfyui_backend(
    *,
    channel: str = "recommended",
    update_deps: bool = True,
    update_custom_nodes: bool = True,
    optional_nodes: bool = False,
    force_reinstall_deps: bool = False,
    auto_stash_dirty: bool = False,
    progress: ProgressCallback = None,
) -> dict[str, Any]:
    """Safely update ComfyUI, its Python dependencies, and required custom nodes.

    Channels:
    - ``recommended``: DreamForge's tested pinned release (e.g. ``v0.46.0``).
    - ``latest_release``: Latest official stable release tag from ``Comfy-Org/ComfyUI``.
    - ``latest_master``: Latest commit on ``Comfy-Org/ComfyUI`` ``master``.
    """
    import _paths

    logs: list[str] = []

    def _log(msg: str) -> None:
        logs.append(msg)
        _report(progress, msg)

    norm_channel = (channel or "recommended").strip().lower()
    if norm_channel not in {"recommended", "latest_release", "latest_master"}:
        norm_channel = "recommended"

    target_commit = str(COMFY_INSTALL_RECIPE.get("comfy_version") or DREAMFORGE_COMFY_VERSION)
    target_label = str(COMFY_INSTALL_RECIPE.get("comfy_version_label") or DREAMFORGE_COMFY_VERSION_LABEL)

    if norm_channel in {"latest_release", "latest_master"}:
        _log("Checking GitHub for latest ComfyUI release…")
        upstream = fetch_upstream_comfyui_info()
        if not upstream.get("ok"):
            return {
                "ok": False,
                "error": f"Could not reach GitHub for ComfyUI {norm_channel}: {upstream.get('error') or 'network error'}",
                "logs": logs,
            }
        if norm_channel == "latest_release" and upstream.get("latest_release_sha"):
            target_commit = str(upstream["latest_release_sha"])
            target_label = str(upstream.get("latest_tag") or target_commit[:12])
        elif upstream.get("latest_master_sha"):
            target_commit = str(upstream["latest_master_sha"])
            target_label = f"master@{target_commit[:12]}"

    comfy_dir = Path(_paths.COMFY_ROOT)
    prev_sha = _git_head_sha(comfy_dir)

    _stop_comfy_if_running(_log)
    _log(f"Updating ComfyUI ({norm_channel}: {target_label} / {target_commit[:12]})…")
    try:
        ensure_comfyui_checkout(
            progress=_log,
            target_commit=target_commit,
            auto_stash_dirty=auto_stash_dirty,
        )
        if update_deps:
            ensure_comfyui_python_deps(progress=_log, force=force_reinstall_deps)
        if update_custom_nodes:
            ensure_krita_custom_nodes(progress=_log, optional=optional_nodes)
            if force_reinstall_deps:
                custom_nodes = comfy_dir / "custom_nodes"
                if custom_nodes.is_dir():
                    for pack_dir in sorted(custom_nodes.iterdir(), key=lambda p: p.name.lower()):
                        if pack_dir.is_dir() and (pack_dir / "requirements.txt").is_file():
                            _install_custom_node_requirements(pack_dir, progress=_log, force=True)
        _refresh_windows_pth_if_needed(_log)
        try:
            from dreamforge_comfy_server import write_dreamforge_extra_model_paths_config

            write_dreamforge_extra_model_paths_config(comfy_dir)
        except Exception:
            pass
        status = inspect_comfyui_installation(check_upstream=False)
        _log(f"ComfyUI updated successfully to {status.get('current_label')}.")
        return {
            "ok": True,
            "needs_comfy_restart": True,
            "channel": norm_channel,
            "target": target_commit,
            "target_label": target_label,
            "logs": logs,
            "status": status,
        }
    except Exception as exc:
        _log(f"Update failed: {exc}")
        # Attempt automatic git rollback if we moved HEAD before failing.
        new_sha = _git_head_sha(comfy_dir)
        if prev_sha and new_sha and new_sha != prev_sha:
            try:
                _log(f"Rolling ComfyUI back to previous commit {prev_sha[:12]}…")
                subprocess.check_call(
                    ["git", "-C", str(comfy_dir), "checkout", prev_sha],
                    **_subprocess_kwargs(),
                )
                _COMFY_PIN_FILE.write_text(f"{prev_sha}\n", encoding="utf-8")
                _log("Rollback complete.")
            except Exception as rb_exc:
                _log(f"Automatic rollback failed: {rb_exc}")
        return {"ok": False, "error": str(exc), "logs": logs}


def rollback_comfyui_update(*, progress: ProgressCallback = None) -> dict[str, Any]:
    """Restore ComfyUI to the saved ``refs/dreamforge/previous`` commit and re-sync deps."""
    import _paths

    logs: list[str] = []

    def _log(msg: str) -> None:
        logs.append(msg)
        _report(progress, msg)

    comfy_dir = Path(_paths.COMFY_ROOT)
    prev_sha = _git_rollback_sha(comfy_dir)
    if not prev_sha:
        return {
            "ok": False,
            "error": "No previous ComfyUI update snapshot is available for rollback.",
            "logs": logs,
        }
    _stop_comfy_if_running(_log)
    try:
        _log(f"Rolling ComfyUI back to {prev_sha[:12]}…")
        subprocess.check_call(
            ["git", "-C", str(comfy_dir), "checkout", prev_sha],
            **_subprocess_kwargs(),
        )
        _COMFY_PIN_FILE.write_text(f"{prev_sha}\n", encoding="utf-8")
        if COMFY_DEPS_MARKER.is_file():
            COMFY_DEPS_MARKER.unlink(missing_ok=True)
        ensure_comfyui_python_deps(progress=_log, force=True)
        _refresh_windows_pth_if_needed(_log)
        status = inspect_comfyui_installation(check_upstream=False)
        _log(f"Rolled back ComfyUI to {status.get('current_label')}.")
        return {
            "ok": True,
            "needs_comfy_restart": True,
            "logs": logs,
            "status": status,
        }
    except Exception as exc:
        _log(f"Rollback failed: {exc}")
        return {"ok": False, "error": str(exc), "logs": logs}


def ensure_dreamforge_comfy_backend(*, progress: ProgressCallback = None, optional_nodes: bool = False) -> None:
    """ComfyUI checkout, pip deps, and required custom-node packs."""
    ensure_comfyui_checkout(progress=progress)
    ensure_comfyui_python_deps(progress=progress)
    ensure_krita_custom_nodes(progress=progress, optional=optional_nodes)
