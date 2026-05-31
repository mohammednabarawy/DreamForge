"""ComfyUI WebSocket streaming (Krita AI Diffusion–style).

Connects to /ws?clientId=… before queueing the prompt, handles progress_state
and binary preview frames, and writes outputs/preview.jpg for the desktop shell.
"""

from __future__ import annotations

import io
import json
import struct
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from _paths import PROJECT_ROOT
from dreamforge_progress import GEN_SAMPLING, generation_label, generation_phase_from_preview

ProgressCallback = Callable[[dict[str, Any]], None]
HistoryPollFn = Callable[[str], str]

# ComfyUI protocol.BinaryEventTypes (see repositories/ComfyUI/protocol.py)
_PREVIEW_IMAGE = 1
_UNENCODED_PREVIEW_IMAGE = 2
_PREVIEW_WITH_METADATA = 4

_SAMPLER_NODE_TYPES = frozenset(
    {
        "KSampler",
        "KSamplerAdvanced",
        "SamplerCustom",
        "SamplerCustomAdvanced",
    }
)

# Krita Style.live_sampler_steps / live_cfg_scale defaults (style.py).
DEFAULT_LIVE_SAMPLING: dict[str, Any] = {
    "steps": 6,
    "cfg": 1.8,
    "sampler_name": "euler",
    "scheduler": "simple",
}

# Must be the first JSON message after /ws connect (Comfy server.py websocket_handler).
_COMFY_CLIENT_FEATURE_FLAGS = {
    "type": "feature_flags",
    "data": {"supports_preview_metadata": True},
}

_WS_CONNECT_ATTEMPTS = 3


@dataclass
class ComfyPromptWaitConfig:
    prompt_id: str
    client_id: str
    job_id: str = ""
    sample_count: int = 20
    node_count: int = 1
    timeout_s: float = 600.0


class ComfyProgressTracker:
    """Weighted node + sampler progress (Krita Progress class)."""

    def __init__(self, *, sample_count: int = 20, node_count: int = 1):
        self.sample_count = max(int(sample_count), 1)
        self.node_count = max(int(node_count), 1)
        self._nodes = 0
        self._samples = 0
        self._state_ratio = 0.0

    def handle(self, msg: dict[str, Any], *, prompt_id: str) -> None:
        data = msg.get("data") or {}
        if data.get("prompt_id") not in (None, prompt_id):
            return
        msg_type = msg.get("type")
        if msg_type == "executing":
            self._nodes += 1
        elif msg_type == "execution_cached":
            nodes = data.get("nodes") or []
            self._nodes += len(nodes) if isinstance(nodes, list) else 1
        elif msg_type == "progress":
            self._samples += 1

    def handle_progress_state(self, msg: dict[str, Any], *, prompt_id: str) -> None:
        data = msg.get("data") or {}
        if data.get("prompt_id") not in (None, prompt_id):
            return
        nodes = data.get("nodes") or {}
        best = 0.0
        for node in nodes.values():
            if not isinstance(node, dict):
                continue
            max_v = float(node.get("max") or 0)
            val = float(node.get("value") or 0)
            if max_v > 0:
                best = max(best, val / max_v)
        self._state_ratio = min(0.99, best)

    @property
    def value(self) -> float:
        node_part = self._nodes / (self.node_count + 1)
        sample_part = self._samples / self.sample_count
        legacy = 0.2 * node_part + 0.8 * sample_part
        return max(legacy, self._state_ratio)


def _sanitize_job_id(job_id: str) -> str:
    cleaned = "".join(c if c.isalnum() or c in "-_" else "_" for c in str(job_id or "").strip())
    return cleaned[:80] or "live"


def count_comfy_prompt_nodes(prompt: dict[str, Any]) -> int:
    """Estimate graph size for progress weighting (Krita workflow.node_count)."""
    if not isinstance(prompt, dict):
        return 1
    return max(len(prompt), 1)


