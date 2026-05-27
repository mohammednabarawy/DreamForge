"""ComfyUI HTTP/WebSocket API client.

HTTP uses stdlib urllib. Live progress and canvas previews use the Comfy
WebSocket API (Krita AI Diffusion–style) via dreamforge_comfy_ws.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from typing import Any, Callable


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

    def prompt(self, prompt: dict[str, Any], *, client_id: str | None = None) -> ComfyPromptResult:
        payload: dict[str, Any] = {"prompt": prompt}
        if client_id:
            payload["client_id"] = client_id
        out = _http_json("POST", f"{self.base_url}/prompt", payload)
        pid = out.get("prompt_id") or out.get("promptId") or out.get("id")
        if not pid:
            raise RuntimeError(f"Comfy /prompt returned no prompt_id: {out}")
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

    def wait_for_outputs(
        self,
        prompt_id: str,
        *,
        timeout_s: float = 600.0,
        poll_s: float = 0.5,
    ) -> dict[str, Any]:
        deadline = time.time() + float(timeout_s)
        last = None
        while time.time() < deadline:
            last = self.history(prompt_id)
            # Comfy returns a dict keyed by prompt_id.
            node = last.get(prompt_id)
            if node and isinstance(node, dict) and node.get("outputs"):
                return node
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
        from dreamforge_comfy_ws import ComfyPromptStreamSession, new_client_id

        cid = str(client_id or new_client_id())
        streamed = False
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
                res = self.prompt(prompt, client_id=cid)
                session.set_prompt_id(res.prompt_id)
                session.wait_until_done()
                streamed = True
                node = self.wait_for_outputs(res.prompt_id, timeout_s=30.0, poll_s=poll_s)
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
                if streamed:
                    raise
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

        res = self.prompt(prompt, client_id=cid)
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

