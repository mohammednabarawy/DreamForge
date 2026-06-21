"""Runtime path layout for dev checkouts and packaged desktop installs.

Separates read-only application code (backend) from mutable user data (models,
outputs, ComfyUI engine, venv). Users may point models at an existing ComfyUI-
compatible folder or use a managed folder under the data root.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

BACKEND_ROOT = Path(__file__).resolve().parent
REPO_ROOT = BACKEND_ROOT.parent

RUNTIME_DIR_NAME = "dreamforge"
RUNTIME_CONFIG_NAME = "runtime.json"
RUNTIME_CONFIG_VERSION = 1
LEGACY_SETUP_MARKER = ".dreamforge_setup_ok"

# Portable Windows runtime folder name (matches setup.bat / dreamforge_env.bat).
EMBED_DIR_NAME = "python_embeded"

ModelsSource = Literal["managed", "external"]

# ComfyUI-compatible model subfolders we create when missing.
MODEL_SUBDIRS: tuple[str, ...] = (
    "checkpoints",
    "clip",
    "clip_vision",
    "controlnet",
    "diffusion_models",
    "embeddings",
    "inpaint",
    "ipadapter",
    "loras",
    "model_patches",
    "style_models",
    "text_encoders",
    "unet",
    "upscale_models",
    "vae",
    "vae_approx",
    "sams",
    "ultralytics",
    "ultralytics/bbox",
    "ultralytics/segm",
    "LLM",
    "configs",
    "faceswap",
    "llm",
    "inbox",
)


@dataclass
class RuntimeConfig:
    version: int = RUNTIME_CONFIG_VERSION
    data_root: str = ""
    models_root: str = ""
    models_source: ModelsSource = "managed"
    setup_complete: bool = False
    setup_version: int = 0
    comfy_root: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> RuntimeConfig:
        source = str(raw.get("models_source") or "managed").lower()
        if source not in {"managed", "external"}:
            source = "managed"
        return cls(
            version=int(raw.get("version") or RUNTIME_CONFIG_VERSION),
            data_root=str(raw.get("data_root") or ""),
            models_root=str(raw.get("models_root") or ""),
            models_source=source,  # type: ignore[arg-type]
            setup_complete=bool(raw.get("setup_complete")),
            setup_version=int(raw.get("setup_version") or 0),
            comfy_root=str(raw.get("comfy_root") or ""),
        )


@dataclass
class RuntimeLayout:
    install_root: Path
    backend_root: Path
    data_root: Path
    models_root: Path
    outputs_root: Path
    comfy_root: Path
    embedded_python_dir: Path
    embedded_python_exe: Path
    runtime_dir: Path
    config_path: Path
    config: RuntimeConfig
    packaged: bool = False
    dev_checkout: bool = False


def _env_path(name: str) -> Path | None:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return None
    return Path(raw).expanduser()


def _is_tauri_build_artifact(path: Path) -> bool:
    lowered = {part.lower() for part in path.parts}
    return "target" in lowered and ("debug" in lowered or "release" in lowered)


def _canonical_install_root() -> Path:
    return REPO_ROOT.resolve()


def _canonical_backend_root() -> Path:
    return BACKEND_ROOT.resolve()


def is_packaged_runtime() -> bool:
    return os.environ.get("DREAMFORGE_PACKAGED", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def resolve_install_root() -> Path:
    """Best install root: repo checkout in dev, env override when packaged."""
    canonical = _canonical_install_root()
    env = _env_path("DREAMFORGE_INSTALL_ROOT")
    if env is not None:
        candidate = env.resolve()
        if (
            not is_packaged_runtime()
            and _is_tauri_build_artifact(candidate)
            and (canonical / EMBED_DIR_NAME / "python.exe").is_file()
        ):
            return canonical
        return candidate
    backend_env = _env_path("DREAMFORGE_BACKEND_ROOT") or _env_path("DREAMFORGE_ROOT")
    if backend_env is not None:
        candidate = backend_env.resolve().parent
        if (
            not is_packaged_runtime()
            and _is_tauri_build_artifact(candidate)
            and (canonical / EMBED_DIR_NAME / "python.exe").is_file()
        ):
            return canonical
        return candidate
    return canonical


def default_data_root() -> Path:
    env = _env_path("DREAMFORGE_DATA_ROOT")
    if env is not None:
        candidate = env.resolve()
        if not is_packaged_runtime() and _is_tauri_build_artifact(candidate):
            return REPO_ROOT.resolve()
        return candidate
    if is_packaged_runtime():
        local = os.environ.get("LOCALAPPDATA", "").strip()
        if local:
            return (Path(local) / "DreamForge").resolve()
        return (Path.home() / ".dreamforge").resolve()
    return REPO_ROOT.resolve()


def default_install_root() -> Path:
    return resolve_install_root()


def default_embedded_python_dir(install_root: Path | None = None) -> Path:
    return (install_root or default_install_root()) / EMBED_DIR_NAME


def default_embedded_python_exe(install_root: Path | None = None) -> Path:
    embed = default_embedded_python_dir(install_root)
    return embed / ("python.exe" if os.name == "nt" else "python")


def default_backend_root() -> Path:
    env = _env_path("DREAMFORGE_BACKEND_ROOT") or _env_path("DREAMFORGE_ROOT")
    canonical = _canonical_backend_root()
    if env is not None:
        candidate = env.resolve()
        if (
            not is_packaged_runtime()
            and _is_tauri_build_artifact(candidate)
            and (canonical / "dreamforge_desktop_bridge.py").is_file()
        ):
            return canonical
        return candidate
    return canonical


def default_comfy_root(data_root: Path, config: RuntimeConfig | None = None) -> Path:
    env = _env_path("DREAMFORGE_COMFY_ROOT")
    if env is not None:
        return env.resolve()
    if config and str(config.comfy_root or "").strip():
        return Path(config.comfy_root).expanduser().resolve()

    managed = (data_root / "engines" / "comfyui").resolve()
    legacy_repo = (BACKEND_ROOT / "repositories" / "ComfyUI").resolve()

    # Packaged / wizard-first: always target data-root engine folder.
    if is_packaged_runtime():
        return managed

    # Dev: prefer managed path when legacy is absent or managed already exists.
    if managed.is_dir() and any(managed.iterdir()):
        return managed
    if legacy_repo.is_dir() and any(legacy_repo.iterdir()) and not managed.is_dir():
        return legacy_repo

    for candidate in (
        REPO_ROOT / "engines" / "comfyui",
        REPO_ROOT / "ComfyUI",
    ):
        if candidate.is_dir() and any(candidate.iterdir()):
            return candidate.resolve()
    return managed


def default_managed_models_root(data_root: Path) -> Path:
    env = _env_path("DREAMFORGE_MODELS_ROOT")
    if env is not None:
        return env.resolve()
    legacy = REPO_ROOT / "models"
    if not is_packaged_runtime() and legacy.is_dir():
        return legacy.resolve()
    return (data_root / "models").resolve()


def runtime_config_path(data_root: Path) -> Path:
    return (data_root / RUNTIME_DIR_NAME / RUNTIME_CONFIG_NAME).resolve()


def _legacy_setup_complete(data_root: Path, install_root: Path | None = None) -> bool:
    data = data_root.resolve()
    if (data / LEGACY_SETUP_MARKER).is_file():
        return True
    install = (install_root or default_install_root()).resolve()
    # Install/repo markers only apply when this data root is the dev checkout layout.
    if data == REPO_ROOT.resolve():
        if (install / LEGACY_SETUP_MARKER).is_file():
            return True
        if not is_packaged_runtime() and (REPO_ROOT / LEGACY_SETUP_MARKER).is_file():
            return True
    return False


def is_provisioned_layout(data_root: Path, install_root: Path, comfy_root: Path) -> bool:
    """Heuristic for dev checkouts that finished setup before runtime.json existed."""
    if _legacy_setup_complete(data_root, install_root):
        return True
    comfy_ok = (comfy_root / "main.py").is_file()
    models_ok = (data_root / "models").is_dir()
    if not models_ok and data_root.resolve() == REPO_ROOT.resolve():
        models_ok = (REPO_ROOT / "models").is_dir()
    repo_embed = REPO_ROOT / EMBED_DIR_NAME / "python.exe"
    if os.name == "nt":
        python_ok = (
            (install_root / EMBED_DIR_NAME / "python.exe").is_file()
            or repo_embed.is_file()
        )
    else:
        python_ok = (install_root / "venv" / "bin" / "python").is_file() or (
            install_root / "venv" / "Scripts" / "python.exe"
        ).is_file()
    return bool(comfy_ok and models_ok and python_ok)


def load_runtime_config(data_root: Path | None = None) -> RuntimeConfig:
    root = (data_root or default_data_root()).resolve()
    path = runtime_config_path(root)
    if path.is_file():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                cfg = RuntimeConfig.from_dict(raw)
                if not cfg.data_root:
                    cfg.data_root = str(root)
                if "setup_complete" not in raw and not cfg.setup_complete:
                    install = default_install_root()
                    comfy = (
                        Path(cfg.comfy_root).resolve()
                        if cfg.comfy_root
                        else default_comfy_root(root, cfg)
                    )
                    if is_provisioned_layout(root, install, comfy):
                        cfg.setup_complete = True
                return cfg
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass

    cfg = RuntimeConfig(
        data_root=str(root),
        models_root=str(default_managed_models_root(root)),
        models_source="managed",
        setup_complete=False,
        comfy_root=str(default_comfy_root(root)),
    )
    install = default_install_root()
    comfy = Path(cfg.comfy_root)
    if is_provisioned_layout(root, install, comfy):
        cfg.setup_complete = True
    return cfg


def save_runtime_config(config: RuntimeConfig, data_root: Path | None = None) -> Path:
    root = Path(config.data_root or (data_root or default_data_root())).resolve()
    config.data_root = str(root)
    runtime_dir = root / RUNTIME_DIR_NAME
    runtime_dir.mkdir(parents=True, exist_ok=True)
    path = runtime_config_path(root)
    path.write_text(
        json.dumps(config.to_dict(), indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    return path


def resolve_models_root(config: RuntimeConfig, data_root: Path) -> Path:
    if config.models_root.strip():
        return Path(config.models_root).expanduser().resolve()
    if config.models_source == "external":
        raise ValueError("External models folder is not configured.")
    return (data_root / "models").resolve()


def validate_models_folder(path: Path, *, create: bool = False) -> dict[str, Any]:
    """Validate a ComfyUI-compatible models directory."""
    target = Path(path).expanduser()
    warnings: list[str] = []
    errors: list[str] = []

    if not target.exists():
        if create:
            try:
                target.mkdir(parents=True, exist_ok=True)
                ensure_model_subdirs(target)
            except OSError as exc:
                errors.append(f"Cannot create folder: {exc}")
                return _validation_result(target, False, warnings, errors)
        else:
            errors.append("Folder does not exist.")
            return _validation_result(target, False, warnings, errors)

    if not target.is_dir():
        errors.append("Path is not a directory.")
        return _validation_result(target, False, warnings, errors)

    resolved = target.resolve()
    lowered = str(resolved).lower()
    if any(token in lowered for token in ("onedrive", "icloud", "dropbox")):
        warnings.append(
            "Cloud-sync folders can cause slow scans and file locks. "
            "A local SSD path is recommended."
        )

    try:
        probe = resolved / ".dreamforge_write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
    except OSError as exc:
        errors.append(f"Folder is not writable: {exc}")
        return _validation_result(resolved, False, warnings, errors)

    known = [name for name in MODEL_SUBDIRS if (resolved / name).is_dir()]
    weight_ext = {".safetensors", ".gguf", ".ckpt", ".pt", ".pth", ".bin"}
    has_weights = any(
        child.is_file() and child.suffix.lower() in weight_ext
        for child in resolved.rglob("*")
        if child.is_file()
    )
    compatible = bool(known) or has_weights or create

    if not compatible and not create:
        warnings.append(
            "No standard ComfyUI subfolders found yet. DreamForge can create them for you."
        )

    # Writable folder is acceptable for setup — warnings do not block install.
    ok = not errors and (compatible or create or resolved.is_dir())
    return _validation_result(resolved, ok, warnings, errors, known=known)


def _validation_result(
    path: Path,
    ok: bool,
    warnings: list[str],
    errors: list[str],
    *,
    known: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "ok": ok and not errors,
        "path": str(path),
        "warnings": warnings,
        "errors": errors,
        "known_subdirs": known or [],
    }


def ensure_model_subdirs(models_root: Path) -> list[str]:
    created: list[str] = []
    root = models_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    for name in MODEL_SUBDIRS:
        folder = root / name
        if not folder.is_dir():
            folder.mkdir(parents=True, exist_ok=True)
            created.append(name)
    return created


def ensure_data_layout(layout: RuntimeLayout) -> dict[str, str]:
    """Create standard folders under the data root."""
    paths = {
        "data_root": str(layout.data_root),
        "models_root": str(layout.models_root),
        "outputs_root": str(layout.outputs_root),
        "comfy_root": str(layout.comfy_root),
        "runtime_dir": str(layout.runtime_dir),
    }
    layout.data_root.mkdir(parents=True, exist_ok=True)
    layout.runtime_dir.mkdir(parents=True, exist_ok=True)
    layout.outputs_root.mkdir(parents=True, exist_ok=True)
    (layout.outputs_root / "dreamforge" / "logs").mkdir(parents=True, exist_ok=True)
    layout.comfy_root.mkdir(parents=True, exist_ok=True)
    ensure_model_subdirs(layout.models_root)
    (layout.backend_root / "cache").mkdir(parents=True, exist_ok=True)
    return paths


def build_runtime_layout(
    config: RuntimeConfig | None = None,
    *,
    data_root: Path | None = None,
) -> RuntimeLayout:
    install = default_install_root()
    backend = default_backend_root()
    root = Path((config.data_root if config else "") or (data_root or default_data_root())).resolve()
    cfg = config or load_runtime_config(root)
    if not cfg.data_root:
        cfg.data_root = str(root)
    data = Path(cfg.data_root).resolve()

    models = resolve_models_root(cfg, data)
    comfy = (
        Path(cfg.comfy_root).resolve()
        if cfg.comfy_root
        else default_comfy_root(data, cfg)
    )
    outputs = data / "outputs"
    runtime_dir = data / RUNTIME_DIR_NAME
    embed_dir = default_embedded_python_dir(install)
    embed_exe = default_embedded_python_exe(install)

    dev_checkout = not is_packaged_runtime() and REPO_ROOT.resolve() == data

    return RuntimeLayout(
        install_root=install,
        backend_root=backend,
        data_root=data,
        models_root=models,
        outputs_root=outputs,
        comfy_root=comfy,
        embedded_python_dir=embed_dir,
        embedded_python_exe=embed_exe,
        runtime_dir=runtime_dir,
        config_path=runtime_config_path(data),
        config=cfg,
        packaged=is_packaged_runtime(),
        dev_checkout=dev_checkout,
    )


def apply_runtime_env(layout: RuntimeLayout | None = None) -> RuntimeLayout:
    """Publish path env vars and refresh ``_paths`` module-level constants."""
    resolved = layout or build_runtime_layout()
    os.environ["DREAMFORGE_INSTALL_ROOT"] = str(resolved.install_root)
    os.environ["DREAMFORGE_BACKEND_ROOT"] = str(resolved.backend_root)
    os.environ["DREAMFORGE_DATA_ROOT"] = str(resolved.data_root)
    os.environ["DREAMFORGE_MODELS_ROOT"] = str(resolved.models_root)
    os.environ["DREAMFORGE_COMFY_ROOT"] = str(resolved.comfy_root)
    if resolved.embedded_python_exe.is_file():
        os.environ["DREAMFORGE_EMBEDDED_PYTHON"] = str(resolved.embedded_python_exe)
    os.environ.setdefault("DREAMFORGE_APP_CONFIG_PATH", str(resolved.runtime_dir / "app-config.json"))

    try:
        from _paths import refresh_path_constants

        refresh_path_constants(resolved)
    except Exception:
        pass
    return resolved


def init_runtime_paths() -> RuntimeLayout:
    layout = build_runtime_layout()
    return apply_runtime_env(layout)


def system_info(data_root: Path | None = None) -> dict[str, Any]:
    root = (data_root or default_data_root()).resolve()
    usage = shutil.disk_usage(root)
    free_gb = round(usage.free / (1024**3), 1)
    total_gb = round(usage.total / (1024**3), 1)
    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python_version": sys.version.split()[0],
        "data_root": str(root),
        "disk_free_gb": free_gb,
        "disk_total_gb": total_gb,
        "disk_ok": free_gb >= 30.0,
        "packaged": is_packaged_runtime(),
    }


def runtime_status() -> dict[str, Any]:
    layout = init_runtime_paths()
    validation = validate_models_folder(layout.models_root, create=False)
    return {
        "ok": True,
        "config": layout.config.to_dict(),
        "paths": {
            "install_root": str(layout.install_root),
            "backend_root": str(layout.backend_root),
            "data_root": str(layout.data_root),
            "models_root": str(layout.models_root),
            "outputs_root": str(layout.outputs_root),
            "comfy_root": str(layout.comfy_root),
            "embedded_python_dir": str(layout.embedded_python_dir),
            "embedded_python": str(layout.embedded_python_exe),
            "config_path": str(layout.config_path),
        },
        "models_validation": validation,
        "system": system_info(layout.data_root),
        "needs_setup_wizard": not layout.config.setup_complete
        and not is_provisioned_layout(layout.data_root, layout.install_root, layout.comfy_root),
    }
