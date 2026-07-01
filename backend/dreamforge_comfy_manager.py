"""ComfyUI-Manager integration (cm-cli) for optional custom nodes and models."""

from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from dreamforge_krita_recipes import COMFY_INSTALL_RECIPE

ProgressCallback = Callable[[str], None] | None

MANAGER_PACK_ID = "ComfyUI-Manager"
MANAGER_REPO_URL = "https://github.com/Comfy-Org/ComfyUI-Manager"
HF_SEGFORMER_B2 = "https://huggingface.co/mattmdjaga/segformer_b2_clothes/resolve/main"

WORKFLOW_MODEL_CATALOG: dict[str, dict[str, Any]] = {
    "segformer_b2_clothes": {
        "id": "segformer_b2_clothes",
        "name": "Segformer B2 Clothes",
        "relative": "segformer_b2_clothes",
        "save_path": "segformer_b2_clothes",
        "type": "segformer",
        "edit_tasks": ["outfit_transfer"],
        "required_nodes": ["LayerMask: SegformerB2ClothesUltra"],
        "min_bytes": 100 * 1024 * 1024,
        "files": [
            {
                "filename": "config.json",
                "url": f"{HF_SEGFORMER_B2}/config.json",
                "min_bytes": 100,
            },
            {
                "filename": "preprocessor_config.json",
                "url": f"{HF_SEGFORMER_B2}/preprocessor_config.json",
                "min_bytes": 100,
            },
            {
                "filename": "model.safetensors",
                "url": f"{HF_SEGFORMER_B2}/model.safetensors",
                "min_bytes": 100 * 1024 * 1024,
            },
        ],
        "manager_metadata": {
            "name": "segformer_b2_clothes",
            "type": "segformer",
            "save_path": "segformer_b2_clothes",
            "url": f"{HF_SEGFORMER_B2}/model.safetensors",
            "filename": "model.safetensors",
        },
    },
    "depth_anything_v2_vitl": {
        "id": "depth_anything_v2_vitl",
        "name": "Depth Anything V2 Large",
        "relative": "../custom_nodes/comfyui_controlnet_aux/ckpts/depth-anything/Depth-Anything-V2-Large",
        "save_path": "../custom_nodes/comfyui_controlnet_aux/ckpts/depth-anything/Depth-Anything-V2-Large",
        "type": "annotator",
        "edit_tasks": ["photo_restore", "cutout_compose", "outfit_transfer", "portrait_master"],
        "required_nodes": ["DepthAnythingV2Preprocessor"],
        "min_bytes": 100 * 1024 * 1024,
        "note": "Depth Anything V2 weights for structure-preserving controls.",
        "files": [
            {
                "filename": "depth_anything_v2_vitl.pth",
                "url": "https://huggingface.co/depth-anything/Depth-Anything-V2-Large/resolve/main/depth_anything_v2_vitl.pth",
                "min_bytes": 1 * 1024 * 1024 * 1024,
            },
        ],
    },
    "lineart_standard": {
        "id": "lineart_standard",
        "name": "Lineart Standard Annotator",
        "relative": "../custom_nodes/comfyui_controlnet_aux/ckpts/lllyasviel/Annotators",
        "save_path": "../custom_nodes/comfyui_controlnet_aux/ckpts/lllyasviel/Annotators",
        "type": "annotator",
        "edit_tasks": ["photo_restore", "cutout_compose", "outfit_transfer"],
        "required_nodes": ["LineartStandardPreprocessor"],
        "min_bytes": 10 * 1024 * 1024,
        "note": "Lineart Standard Annotator weights for edge-preserving controls.",
        "files": [
            {
                "filename": "sk_model.pth",
                "url": "https://huggingface.co/lllyasviel/Annotators/resolve/main/sk_model.pth",
                "min_bytes": 10 * 1024 * 1024,
            },
            {
                "filename": "sk_model2.pth",
                "url": "https://huggingface.co/lllyasviel/Annotators/resolve/main/sk_model2.pth",
                "min_bytes": 10 * 1024 * 1024,
            },
        ],
    },
}