def guess_sample_count_from_prompt(prompt: dict[str, Any], *, fallback: int = 20) -> int:
    """Sum KSampler step counts from a Comfy API prompt (Krita guess_sample_count)."""
    if not isinstance(prompt, dict):
        return max(int(fallback), 1)
    total = 0
    for node in prompt.values():
        if not isinstance(node, dict):
            continue
        class_type = str(node.get("class_type") or "")
        if class_type not in _SAMPLER_NODE_TYPES:
            continue
        inputs = node.get("inputs") if isinstance(node.get("inputs"), dict) else {}
        steps = inputs.get("steps")
        if not isinstance(steps, (int, float)) or steps <= 0:
            continue
        if class_type == "KSamplerAdvanced":
            start_at = inputs.get("start_at_step") or 0
            try:
                total += max(int(steps) - int(start_at), 1)
            except (TypeError, ValueError):
                total += int(steps)
        else:
            total += int(steps)
    return max(total, int(fallback), 1)


def prompt_id_from_job_id(job_id: str) -> str | None:
    """Use DreamForge job UUID as Comfy prompt_id when possible (Krita client pattern)."""
    value = str(job_id or "").strip()
    if not value:
        return None
    try:
        uuid.UUID(value)
    except ValueError:
        return None
    return value


def live_preview_path(job_id: str = "") -> Path:
    base = PROJECT_ROOT / "outputs"
    if str(job_id or "").strip():
        return base / f"preview-{_sanitize_job_id(job_id)}.jpg"
    return base / "preview.jpg"


def write_live_preview(
    image_bytes: bytes,
    *,
    image_format: int | None = None,
    job_id: str = "",
) -> Path:
    """Write live preview JPEG for the desktop shell (atomic replace)."""
    from PIL import Image

    path = live_preview_path(job_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    legacy_path = live_preview_path()
    # Tauri also checks backend/outputs/preview.jpg when agent_root is backend/.
    backend_mirror = path.parent.parent / "backend" / "outputs" / path.name
    backend_legacy = path.parent.parent / "backend" / "outputs" / legacy_path.name
    if image_format == 2 or image_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=88)
        image_bytes = buf.getvalue()
    elif image_format != 1 and image_bytes[:2] != b"\xff\xd8":
        try:
            img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=88)
            image_bytes = buf.getvalue()
        except Exception:
            pass

    def _atomic_write(target: Path) -> None:
        tmp = target.with_suffix(f"{target.suffix}.tmp")
        tmp.write_bytes(image_bytes)
        tmp.replace(target)

    _atomic_write(path)
    if job_id:
        _atomic_write(legacy_path)
    resolved = path.resolve()
    for mirror in (backend_mirror, backend_legacy if job_id else None):
        if mirror is None:
            continue
        try:
            mirror.parent.mkdir(parents=True, exist_ok=True)
            mirror.write_bytes(image_bytes)
        except OSError:
            pass
    return resolved


def extract_preview_image_bytes(data: bytes | memoryview) -> tuple[bytes, int] | None:
    """Parse Comfy binary preview (legacy PREVIEW_IMAGE and PREVIEW_IMAGE_WITH_METADATA)."""
    view = memoryview(data) if not isinstance(data, memoryview) else data
    if len(view) < 4:
        return None
    event = struct.unpack_from(">I", view, 0)[0]

    if event == _UNENCODED_PREVIEW_IMAGE and len(view) >= 8:
        fmt = struct.unpack_from(">I", view, 4)[0]
        if fmt in (1, 2):
            return bytes(view[8:]), int(fmt)

    if event == _PREVIEW_WITH_METADATA and len(view) >= 8:
        meta_len = struct.unpack_from(">I", view, 4)[0]
        meta_end = 8 + meta_len
        if meta_end <= len(view):
            image_bytes = bytes(view[meta_end:])
            if image_bytes[:2] == b"\xff\xd8":
                return image_bytes, 1
            if image_bytes[:8] == b"\x89PNG\r\n\x1a\n":
                return image_bytes, 2
            return image_bytes, 1

    if event == _PREVIEW_IMAGE and len(view) >= 8:
        fmt = struct.unpack_from(">I", view, 4)[0]
        if fmt in (1, 2):
            return bytes(view[8:]), int(fmt)

    if view[:2] == b"\xff\xd8":
        return bytes(view), 1
    if view[:8] == b"\x89PNG\r\n\x1a\n":
        return bytes(view), 2
    return None


