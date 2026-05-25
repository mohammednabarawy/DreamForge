"""
Robust JSON-line IPC for the DreamForge desktop GPU worker.

Tauri on Windows pipes stdout; ComfyUI/tqdm and native extensions can write
directly to fd 1 and break the IPC pipe. We keep fd 1 pointed at stderr for
all library output and write JSON IPC lines only through a saved pipe fd.
"""
from __future__ import annotations

import errno
import io
import json
import os
import sys
from pathlib import Path

_WIN_PIPE_ERRNO = getattr(errno, "EINVAL", 22)

# Dedicated stream to the Tauri stdout pipe (never used by ComfyUI/tqdm).
_ipc_stream = None


def events_file_path(code_root: Path) -> Path:
    return (
        code_root.parent
        / "outputs"
        / "dreamforge"
        / "logs"
        / "worker.events"
    )


def configure_stdio() -> None:
    """Isolate piped stdout from ComfyUI on Windows (Tauri CREATE_NO_WINDOW + pipe)."""
    global _ipc_stream
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    os.environ.setdefault("TQDM_DISABLE", "1")
    os.environ.setdefault("DREAMFORGE_HEADLESS", "1")

    if not hasattr(sys.stdout, "buffer"):
        _ipc_stream = sys.stdout
        return

    try:
        sys.stderr = io.TextIOWrapper(
            sys.stderr.buffer,
            encoding="utf-8",
            errors="replace",
            newline="\n",
            line_buffering=True,
            write_through=True,
        )
    except Exception:
        pass

    if sys.platform == "win32":
        try:
            ipc_fd = os.dup(sys.stdout.fileno())
            os.dup2(sys.stderr.fileno(), sys.stdout.fileno())
            sys.stdout = sys.stderr
            _ipc_stream = io.TextIOWrapper(
                os.fdopen(ipc_fd, "wb", closefd=True),
                encoding="utf-8",
                errors="replace",
                newline="\n",
                line_buffering=True,
                write_through=True,
            )
        except OSError:
            try:
                sys.stdout = io.TextIOWrapper(
                    sys.stdout.buffer,
                    encoding="utf-8",
                    errors="replace",
                    newline="\n",
                    line_buffering=True,
                    write_through=True,
                )
            except Exception:
                pass
            _ipc_stream = sys.stdout
        return

    try:
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer,
            encoding="utf-8",
            errors="replace",
            newline="\n",
            line_buffering=True,
            write_through=True,
        )
    except Exception:
        pass
    _ipc_stream = sys.stdout


def _safe_flush(stream) -> None:
    try:
        stream.flush()
    except OSError as exc:
        if getattr(exc, "errno", None) not in (_WIN_PIPE_ERRNO, errno.EPIPE):
            raise
    except (BrokenPipeError, ValueError):
        pass


def _slim_ipc_payload(payload: dict) -> dict:
    """Preview frames can exceed Windows pipe limits; stream metadata only."""
    if "image_b64" not in payload:
        return payload
    slim = dict(payload)
    slim.pop("image_b64", None)
    if payload.get("preview_path"):
        slim["has_preview"] = True
    return slim


def _slim_events_payload(payload: dict) -> dict:
    """Keep worker.events small; UI loads preview bytes from preview_path."""
    if payload.get("type") != "preview" or "image_b64" not in payload:
        return payload
    slim = dict(payload)
    slim.pop("image_b64", None)
    slim["has_preview"] = bool(payload.get("preview_path"))
    return slim


def emit(payload: dict, events_path: Path) -> bool:
    events_payload = _slim_events_payload(payload)
    line = json.dumps(events_payload, ensure_ascii=False) + "\n"

    try:
        events_path.parent.mkdir(parents=True, exist_ok=True)
        with open(events_path, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(line)
            fh.flush()
    except OSError:
        pass

    stream = _ipc_stream
    if stream is None:
        return True

    ipc_line = json.dumps(_slim_ipc_payload(payload), ensure_ascii=False) + "\n"
    try:
        stream.write(ipc_line)
        _safe_flush(stream)
    except OSError as exc:
        if getattr(exc, "errno", None) not in (_WIN_PIPE_ERRNO, errno.EPIPE):
            if sys.platform != "win32":
                raise
    except BrokenPipeError:
        pass

    return True


def reset_events_file(events_path: Path) -> None:
    try:
        events_path.parent.mkdir(parents=True, exist_ok=True)
        events_path.write_text("", encoding="utf-8")
    except OSError:
        pass