@dataclass
class ManagerInstallResult:
    installed: list[str] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)


class ManagerSecurityError(RuntimeError):
    """ComfyUI-Manager blocked an install due to its security policy."""

    def __init__(self, message: str, *, status_code: int = 403, detail: str = ""):
        super().__init__(message)
        self.status_code = int(status_code)
        self.detail = str(detail or message)


MANAGER_SECURITY_HINT = (
    "ComfyUI-Manager blocked this install. Open ComfyUI → Manager → Settings → Security "
    "and allow the repository, or use DreamForge's pinned pack install when available."
)


def is_manager_security_block(message: str) -> bool:
    text = str(message or "").strip().lower()
    return (
        "security policy" in text
        or "manager_security_blocked" in text
        or "http 403" in text
        or " 403 " in f" {text} "
        or text.startswith("403")
    )


def manager_install_error(pack_id: str, message: str) -> dict[str, str]:
    text = str(message or "").strip() or "install failed"
    if is_manager_security_block(text):
        return {
            "pack_id": pack_id,
            "error": text,
            "code": "manager_security_blocked",
            "hint": MANAGER_SECURITY_HINT,
        }
    return {"pack_id": pack_id, "error": text}


def _report(progress: ProgressCallback, message: str) -> None:
    if progress:
        progress(message)


def make_progress_sink(
    messages: list[str],
    *,
    progress_file: str | Path | None = None,
) -> ProgressCallback:
    """Collect progress lines and optionally append JSONL for UI polling."""
    path = Path(progress_file) if progress_file else None
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")

    def _sink(message: str) -> None:
        text = str(message or "").strip()
        if not text:
            return
        messages.append(text)
        if path is not None:
            payload = json.dumps({"ts": time.time(), "message": text}, ensure_ascii=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(payload + "\n")

    return _sink


def _subprocess_kwargs() -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return kwargs


def manager_directory() -> Path:
    import _paths

    return Path(_paths.COMFY_ROOT) / "custom_nodes" / MANAGER_PACK_ID


def manager_cm_cli_path() -> Path:
    return manager_directory() / "cm-cli.py"


def manager_is_installed() -> bool:
    return manager_cm_cli_path().is_file()


def resolve_pack_install_strategy(
    entry: dict[str, Any] | None,
    pack_id: str,
) -> str:
    """Return ``pinned`` for core recipe packs or ``manager`` for optional/unknown."""
    if isinstance(entry, dict):
        explicit = str(entry.get("install_via") or "").strip().lower()
        if explicit in {"manager", "pinned"}:
            return explicit
    required_ids = {
        str(item.get("id") or "")
        for item in COMFY_INSTALL_RECIPE.get("required_custom_nodes", [])
    }
    optional_ids = {
        str(item.get("id") or "")
        for item in COMFY_INSTALL_RECIPE.get("optional_custom_nodes", [])
    }
    if pack_id in required_ids:
        return "pinned"
    if pack_id in optional_ids:
        return "manager"
    return "manager"


def ensure_comfyui_manager(*, progress: ProgressCallback = None) -> Path:
    """Clone or update ComfyUI-Manager under the managed ComfyUI custom_nodes folder."""
    from dreamforge_comfy_install import _git_checkout

    dest = manager_directory()
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_dir() and manager_cm_cli_path().is_file():
        _report(progress, "ComfyUI-Manager is already present.")
        return dest
    _report(progress, "Installing ComfyUI-Manager…")
    try:
        _git_checkout(MANAGER_REPO_URL, dest, MANAGER_PACK_ID, "")
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        from dreamforge_bootstrap import checkout_github_commit

        checkout_github_commit(
            MANAGER_REPO_URL,
            "main",
            dest,
            progress=progress,
            label=MANAGER_PACK_ID,
        )
    if not manager_cm_cli_path().is_file():
        raise RuntimeError("ComfyUI-Manager installation failed: cm-cli.py not found.")
    return dest


def _run_cm_cli(
    args: list[str],
    *,
    progress: ProgressCallback = None,
) -> subprocess.CompletedProcess[str]:
    import _paths

    ensure_comfyui_manager(progress=progress)
    cli = manager_cm_cli_path()
    python = Path(_paths.PYTHON_EXE)
    cmd = [str(python), str(cli), *args]
    _report(progress, f"ComfyUI-Manager: {' '.join(args)}")
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        **_subprocess_kwargs(),
    )
    captured: list[str] = []
    assert proc.stdout is not None
    for line in proc.stdout:
        text = line.rstrip()
        if text:
            captured.append(text)
            _report(progress, text)
    returncode = proc.wait()
    stdout = "\n".join(captured)
    return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr="")


