"""Managed ComfyUI server (local subprocess).

This mirrors the "managed Comfy server" approach used by apps like Krita AI Diffusion:
- spawn ComfyUI as a separate process
- talk to it via HTTP + WebSocket API

We keep this intentionally small and dependency-free (stdlib only).
"""

from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from _paths import BACKEND_ROOT, COMFY_ROOT, PYTHON_EXE
from dreamforge_cli_inventory import MODELS_ROOT


_DREAMFORGE_EXTRA_MODEL_PATHS_NAME = "extra_model_paths.dreamforge.yaml"


def resolved_models_root() -> Path:
    """Resolve symlinks/junctions (e.g. backend/models -> krita_server/models)."""
    return Path(MODELS_ROOT).resolve()


def _dreamforge_extra_model_paths_yaml(models_base: Path) -> str:
    base = models_base.as_posix()
    return f"""dreamforge-managed:
    base_path: {base}
    is_default: true
    checkpoints: checkpoints
    clip: |
        clip
        text_encoders
    clip_vision: clip_vision
    controlnet: controlnet
    diffusion_models: |
        diffusion_models
        unet
    embeddings: embeddings
    inpaint: inpaint
    ipadapter: ipadapter
    loras: loras
    model_patches: model_patches
    style_models: style_models
    text_encoders: |
        text_encoders
        clip
    upscale_models: upscale_models
    unet: |
        unet
        diffusion_models
    vae: vae
"""

_MODEL_DIRS = (
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
    "upscale_models",
    "unet",
    "vae",
)


def write_dreamforge_extra_model_paths_config(comfy_root: Path | None = None) -> Path:
    """Write Comfy extra_model_paths YAML with an absolute, symlink-resolved models root."""
    root = Path(comfy_root or COMFY_ROOT)
    root.mkdir(parents=True, exist_ok=True)
    models_root = resolved_models_root()
    models_root.mkdir(parents=True, exist_ok=True)
    for folder in _MODEL_DIRS:
        (models_root / folder).mkdir(parents=True, exist_ok=True)

    block = _dreamforge_extra_model_paths_yaml(models_root).strip() + "\n"
    dreamforge_yaml = root / _DREAMFORGE_EXTRA_MODEL_PATHS_NAME
    dreamforge_yaml.write_text(block, encoding="utf-8")

    # Keep extra_model_paths.yaml in sync for manual Comfy launches from the repo.
    legacy = root / "extra_model_paths.yaml"
    example = root / "extra_model_paths.yaml.example"
    if not legacy.exists() and example.exists():
        legacy.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
    if not legacy.exists():
        legacy.write_text("", encoding="utf-8")
    contents = legacy.read_text(encoding="utf-8")
    if "dreamforge-managed:" in contents:
        contents = re.sub(
            r"(?ms)^dreamforge-managed:.*?(?=^\S|\Z)",
            block,
            contents,
        )
    else:
        contents = contents.rstrip() + "\n\n" + block
    if contents != legacy.read_text(encoding="utf-8"):
        legacy.write_text(contents, encoding="utf-8")
    return dreamforge_yaml


def ensure_dreamforge_extra_model_paths(comfy_root: Path | None = None) -> Path:
    """Backward-compatible alias for write_dreamforge_extra_model_paths_config."""
    return write_dreamforge_extra_model_paths_config(comfy_root)


def _is_port_open(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.2)
        return s.connect_ex((host, port)) == 0


def _pick_free_port(start: int = 8188) -> int:
    if not _is_port_open(start):
        return start
    # Try a small range next to the default.
    for port in range(start + 1, start + 64):
        if not _is_port_open(port):
            return port
    # Last resort: OS-assigned port.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@dataclass
class ComfyServerConfig:
    host: str = "127.0.0.1"
    port: int = 8188
    listen: str = "127.0.0.1"
    log_path: Optional[Path] = None
    extra_args: tuple[str, ...] = ()
    # If set, we pass Comfy a custom output directory (optional).
    output_directory: Optional[Path] = None
    # If set, we pass Comfy a custom input directory (optional).
    input_directory: Optional[Path] = None


