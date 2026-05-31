"""Managed ComfyUI server (local subprocess).

This mirrors the "managed Comfy server" approach used by apps like Krita AI Diffusion:
- spawn ComfyUI as a separate process
- talk to it via HTTP + WebSocket API

We keep this intentionally small and dependency-free (stdlib only).
"""

from __future__ import annotations

import atexit
import json
import os
import re
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from _paths import BACKEND_ROOT, COMFY_ROOT, PYTHON_EXE
from dreamforge_cli_inventory import MODELS_ROOT


_DREAMFORGE_EXTRA_MODEL_PATHS_NAME = "extra_model_paths.dreamforge.yaml"
_COMFY_PIDFILE = BACKEND_ROOT / "outputs" / "dreamforge" / "logs" / "comfy.server.pid"
_COMFY_DEFAULT_PORT = 8188
_COMFY_PORT_SCAN_RANGE = 64
_shutdown_registered = False


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
    sams: sams
    ultralytics: ultralytics
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
    "sams",
    "ultralytics",
    "ultralytics/bbox",
    "ultralytics/segm",
)

# Impact Subpack registers ultralytics_bbox relative to ComfyUI/models at import time.
_COMFY_MODELS_MIRROR_DIRS = ("ultralytics",)


def _create_dir_link(link: Path, target: Path) -> None:
    target = target.resolve()
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.symlink(target, link, target_is_directory=True)
        return
    except OSError:
        pass
    if os.name == "nt":
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            check=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return
    raise OSError(f"Unable to link {link} -> {target}")


def _mirror_models_into_comfy_tree(comfy_root: Path, models_root: Path) -> None:
    """Mirror shared model folders into ComfyUI/models for custom nodes that ignore extra_model_paths."""
    local_root = Path(comfy_root) / "models"
    local_root.mkdir(parents=True, exist_ok=True)
    for name in _COMFY_MODELS_MIRROR_DIRS:
        target = Path(models_root) / name
        if not target.exists():
            continue
        link = local_root / name
        if link.exists() or link.is_symlink():
            continue
        _create_dir_link(link, target)


def write_dreamforge_extra_model_paths_config(comfy_root: Path | None = None) -> Path:
    """Write Comfy extra_model_paths YAML with an absolute, symlink-resolved models root."""
    root = Path(comfy_root or COMFY_ROOT)
    root.mkdir(parents=True, exist_ok=True)
    models_root = resolved_models_root()
    models_root.mkdir(parents=True, exist_ok=True)
    for folder in _MODEL_DIRS:
        (models_root / folder).mkdir(parents=True, exist_ok=True)
    _mirror_models_into_comfy_tree(root, models_root)

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


def parse_comfy_startup_url(line: str) -> str | None:
    """Parse Comfy stdout line: 'To see the GUI go to: http://127.0.0.1:8188' (Krita-style)."""
    text = (line or "").strip()
    if not text.startswith("To see the GUI go to:"):
        return None
    url = text.split("http://", 1)[-1].strip()
    if not url.startswith("http"):
        url = f"http://{url}"
    return url.rstrip("/")


def _read_comfy_url_from_log(log_path: Path, *, tail_lines: int = 80) -> str | None:
    if not log_path.is_file():
        return None
    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    for line in reversed(lines[-tail_lines:]):
        url = parse_comfy_startup_url(line)
        if url:
            return url
    return None


def _comfy_pidfile_path() -> Path:
    return _COMFY_PIDFILE


def _write_comfy_pidfile(pid: int) -> None:
    path = _comfy_pidfile_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(int(pid)), encoding="utf-8")


def _clear_comfy_pidfile() -> None:
    try:
        _comfy_pidfile_path().unlink(missing_ok=True)
    except OSError:
        pass


def _process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        if not handle:
            return False
        try:
            exit_code = ctypes.c_ulong()
            if not ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return False
            return int(exit_code.value) == STILL_ACTIVE
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _terminate_process_tree(pid: int, *, force: bool = False) -> None:
    if pid <= 0:
        return
    if os.name == "nt":
        args = ["taskkill", "/PID", str(int(pid)), "/T"]
        if force:
            args.append("/F")
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.run(
            args,
            capture_output=True,
            creationflags=creationflags,
            check=False,
        )
        return
    sig = signal.SIGKILL if force else signal.SIGTERM
    try:
        os.killpg(os.getpgid(pid), sig)
        return
    except (ProcessLookupError, PermissionError, OSError):
        pass
    try:
        os.kill(pid, sig)
    except (ProcessLookupError, PermissionError, OSError):
        pass