def install_packs_via_manager(
    pack_ids: list[str],
    *,
    progress: ProgressCallback = None,
    exit_on_fail: bool = False,
) -> ManagerInstallResult:
    """Install custom node packs through cm-cli (registry name or git URL)."""
    result = ManagerInstallResult()
    targets = [str(item).strip() for item in pack_ids if str(item).strip()]
    if not targets:
        return result
    args = ["install", *targets]
    if exit_on_fail:
        args.append("--exit-on-fail")
    completed = _run_cm_cli(args, progress=progress)
    if completed.stdout:
        for line in completed.stdout.splitlines():
            text = line.strip()
            if text:
                result.messages.append(text)
    if completed.stderr:
        for line in completed.stderr.splitlines():
            text = line.strip()
            if text:
                result.messages.append(text)
    if completed.returncode == 0:
        result.installed.extend(targets)
    else:
        detail = (completed.stderr or completed.stdout or "cm-cli install failed").strip()
        for pack_id in targets:
            result.errors.append(manager_install_error(pack_id, detail))
    return result


def _models_root() -> Path:
    from _paths import MODELS_ROOT

    return Path(MODELS_ROOT)


def _comfy_root() -> Path:
    from _paths import COMFY_ROOT

    return Path(COMFY_ROOT)


def _workflow_model_base_path(relative: str) -> Path:
    """Resolve catalog relative paths under models/ or ComfyUI custom_nodes/."""
    rel = str(relative or "").strip().replace("\\", "/")
    if rel.startswith("../custom_nodes/") or rel.startswith("custom_nodes/"):
        return _comfy_root() / rel.removeprefix("../")
    return _models_root() / rel


def workflow_model_catalog_entry(catalog_id: str) -> dict[str, Any] | None:
    entry = WORKFLOW_MODEL_CATALOG.get(str(catalog_id or "").strip())
    return dict(entry) if isinstance(entry, dict) else None


def workflow_model_directory(catalog_id: str) -> Path:
    entry = workflow_model_catalog_entry(catalog_id) or {}
    relative = str(entry.get("relative") or catalog_id).strip()
    return _workflow_model_base_path(relative)


def workflow_model_ready(catalog_id: str) -> bool:
    entry = workflow_model_catalog_entry(catalog_id)
    if not entry:
        return False
    root = workflow_model_directory(catalog_id)
    for spec in entry.get("files") or []:
        if not isinstance(spec, dict):
            continue
        filename = str(spec.get("filename") or "").strip()
        if not filename:
            continue
        path = root / filename
        min_bytes = int(spec.get("min_bytes") or entry.get("min_bytes") or 1024)
        if not path.is_file() or path.stat().st_size < min_bytes:
            return False
    return True