def _http_to_ws_url(base_url: str) -> str:
    parsed = urlparse(base_url.rstrip("/"))
    scheme = "wss" if parsed.scheme == "https" else "ws"
    host = parsed.netloc or parsed.path
    return f"{scheme}://{host}"


def preview_stream_payload(
    preview_file: Path,
    *,
    job_id: str,
    percentage: int,
    title: str,
) -> dict[str, Any]:
    return {
        "type": "preview",
        "job_id": job_id,
        "percentage": int(percentage),
        "title": str(title or ""),
        "preview_path": str(preview_file),
        "has_preview": True,
        "live": True,
        "phase": generation_phase_from_preview(percentage, title),
    }


def progress_stream_payload(
    *,
    job_id: str,
    progress_value: float,
    message: str | None = None,
) -> dict[str, Any]:
    pct = int(max(0, min(99, round(progress_value * 100))))
    phase = generation_phase_from_preview(pct, message)
    label = generation_label(phase, message)
    return {
        "type": "progress",
        "job_id": job_id,
        "phase": phase,
        "progress": pct,
        "message": label,
    }


def ensure_websockets_available() -> None:
    try:
        from websockets.sync.client import connect  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "Live Comfy previews require the 'websockets' package (see backend/pip/modules.txt). "
            "Restart the GPU engine after installing dependencies."
        ) from exc


def new_client_id() -> str:
    return str(uuid.uuid4())


def verify_comfy_websocket(
    base_url: str,
    *,
    client_id: str | None = None,
    timeout_s: float = 10.0,
) -> None:
    """Probe Comfy /ws before generation (Krita ComfyClient.connect handshake)."""
    ensure_websockets_available()
    from websockets.sync.client import connect

    cid = str(client_id or new_client_id())
    uri = f"{_http_to_ws_url(base_url.rstrip('/'))}/ws?clientId={cid}"
    with connect(uri, max_size=2**16, open_timeout=float(timeout_s)) as websocket:
        websocket.send(json.dumps(_COMFY_CLIENT_FEATURE_FLAGS))


