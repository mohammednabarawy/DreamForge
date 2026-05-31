"""ComfyUI HTTP/WebSocket API client.

HTTP uses stdlib urllib. Live progress and canvas previews use the Comfy
WebSocket API (Krita AI Diffusion–style) via dreamforge_comfy_ws.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from typing import Any, Callable

_log = logging.getLogger(__name__)


def _http_json(method: str, url: str, payload: dict | None = None, timeout_s: float = 30.0) -> dict:
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        body = None
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            body = None
        raise RuntimeError(f"Comfy HTTP {exc.code} {exc.reason}: {body}") from exc
    return json.loads(raw.decode("utf-8", errors="replace") or "{}")


def _http_multipart(
    url: str,
    *,
    fields: dict[str, str],
    file_field: str,
    file_name: str,
    file_bytes: bytes,
    content_type: str = "application/octet-stream",
    timeout_s: float = 60.0,
) -> dict:
    boundary = f"----dreamforge-{uuid.uuid4().hex}"
    body = bytearray()
    for key, value in (fields or {}).items():
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode("utf-8"))
        body.extend(str(value).encode("utf-8"))
        body.extend(b"\r\n")
    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(
        (
            f'Content-Disposition: form-data; name="{file_field}"; '
            f'filename="{file_name}"\r\n'
        ).encode("utf-8")
    )
    body.extend(f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"))
    body.extend(file_bytes)
    body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode("utf-8"))
    headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
    req = urllib.request.Request(url, data=bytes(body), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        body = None
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            body = None
        raise RuntimeError(f"Comfy HTTP {exc.code} {exc.reason}: {body}") from exc
    return json.loads(raw.decode("utf-8", errors="replace") or "{}")


class ComfyExecutionError(RuntimeError):
    """Raised when ComfyUI finishes a prompt without usable outputs."""

    def __init__(self, message: str, *, prompt_id: str = "", details: dict | None = None):
        super().__init__(message)
        self.prompt_id = prompt_id
        self.details = details or {}


def _extract_comfy_execution_error(node: dict[str, Any]) -> str | None:
    """Return a user-facing error when Comfy marked the prompt done but produced no outputs."""
    if not isinstance(node, dict) or node.get("outputs"):
        return None

    status = node.get("status")
    if not isinstance(status, dict):
        return None

    status_str = str(status.get("status_str") or "").lower()
    completed = bool(status.get("completed"))
    if not completed and status_str not in {"error", "failed"}:
        return None

    messages = status.get("messages") or []
    for item in messages:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        tag = str(item[0])
        payload = item[1] if isinstance(item[1], dict) else {}
        if tag != "execution_error":
            continue
        message = str(
            payload.get("exception_message")
            or payload.get("traceback")
            or "ComfyUI execution failed"
        ).strip()
        node_type = payload.get("node_type")
        if node_type:
            return f"{node_type}: {message}"
        return message

    if status_str in {"error", "failed"}:
        return "ComfyUI workflow failed without output images"
    if completed:
        return "ComfyUI finished without output images (likely OOM or workflow mismatch)"
    return None


@dataclass
class ComfyPromptResult:
    prompt_id: str


class ComfyClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def object_info(self, *, timeout_s: float = 60.0) -> dict[str, Any]:
        return _http_json("GET", f"{self.base_url}/object_info", None, timeout_s=timeout_s)

    def interrupt(self, *, timeout_s: float = 10.0) -> None:
        _http_json("POST", f"{self.base_url}/interrupt", {}, timeout_s=timeout_s)

    def prompt(
        self,
        prompt: dict[str, Any],
        *,
        client_id: str | None = None,
        prompt_id: str | None = None,
    ) -> ComfyPromptResult:
        payload: dict[str, Any] = {"prompt": prompt}
        if client_id:
            payload["client_id"] = client_id
        if prompt_id:
            payload["prompt_id"] = str(prompt_id)
        out = _http_json("POST", f"{self.base_url}/prompt", payload)
        pid = out.get("prompt_id") or out.get("promptId") or out.get("id")
        if not pid:
            raise RuntimeError(f"Comfy /prompt returned no prompt_id: {out}")
        if prompt_id and str(pid) != str(prompt_id):
            _log.warning("Comfy prompt_id mismatch: got %s, expected %s", pid, prompt_id)
        return ComfyPromptResult(prompt_id=str(pid))

    def history(self, prompt_id: str) -> dict[str, Any]:
        return _http_json("GET", f"{self.base_url}/history/{prompt_id}", None)

    def upload_image(
        self,
        *,
        image_bytes: bytes,
        filename: str,
        folder_type: str = "input",
        subfolder: str = "",
        overwrite: bool = True,
        timeout_s: float = 120.0,
    ) -> dict[str, Any]:
        return _http_multipart(
            f"{self.base_url}/upload/image",
            fields={
                "type": str(folder_type or "input"),
                "subfolder": str(subfolder or ""),
                "overwrite": "true" if overwrite else "false",
            },
            file_field="image",
            file_name=str(filename),
            file_bytes=image_bytes,
            content_type="image/png",
            timeout_s=timeout_s,
        )

    def history_poll_state(self, prompt_id: str) -> str:
        """Return pending, done, or error:<message> for WebSocket wait fallback."""
        node = self.history(prompt_id).get(prompt_id) or {}
        if node.get("outputs"):
            return "done"
        err = _extract_comfy_execution_error(node)
        if err:
            return f"error:{err}"
        return "pending"

    def wait_for_outputs(
        self,
        prompt_id: str,
        *,
        timeout_s: float = 600.0,
        poll_s: float = 0.5,
        max_connection_errors: int = 6,
    ) -> dict[str, Any]:
        """Poll /history until outputs appear or an error is detected.

        Tolerates transient connection errors (e.g. ComfyUI briefly
        unreachable after heavy VRAM work) up to *max_connection_errors*
        consecutive failures before giving up.
        """
        deadline = time.time() + float(timeout_s)
        last = None
        consecutive_conn_errors = 0
        while time.time() < deadline:
            try:
                last = self.history(prompt_id)
                consecutive_conn_errors = 0  # reset on success
            except (urllib.error.URLError, OSError, ConnectionError) as exc:
                consecutive_conn_errors += 1
                _log.warning(
                    "Comfy /history connection error (%d/%d): %s",
                    consecutive_conn_errors,
                    max_connection_errors,
                    exc,
                )
                if consecutive_conn_errors >= max_connection_errors:
                    raise ComfyExecutionError(
                        f"ComfyUI server became unreachable after sampling "
                        f"({consecutive_conn_errors} consecutive connection failures). "
                        f"The server may have crashed (OOM, driver reset, etc.).",
                        prompt_id=str(prompt_id),
                        details={"last_error": str(exc)},
                    ) from exc
                # Back off progressively: 1s, 2s, 3s … before retrying
                time.sleep(min(float(consecutive_conn_errors), 5.0))
                continue
            # Comfy returns a dict keyed by prompt_id.
            node = last.get(prompt_id)
            if node and isinstance(node, dict):
                if node.get("outputs"):
                    return node
                err = _extract_comfy_execution_error(node)
                if err:
                    raise ComfyExecutionError(err, prompt_id=str(prompt_id), details=node)
            time.sleep(float(poll_s))
        raise TimeoutError(f"Timed out waiting for Comfy outputs ({prompt_id}). Last={last}")

    def run_prompt_with_stream(
        self,
        prompt: dict[str, Any],
        *,
        client_id: str | None = None,
        job_id: str = "",
        sample_count: int = 20,
        node_count: int = 1,
        timeout_s: float = 600.0,
        on_event: Callable[[dict[str, Any]], None] | None = None,
        poll_s: float = 0.5,
    ) -> tuple[ComfyPromptResult, dict[str, Any]]:
        """Queue prompt after opening WebSocket (Krita-style), stream previews, return outputs."""
        from dreamforge_comfy_ws import ComfyPromptStreamSession, new_client_id, prompt_id_from_job_id

        cid = str(client_id or new_client_id())
        requested_prompt_id = prompt_id_from_job_id(str(job_id or ""))
        submitted: ComfyPromptResult | None = None
        if on_event is not None:
            try:
                session = ComfyPromptStreamSession(
                    self.base_url,
                    cid,
                    job_id=str(job_id),
                    sample_count=int(sample_count),
                    node_count=int(node_count),
                    timeout_s=float(timeout_s),
                    on_event=on_event,
                )
                session.start()
                if requested_prompt_id:
                    session.set_prompt_id(requested_prompt_id)
                res = self.prompt(prompt, client_id=cid, prompt_id=requested_prompt_id)
                submitted = res
                session.set_prompt_id(res.prompt_id)
                session.wait_until_done(history_poll=self.history_poll_state)
                node = self.wait_for_outputs(
                    res.prompt_id,
                    timeout_s=float(timeout_s),
                    poll_s=poll_s,
                )
                return res, node
            except ImportError as exc:
                if on_event is not None:
                    on_event(
                        {
                            "type": "progress",
                            "job_id": job_id,
                            "phase": "sampling",
                            "progress": 0,
                            "message": (
                                "Live preview unavailable (install websockets in the GPU Python). "
                                f"{exc}"
                            ),
                        }
                    )
            except Exception as exc:
                if submitted is not None:
                    if on_event is not None:
                        on_event(
                            {
                                "type": "progress",
                                "job_id": job_id,
                                "phase": "sampling",
                                "progress": 0,
                                "message": (
                                    "Live preview WebSocket unavailable; "
                                    "waiting for Comfy via HTTP…"
                                ),
                            },
                        )
                    try:
                        node = self.wait_for_outputs(
                            submitted.prompt_id,
                            timeout_s=float(timeout_s),
                            poll_s=poll_s,
                        )
                        return submitted, node
                    except ComfyExecutionError:
                        raise  # propagate structured Comfy errors
                    except (urllib.error.URLError, OSError, ConnectionError) as http_exc:
                        raise ComfyExecutionError(
                            f"ComfyUI server became unreachable after sampling completed. "
                            f"This usually means ComfyUI crashed (OOM, driver reset). "
                            f"Original WebSocket error: {exc}; HTTP error: {http_exc}",
                            prompt_id=str(submitted.prompt_id),
                            details={"ws_error": str(exc), "http_error": str(http_exc)},
                        ) from http_exc
                if on_event is not None:
                    on_event(
                        {
                            "type": "progress",
                            "job_id": job_id,
                            "phase": "sampling",
                            "progress": 0,
                            "message": f"Live preview WebSocket failed: {exc}",
                        }
                    )

        res = submitted or self.prompt(prompt, client_id=cid)
        node = self.wait_for_outputs(res.prompt_id, timeout_s=float(timeout_s), poll_s=poll_s)
        return res, node

    def wait_for_prompt(
        self,
        prompt_id: str,
        *,
        client_id: str,
        job_id: str = "",
        sample_count: int = 20,
        node_count: int = 1,
        timeout_s: float = 600.0,
        on_event: Callable[[dict[str, Any]], None] | None = None,
        poll_s: float = 0.5,
    ) -> dict[str, Any]:
        """Wait for an already-submitted prompt (prefer run_prompt_with_stream)."""
        from dreamforge_comfy_ws import ComfyPromptStreamSession

        try:
            session = ComfyPromptStreamSession(
                self.base_url,
                str(client_id),
                job_id=str(job_id or prompt_id),
                sample_count=int(sample_count),
                node_count=int(node_count),
                timeout_s=float(timeout_s),
                on_event=on_event,
            )
            session.start()
            session.set_prompt_id(str(prompt_id))
            session.wait_until_done()
        except ImportError:
            pass
        except Exception:
            if on_event is not None:
                raise
        return self.wait_for_outputs(prompt_id, timeout_s=float(timeout_s), poll_s=poll_s)

    def view(self, *, filename: str, subfolder: str = "", folder_type: str = "output", timeout_s: float = 60.0) -> bytes:
        q = urllib.parse.urlencode(
            {
                "filename": filename,
                "subfolder": subfolder,
                "type": folder_type,
            }
        )
        url = f"{self.base_url}/view?{q}"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            return resp.read()