def missing_workflow_model_entries(
    *,
    edit_task: str | None = None,
    missing_nodes: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Return downloadable workflow-model rows for outfit transfer and similar tasks."""
    task = str(edit_task or "").strip().lower()
    wanted_nodes = {str(node).strip() for node in (missing_nodes or []) if str(node).strip()}
    missing: list[dict[str, Any]] = []
    for catalog_id, entry in WORKFLOW_MODEL_CATALOG.items():
        tasks = {str(item).strip().lower() for item in (entry.get("edit_tasks") or [])}
        required_nodes = {
            str(node).strip() for node in (entry.get("required_nodes") or []) if str(node).strip()
        }
        if task and task not in tasks:
            if not wanted_nodes or not (wanted_nodes & required_nodes):
                continue
        elif wanted_nodes and required_nodes and not (wanted_nodes & required_nodes):
            continue
        if workflow_model_ready(catalog_id):
            continue
        primary = next(
            (
                spec
                for spec in (entry.get("files") or [])
                if isinstance(spec, dict)
                and str(spec.get("filename") or "").endswith((".safetensors", ".bin", ".pt", ".pth"))
            ),
            None,
        )
        relative = str(entry.get("relative") or catalog_id)
        filename = str((primary or {}).get("filename") or catalog_id)
        row = {
            "kind": "workflow_model",
            "id": catalog_id,
            "catalog_id": catalog_id,
            "name": str(entry.get("name") or catalog_id),
            "filename": filename,
            "relative": f"{relative}/{filename}",
            "expected_path": str(workflow_model_directory(catalog_id) / filename),
            "category": relative,
            "install_via": "direct",
            "url": str((primary or {}).get("url") or ""),
            "min_bytes": int((primary or {}).get("min_bytes") or entry.get("min_bytes") or 1024 * 1024),
            "note": str(entry.get("note") or f"{catalog_id} required weights for {task or 'ComfyUI'}"),
        }
        from dreamforge_companion_download import companion_download_tier

        row["download_tier"] = companion_download_tier(row)
        missing.append(row)
    return missing


def install_workflow_model_files(
    catalog_id: str,
    *,
    progress: ProgressCallback = None,
) -> ManagerInstallResult:
    """Download all files for a catalog entry into models/{relative}."""
    from dreamforge_companion_download import _download_file

    entry = workflow_model_catalog_entry(catalog_id)
    result = ManagerInstallResult()
    if not entry:
        result.errors.append({"pack_id": catalog_id, "error": "unknown workflow model catalog entry"})
        return result
    dest_root = workflow_model_directory(catalog_id)
    dest_root.mkdir(parents=True, exist_ok=True)
    for spec in entry.get("files") or []:
        if not isinstance(spec, dict):
            continue
        filename = str(spec.get("filename") or "").strip()
        url = str(spec.get("url") or "").strip()
        if not filename or not url:
            continue
        dest = dest_root / filename
        min_bytes = int(spec.get("min_bytes") or 1024)
        if dest.is_file() and dest.stat().st_size >= min_bytes:
            result.messages.append(f"{filename} already present.")
            continue
        _report(progress, f"Downloading {filename} for {catalog_id}…")
        try:
            _download_file(url, dest, min_bytes=min_bytes, progress=progress)
            result.messages.append(f"Downloaded {filename}.")
        except Exception as exc:
            result.errors.append({"pack_id": catalog_id, "error": f"{filename}: {exc}"})
    if not result.errors and workflow_model_ready(catalog_id):
        result.installed.append(catalog_id)
    elif not result.errors:
        result.errors.append(
            {
                "pack_id": catalog_id,
                "error": f"{catalog_id} download finished but the file is missing or too small on disk",
            }
        )
    return result


def _manager_http_json(
    base_url: str,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    *,
    timeout_s: float = 30.0,
) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}{path}"
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        if exc.code == 403 or is_manager_security_block(body):
            raise ManagerSecurityError(
                MANAGER_SECURITY_HINT,
                status_code=int(exc.code or 403),
                detail=body or exc.reason,
            ) from exc
        raise RuntimeError(f"Comfy HTTP {exc.code} {exc.reason}: {body}") from exc
    return json.loads(raw.decode("utf-8", errors="replace") or "{}")


def manager_queue_install_model(
    base_url: str,
    metadata: dict[str, Any],
    *,
    progress: ProgressCallback = None,
) -> None:
    _report(progress, f"Queueing model install via ComfyUI-Manager: {metadata.get('name') or metadata.get('filename')}")
    _manager_http_json(base_url, "POST", "/manager/queue/install_model", metadata)


def get_manager_queue_status(base_url: str | None = None) -> dict[str, Any]:
    """Read ComfyUI-Manager queue status when ComfyUI is running."""
    url = base_url
    if not url:
        from dreamforge_comfy_server import probe_comfy_http_base_url

        url = probe_comfy_http_base_url(timeout_s=4.0)
    if not url:
        return {"ok": False, "error": "comfy_not_running"}
    try:
        status = _manager_http_json(url, "GET", "/manager/queue/status")
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "base_url": url, "status": status}


def poll_manager_queue(
    base_url: str,
    *,
    timeout_s: float = 600.0,
    progress: ProgressCallback = None,
) -> dict[str, Any]:
    deadline = time.monotonic() + max(5.0, float(timeout_s))
    last_done = -1
    while time.monotonic() < deadline:
        status = _manager_http_json(base_url, "GET", "/manager/queue/status")
        done = int(status.get("done_count") or 0)
        total = int(status.get("total_count") or 0)
        if done != last_done:
            _report(progress, f"ComfyUI-Manager queue: {done}/{total} complete.")
            last_done = done
        if total > 0 and done >= total and not status.get("is_processing"):
            return status
        if total == 0 and not status.get("is_processing"):
            return status
        time.sleep(1.5)
    raise TimeoutError("Timed out waiting for ComfyUI-Manager model install queue.")


def install_workflow_models(
    catalog_ids: list[str],
    *,
    progress: ProgressCallback = None,
    prefer_manager: bool = True,
) -> ManagerInstallResult:
    """Install workflow models via Manager HTTP when ComfyUI is up, else direct HF download."""
    result = ManagerInstallResult()
    targets = [str(item).strip() for item in catalog_ids if str(item).strip()]
    if not targets:
        return result

    base_url = None
    if prefer_manager:
        try:
            from dreamforge_comfy_server import probe_comfy_http_base_url

            base_url = probe_comfy_http_base_url(timeout_s=4.0)
        except Exception:
            base_url = None

    for catalog_id in targets:
        entry = workflow_model_catalog_entry(catalog_id)
        if not entry:
            result.errors.append({"pack_id": catalog_id, "error": "unknown workflow model catalog entry"})
            continue
        if workflow_model_ready(catalog_id):
            result.messages.append(f"{catalog_id} is already installed.")
            result.installed.append(catalog_id)
            continue

        manager_meta = entry.get("manager_metadata")
        used_manager = False
        if prefer_manager and base_url and isinstance(manager_meta, dict):
            try:
                manager_queue_install_model(base_url, dict(manager_meta), progress=progress)
                poll_manager_queue(base_url, progress=progress)
                if workflow_model_ready(catalog_id):
                    result.installed.append(catalog_id)
                    result.messages.append(f"Installed {catalog_id} via ComfyUI-Manager.")
                    used_manager = True
            except ManagerSecurityError as exc:
                result.messages.append(str(exc))
                result.errors.append(
                    manager_install_error(catalog_id, exc.detail or str(exc)),
                )
            except Exception as exc:
                result.messages.append(
                    f"Manager install for {catalog_id} failed, falling back to direct download: {exc}"
                )

        if used_manager:
            continue

        file_result = install_workflow_model_files(catalog_id, progress=progress)
        result.messages.extend(file_result.messages)
        result.errors.extend(file_result.errors)
        result.installed.extend(file_result.installed)

    return result


def fix_packs_via_manager(
    pack_ids: list[str],
    *,
    progress: ProgressCallback = None,
) -> ManagerInstallResult:
    """Run cm-cli fix to repair Python deps for installed custom nodes."""
    result = ManagerInstallResult()
    targets = [str(item).strip() for item in pack_ids if str(item).strip()]
    if not targets:
        return result
    completed = _run_cm_cli(["fix", *targets], progress=progress)
    if completed.stdout:
        result.messages.extend(line.strip() for line in completed.stdout.splitlines() if line.strip())
    if completed.stderr:
        result.messages.extend(line.strip() for line in completed.stderr.splitlines() if line.strip())
    if completed.returncode == 0:
        result.installed.extend(targets)
    else:
        detail = (completed.stderr or completed.stdout or "cm-cli fix failed").strip()
        for pack_id in targets:
            result.errors.append(manager_install_error(pack_id, detail))
    return result