def cleanup_stale_managed_comfy(*, force: bool = True) -> None:
    """Stop a ComfyUI process left behind by a crashed worker (pidfile)."""
    path = _comfy_pidfile_path()
    if not path.is_file():
        return
    try:
        pid = int(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        _clear_comfy_pidfile()
        return
    if _process_alive(pid):
        _terminate_process_tree(pid, force=force)
    _clear_comfy_pidfile()


def _is_comfy_http_server(port: int, host: str = "127.0.0.1") -> bool:
    url = f"http://{host}:{int(port)}/system_stats"
    try:
        with urllib.request.urlopen(url, timeout=1.5) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="replace"))
    except (OSError, urllib.error.URLError, ValueError, json.JSONDecodeError):
        return False
    return isinstance(payload, dict) and ("system" in payload or "devices" in payload)


def _localhost_listening_pids(port: int) -> list[int]:
    port = int(port)
    pids: list[int] = []
    if os.name == "nt":
        try:
            proc = subprocess.run(
                ["netstat", "-ano", "-p", "tcp"],
                capture_output=True,
                text=True,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except OSError:
            return []
        suffix = f":{port}"
        for line in proc.stdout.splitlines():
            if "LISTENING" not in line.upper():
                continue
            parts = line.split()
            if len(parts) < 5:
                continue
            local_addr = parts[1]
            if not local_addr.endswith(suffix):
                continue
            host_part = local_addr.rsplit(":", 1)[0].strip("[]")
            if host_part not in {"127.0.0.1", "0.0.0.0", "::1", "[::]"}:
                continue
            try:
                pids.append(int(parts[-1]))
            except ValueError:
                continue
        return list(dict.fromkeys(pids))

    for cmd in (
        ["ss", "-H", "-ltnp", f"sport = :{port}"],
        ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
    ):
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        except OSError:
            continue
        if proc.returncode != 0:
            continue
        if cmd[0] == "lsof":
            for token in proc.stdout.split():
                try:
                    pids.append(int(token.strip()))
                except ValueError:
                    continue
            if pids:
                return list(dict.fromkeys(pids))
            continue
        for line in proc.stdout.splitlines():
            match = re.search(r"pid=(\d+)", line)
            if match:
                pids.append(int(match.group(1)))
        if pids:
            return list(dict.fromkeys(pids))
    return list(dict.fromkeys(pids))


def _pids_running_comfy_main(comfy_root: Path | None = None) -> list[int]:
    root = Path(comfy_root or COMFY_ROOT).resolve()
    main_py = (root / "main.py").resolve()
    root_token = str(root).replace("'", "''")
    main_token = str(main_py).replace("'", "''")
    pids: list[int] = []

    if os.name == "nt":
        ps_cmd = (
            "Get-CimInstance Win32_Process | "
            "Where-Object { $_.CommandLine -like '*main.py*' -and "
            f"($_.CommandLine -like '*{root_token}*' -or $_.CommandLine -like '*ComfyUI*') }} | "
            "Select-Object -ExpandProperty ProcessId"
        )
        try:
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except OSError:
            return []
        for line in proc.stdout.splitlines():
            line = line.strip()
            if line.isdigit():
                pids.append(int(line))
        return list(dict.fromkeys(pids))

    try:
        proc = subprocess.run(
            ["ps", "-eo", "pid,args"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return []
    for line in proc.stdout.splitlines()[1:]:
        parts = line.strip().split(None, 1)
        if len(parts) != 2:
            continue
        pid_str, args = parts
        if "main.py" not in args:
            continue
        if str(main_py) not in args and str(root) not in args and "ComfyUI" not in args:
            continue
        try:
            pids.append(int(pid_str))
        except ValueError:
            continue
    return list(dict.fromkeys(pids))


def _find_foreign_comfy_pids(*, exclude_pids: set[int] | None = None) -> list[int]:
    exclude = {int(p) for p in (exclude_pids or set()) if int(p) > 0}
    exclude.add(os.getpid())
    found: set[int] = set()

    for pid in _pids_running_comfy_main(COMFY_ROOT):
        if pid not in exclude:
            found.add(pid)

    for port in range(_COMFY_DEFAULT_PORT, _COMFY_DEFAULT_PORT + _COMFY_PORT_SCAN_RANGE):
        if not _is_port_open(port, host="127.0.0.1"):
            continue
        if not _is_comfy_http_server(port, host="127.0.0.1"):
            continue
        for pid in _localhost_listening_pids(port):
            if pid not in exclude:
                found.add(pid)

    path = _comfy_pidfile_path()
    if path.is_file():
        try:
            pid = int(path.read_text(encoding="utf-8").strip())
            if pid not in exclude:
                found.add(pid)
        except (OSError, ValueError):
            pass

    return sorted(found)


def _wait_for_ports_closed(ports: range, *, timeout_s: float = 8.0) -> None:
    deadline = time.time() + float(timeout_s)
    while time.time() < deadline:
        if not any(_is_port_open(port, host="127.0.0.1") for port in ports):
            return
        time.sleep(0.15)


def cleanup_all_foreign_comfy_servers(
    *,
    force: bool = True,
    exclude_pids: set[int] | None = None,
) -> list[int]:
    """Stop every local ComfyUI instance so DreamForge can own the managed server."""
    killed: list[int] = []
    for pid in _find_foreign_comfy_pids(exclude_pids=exclude_pids):
        if not _process_alive(pid):
            continue
        _terminate_process_tree(pid, force=force)
        killed.append(pid)
    _clear_comfy_pidfile()
    _wait_for_ports_closed(
        range(_COMFY_DEFAULT_PORT, _COMFY_DEFAULT_PORT + _COMFY_PORT_SCAN_RANGE),
        timeout_s=8.0 if killed else 1.0,
    )
    return killed


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
        self.pid: int | None = None
        self.started_at: float | None = None

    @property
    def base_url(self) -> str:
        return f"http://{self.config.host}:{self.config.port}"

    def is_running(self) -> bool:
        """True only when this manager spawned Comfy and the process is still alive."""
        return self.proc is not None and self.proc.poll() is None

    def discard_dead_process(self) -> None:
        """Drop handles for a Comfy subprocess that already exited."""
        proc = self.proc
        if proc is not None and proc.poll() is not None:
            self.proc = None
            self.pid = None
            _clear_comfy_pidfile()

    def start(self, timeout_s: float = 30.0) -> None:
        if self.is_running():
            return
        self.discard_dead_process()

        exclude: set[int] = {os.getpid()}
        if self.pid and _process_alive(self.pid):
            exclude.add(int(self.pid))
        stopped = cleanup_all_foreign_comfy_servers(force=True, exclude_pids=exclude)
        if stopped:
            print(
                f"[DreamForge] Stopped {len(stopped)} existing local ComfyUI instance(s) "
                f"before starting managed server (PIDs: {', '.join(map(str, stopped))})",
                file=sys.stderr,
            )

        comfy_main = Path(COMFY_ROOT) / "main.py"
        if not comfy_main.is_file():
            raise FileNotFoundError(
                f"ComfyUI main.py not found at {comfy_main}. "
                "Make sure backend/repositories/ComfyUI is cloned."
            )
        extra_yaml = write_dreamforge_extra_model_paths_config(COMFY_ROOT)

        port = int(self.config.port)
        if _is_port_open(port, host=self.config.listen):
            cleanup_all_foreign_comfy_servers(force=True, exclude_pids=exclude)
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
            "--preview-method",
            "auto",
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

        popen_kwargs: dict = {
            "args": args,
            "cwd": str(COMFY_ROOT),
            "env": env,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
            "stdin": subprocess.DEVNULL,
            "creationflags": creationflags,
        }
        if os.name != "nt":
            popen_kwargs["start_new_session"] = True

        self.proc = subprocess.Popen(**popen_kwargs)
        self.pid = int(self.proc.pid)
        _write_comfy_pidfile(self.pid)

        def _pump_output() -> None:
            assert self.proc is not None and self.proc.stdout is not None
            with open(log_path, "a", encoding="utf-8", errors="replace") as log:
                for chunk in iter(self.proc.stdout.readline, b""):
                    try:
                        log.write(chunk.decode("utf-8", errors="replace"))
                        log.flush()
                    except (OSError, ValueError):
                        break

        import threading

        threading.Thread(target=_pump_output, name="comfy-log-pump", daemon=True).start()

        self.started_at = time.time()
        register_managed_comfy_shutdown()

        deadline = time.time() + float(timeout_s)
        while time.time() < deadline:
            if self.proc and self.proc.poll() is not None:
                raise RuntimeError(f"ComfyUI server exited early with code {self.proc.returncode}")
            if log_path.is_file():
                parsed = _read_comfy_url_from_log(log_path)
                if parsed:
                    try:
                        from urllib.parse import urlparse

                        hostport = urlparse(parsed).netloc
                        if hostport and ":" in hostport:
                            _host, _port = hostport.rsplit(":", 1)
                            if _host in (self.config.host, self.config.listen, "127.0.0.1", "localhost"):
                                self.config.port = int(_port)
                    except ValueError:
                        pass
            if _is_port_open(self.config.port, host=self.config.host):
                return
            time.sleep(0.25)
        raise TimeoutError(f"ComfyUI server did not open port {self.config.port} within {timeout_s}s")

    def stop(self, timeout_s: float = 10.0) -> None:
        proc = self.proc
        pid = self.pid or (proc.pid if proc else None)
        self.proc = None
        self.pid = None
        if not proc and not pid:
            _clear_comfy_pidfile()
            return
        if proc and proc.poll() is not None:
            _clear_comfy_pidfile()
            return
        try:
            if proc:
                proc.terminate()
            elif pid:
                _terminate_process_tree(int(pid), force=False)
        except Exception:
            pass
        deadline = time.time() + float(timeout_s)
        while time.time() < deadline:
            if proc and proc.poll() is not None:
                _clear_comfy_pidfile()
                return
            if pid and not _process_alive(int(pid)):
                _clear_comfy_pidfile()
                return
            time.sleep(0.1)
        try:
            if proc:
                proc.kill()
            if pid:
                _terminate_process_tree(int(pid), force=True)
        except Exception:
            pass
        _clear_comfy_pidfile()


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
    try:
        from dreamforge_comfy_ws import ensure_websockets_available

        ensure_websockets_available()
    except ImportError as exc:
        _emit(f"Warning: live preview disabled ({exc})", phase="starting_comfy")
    _emit("Starting managed ComfyUI server…", phase="starting_comfy")
    server = get_default_comfy_server()
    server.start(timeout_s=float(timeout_s))
    from dreamforge_comfy_client import ComfyClient
    from dreamforge_comfy_models import verify_comfy_model_paths_loaded

    client = ComfyClient(server.base_url)
    try:
        from dreamforge_comfy_ws import verify_comfy_websocket

        verify_comfy_websocket(server.base_url)
    except Exception as exc:
        _emit(f"Warning: Comfy WebSocket probe failed ({exc})", phase="starting_comfy")
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
    server.discard_dead_process()
    if not server.is_running():
        ensure_dreamforge_extra_model_paths(COMFY_ROOT)
        server.start(timeout_s=float(timeout_s))
    return server


def recover_managed_comfy_server(*, timeout_s: float = 90.0, reason: str = "") -> ManagedComfyServer:
    """Restart Comfy after a crash without restarting the whole GPU worker."""
    server = get_default_comfy_server()
    server.discard_dead_process()
    if reason:
        print(
            f"[DreamForge] Recovering managed ComfyUI ({reason})",
            file=sys.stderr,
        )
    if server.is_running():
        return server
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


def register_managed_comfy_shutdown() -> None:
    """Register atexit cleanup once per process (desktop worker)."""
    global _shutdown_registered
    if _shutdown_registered:
        return
    atexit.register(stop_managed_comfy_server)
    _shutdown_registered = True


def install_worker_signal_handlers() -> None:
    """Best-effort SIGTERM/SIGINT handler for graceful worker shutdown."""

    def _handle(_signum, _frame) -> None:
        stop_managed_comfy_server()
        raise SystemExit(0)

    for sig in (getattr(signal, "SIGTERM", None), getattr(signal, "SIGINT", None)):
        if sig is None:
            continue
        try:
            signal.signal(sig, _handle)
        except (OSError, ValueError):
            pass
    if os.name == "nt" and hasattr(signal, "SIGBREAK"):
        try:
            signal.signal(signal.SIGBREAK, _handle)
        except (OSError, ValueError):
            pass