class ManagedComfyServer:
    def __init__(self, config: ComfyServerConfig):
        self.config = config
        self.proc: subprocess.Popen | None = None
        self.started_at: float | None = None

    @property
    def base_url(self) -> str:
        return f"http://{self.config.host}:{self.config.port}"

    def is_running(self) -> bool:
        """True only when this manager spawned Comfy and the process is still alive."""
        return self.proc is not None and self.proc.poll() is None

    def start(self, timeout_s: float = 30.0) -> None:
        if self.is_running():
            return

        comfy_main = Path(COMFY_ROOT) / "main.py"
        if not comfy_main.is_file():
            raise FileNotFoundError(
                f"ComfyUI main.py not found at {comfy_main}. "
                "Make sure backend/repositories/ComfyUI is cloned."
            )
        extra_yaml = write_dreamforge_extra_model_paths_config(COMFY_ROOT)

        port = int(self.config.port)
        # Do not attach to a foreign ComfyUI already listening (often missing model paths).
        if _is_port_open(port, host=self.config.listen):
            port = _pick_free_port(port)
        self.config.port = port

        env = os.environ.copy()
        # Ensure Comfy imports resolve.
        env.setdefault("PYTHONUTF8", "1")
        env.setdefault("PYTHONIOENCODING", "utf-8")
        # Prefer local-only server.
        args = [
            str(PYTHON_EXE or sys.executable),
            str(comfy_main),
            "--listen",
            str(self.config.listen),
            "--port",
            str(self.config.port),
            "--extra-model-paths-config",
            str(extra_yaml.resolve()),
        ]

        if self.config.output_directory:
            args += ["--output-directory", str(self.config.output_directory)]
        if self.config.input_directory:
            args += ["--input-directory", str(self.config.input_directory)]
        args += list(self.config.extra_args or ())

        log_path = self.config.log_path
        if log_path is None:
            log_path = BACKEND_ROOT / "outputs" / "dreamforge" / "logs" / "comfy.server.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Windows-friendly: avoid opening a console window.
        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]

        with open(log_path, "a", encoding="utf-8", errors="replace") as log:
            self.proc = subprocess.Popen(
                args,
                cwd=str(COMFY_ROOT),
                env=env,
                stdout=log,
                stderr=log,
                stdin=subprocess.DEVNULL,
                creationflags=creationflags,
            )

        self.started_at = time.time()

        deadline = time.time() + float(timeout_s)
        while time.time() < deadline:
            if self.proc and self.proc.poll() is not None:
                raise RuntimeError(f"ComfyUI server exited early with code {self.proc.returncode}")
            if _is_port_open(self.config.port, host=self.config.host):
                return
            time.sleep(0.25)
        raise TimeoutError(f"ComfyUI server did not open port {self.config.port} within {timeout_s}s")

    def stop(self, timeout_s: float = 10.0) -> None:
        proc = self.proc
        self.proc = None
        if not proc:
            return
        if proc.poll() is not None:
            return
        try:
            proc.terminate()
        except Exception:
            return
        deadline = time.time() + float(timeout_s)
        while time.time() < deadline:
            if proc.poll() is not None:
                return
            time.sleep(0.1)
        try:
            proc.kill()
        except Exception:
            pass


_DEFAULT_SERVER: ManagedComfyServer | None = None


def get_default_comfy_server() -> ManagedComfyServer:
    global _DEFAULT_SERVER
    if _DEFAULT_SERVER is None:
        cfg = ComfyServerConfig()
        _DEFAULT_SERVER = ManagedComfyServer(cfg)
    return _DEFAULT_SERVER


def boot_managed_comfy_server(
    *,
    progress=None,
    timeout_s: float = 120.0,
) -> dict:
    """Start (or attach to) the managed ComfyUI server. Used at desktop worker boot."""
    def _emit(message: str, *, phase: str = "booting") -> None:
        if progress is None:
            return
        progress({"type": "boot_progress", "message": message, "phase": phase})

    _emit("Configuring ComfyUI model paths…")
    ensure_dreamforge_extra_model_paths(COMFY_ROOT)
    _emit("Starting managed ComfyUI server…", phase="starting_comfy")
    server = get_default_comfy_server()
    server.start(timeout_s=float(timeout_s))
    from dreamforge_comfy_client import ComfyClient
    from dreamforge_comfy_models import verify_comfy_model_paths_loaded

    client = ComfyClient(server.base_url)
    verify_comfy_model_paths_loaded(client, models_root=resolved_models_root())
    _emit("ComfyUI is ready", phase="ready")
    return {
        "ready": True,
        "boot_phase": "ready",
        "comfy_url": server.base_url,
        "comfy_port": int(server.config.port),
        "models_root": str(resolved_models_root()),
        "engine": "comfy",
    }


def ensure_comfy_running(*, timeout_s: float = 60.0) -> ManagedComfyServer:
    """Ensure the default managed Comfy server is up (idempotent)."""
    server = get_default_comfy_server()
    if not server.is_running():
        ensure_dreamforge_extra_model_paths(COMFY_ROOT)
        server.start(timeout_s=float(timeout_s))
    return server


def stop_managed_comfy_server(*, timeout_s: float = 10.0) -> None:
    """Stop the managed ComfyUI subprocess."""
    global _DEFAULT_SERVER
    server = _DEFAULT_SERVER
    if server is not None:
        server.stop(timeout_s=float(timeout_s))
    _DEFAULT_SERVER = None