class ComfyPromptStreamSession:
    """Listen on Comfy WebSocket before/while a prompt runs (Krita connect-first pattern)."""

    def __init__(
        self,
        base_url: str,
        client_id: str,
        *,
        job_id: str = "",
        sample_count: int = 20,
        node_count: int = 1,
        timeout_s: float = 600.0,
        on_event: ProgressCallback | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.client_id = str(client_id)
        self.config = ComfyPromptWaitConfig(
            prompt_id="",
            client_id=self.client_id,
            job_id=str(job_id or ""),
            sample_count=int(sample_count),
            node_count=int(node_count),
            timeout_s=float(timeout_s),
        )
        self.on_event = on_event
        self._prompt_id: str | None = None
        self._connected = threading.Event()
        self._done = threading.Event()
        self._error: BaseException | None = None
        self._thread: threading.Thread | None = None
        self._tracker = ComfyProgressTracker(
            sample_count=self.config.sample_count,
            node_count=self.config.node_count,
        )

    def start(self) -> None:
        ensure_websockets_available()
        self._thread = threading.Thread(target=self._run, name="comfy-ws", daemon=True)
        self._thread.start()
        if not self._connected.wait(timeout=15.0):
            raise TimeoutError("Timed out connecting to ComfyUI WebSocket for live preview")
        if self._error is not None:
            raise RuntimeError(str(self._error)) from self._error

    def set_prompt_id(self, prompt_id: str) -> None:
        self._prompt_id = str(prompt_id)
        self.config.prompt_id = self._prompt_id

    def wait_until_done(self, *, history_poll: HistoryPollFn | None = None) -> None:
        deadline = time.time() + float(self.config.timeout_s)
        last_poll = 0.0
        while time.time() < deadline:
            if self._error is not None:
                raise RuntimeError(str(self._error)) from self._error
            if self._done.is_set():
                return
            if history_poll and self._prompt_id and time.time() - last_poll >= 2.0:
                last_poll = time.time()
                state = history_poll(self._prompt_id)
                if state == "done":
                    return
                if state.startswith("error:"):
                    raise RuntimeError(state[6:])
            time.sleep(0.05)
        raise TimeoutError(f"Timed out waiting for Comfy prompt {self._prompt_id}")

    def _emit_progress(self) -> None:
        if not self.on_event:
            return
        self.on_event(
            progress_stream_payload(
                job_id=self.config.job_id or self.config.prompt_id,
                progress_value=self._tracker.value,
                message=generation_label(GEN_SAMPLING, None),
            )
        )

    def _emit_preview(self, image_bytes: bytes, fmt: int) -> None:
        if not self.on_event:
            return
        path = write_live_preview(
            image_bytes,
            image_format=fmt,
            job_id=self.config.job_id,
        )
        pct = int(self._tracker.value * 100)
        self.on_event(
            preview_stream_payload(
                path,
                job_id=self.config.job_id or self.config.prompt_id,
                percentage=pct,
                title=generation_label(GEN_SAMPLING, "Sampling…"),
            )
        )

    def _run(self) -> None:
        uri = f"{_http_to_ws_url(self.base_url)}/ws?clientId={self.client_id}"
        last_error: BaseException | None = None
        for attempt in range(_WS_CONNECT_ATTEMPTS):
            if self._done.is_set():
                return
            try:
                self._listen_on_websocket(uri)
                return
            except Exception as exc:
                last_error = exc
                if self._done.is_set():
                    return
                if attempt + 1 >= _WS_CONNECT_ATTEMPTS:
                    break
                time.sleep(min(float(attempt + 1), 3.0))
        self._error = last_error or RuntimeError("ComfyUI WebSocket connection failed")
        self._connected.set()
        self._done.set()

    def _listen_on_websocket(self, uri: str) -> None:
        from websockets.sync.client import connect

        with connect(uri, max_size=2**30, open_timeout=30) as websocket:
            websocket.send(json.dumps(_COMFY_CLIENT_FEATURE_FLAGS))
            self._connected.set()
            deadline = time.time() + float(self.config.timeout_s)
            while not self._done.is_set() and time.time() < deadline:
                if self._prompt_id is None:
                    time.sleep(0.02)
                    continue
                try:
                    raw = websocket.recv(timeout=1.0)
                except TimeoutError:
                    continue

                if isinstance(raw, (bytes, bytearray, memoryview)):
                    parsed = extract_preview_image_bytes(raw)
                    if parsed:
                        image_bytes, fmt = parsed
                        self._emit_preview(image_bytes, fmt)
                    continue

                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                msg_type = msg.get("type")
                data = msg.get("data") or {}
                pid = data.get("prompt_id")

                if msg_type == "execution_start" and self._prompt_id and pid == self._prompt_id:
                    self._tracker = ComfyProgressTracker(
                        sample_count=self.config.sample_count,
                        node_count=self.config.node_count,
                    )

                if msg_type == "execution_error" and pid == self._prompt_id:
                    err = data.get("exception_message") or "ComfyUI execution_error"
                    self._error = RuntimeError(str(err))
                    self._done.set()
                    break

                if msg_type == "execution_interrupted" and pid == self._prompt_id:
                    self._error = RuntimeError("ComfyUI execution interrupted")
                    self._done.set()
                    break

                if self._prompt_id and pid not in (None, self._prompt_id):
                    continue

                if msg_type == "execution_success" and self._prompt_id:
                    self._done.set()
                    break

                if msg_type == "progress_state" and self._prompt_id:
                    self._tracker.handle_progress_state(msg, prompt_id=self._prompt_id)
                    self._emit_progress()
                elif msg_type in ("execution_cached", "executing", "progress") and self._prompt_id:
                    self._tracker.handle(msg, prompt_id=self._prompt_id)
                    self._emit_progress()

                if msg_type == "executing" and data.get("node") is None:
                    self._done.set()
                    break


def wait_for_prompt_websocket(
    base_url: str,
    config: ComfyPromptWaitConfig,
    on_event: ProgressCallback | None = None,
) -> None:
    """Legacy blocking wait (connect may race prompt). Prefer ComfyPromptStreamSession."""
    session = ComfyPromptStreamSession(
        base_url,
        config.client_id,
        job_id=config.job_id,
        sample_count=config.sample_count,
        node_count=config.node_count,
        timeout_s=config.timeout_s,
        on_event=on_event,
    )
    session.start()
    session.set_prompt_id(config.prompt_id)
    session.wait_until_done()
