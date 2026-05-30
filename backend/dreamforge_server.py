"""
DreamForge REST API Headless Server.
Runs on localhost:7777 using zero external dependencies (standard library only).
"""
from __future__ import annotations

import json
import os
import sys
import traceback
from http.server import BaseHTTPRequestHandler
from socketserver import ThreadingTCPServer
from urllib.parse import parse_qs, urlparse

from _paths import BACKEND_ROOT, extend_sys_path
extend_sys_path()

from dreamforge_engine import DreamForgeEngine
from dreamforge_workflow_planner import list_workflow_templates


class DreamForgeRESTHandler(BaseHTTPRequestHandler):
    """Zero-dependency HTTP Handler for DreamForge REST API."""
    
    def _send_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def _respond_json(self, status_code: int, payload: dict) -> None:
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))

    def _read_json_body(self) -> dict:
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            return {}
        raw_body = self.rfile.read(content_length)
        return json.loads(raw_body.decode("utf-8"))

    def do_GET(self) -> None:
        parsed_url = urlparse(self.path)
        path = parsed_url.path.rstrip('/')
        
        if path == "/models":
            try:
                summary = DreamForgeEngine.list_models()
                self._respond_json(200, {"status": "success", "models": summary})
            except Exception as e:
                self._respond_json(500, {"status": "error", "message": str(e)})

        elif path == "/workflows":
            try:
                # List workflow files inside settings or defaults
                workflow_dir = BACKEND_ROOT / "settings"
                workflows = []
                if workflow_dir.is_dir():
                    workflows = [f.name for f in workflow_dir.glob("*.json")]
                self._respond_json(200, {"status": "success", "workflows": workflows})
            except Exception as e:
                self._respond_json(500, {"status": "error", "message": str(e)})

        elif path == "/workflow-templates":
            self._respond_json(200, {
                "status": "success",
                "image_backend": "local_comfy",
                "local_only": True,
                "templates": list_workflow_templates(),
            })

        elif path == "/projects":
            try:
                # Return recent outputs
                query_params = parse_qs(parsed_url.query)
                limit = int(query_params.get("limit", [40])[0])
                offset = int(query_params.get("offset", [0])[0])
                payload = DreamForgeEngine.list_outputs(limit=limit, offset=offset)
                self._respond_json(200, {"status": "success", **payload})
            except Exception as e:
                self._respond_json(500, {"status": "error", "message": str(e)})

        elif path in ("", "/health", "/ping"):
            self._respond_json(200, {"status": "alive", "service": "DreamForge Server", "version": "0.1.0"})

        else:
            self._respond_json(404, {"status": "error", "message": "Not Found"})

    def do_POST(self) -> None:
        parsed_url = urlparse(self.path)
        path = parsed_url.path.rstrip('/')

        if path in ("/generate", "/edit", "/upscale"):
            try:
                params = self._read_json_body()
                
                # Coerce/route specific configurations for edit/upscale endpoints if needed
                if path == "/edit":
                    params.setdefault("edit_type", "auto")
                    params.setdefault("use_comfy_server", True)
                elif path == "/upscale":
                    params.setdefault("cn_type", "upscale")
                    params.setdefault("upscale_method", "2x")
                    params.setdefault("use_comfy_server", True)

                print(f"[DreamForge Server] Running generation for {path} with params: {params}", file=sys.stderr)
                result = DreamForgeEngine.execute_job(params)
                
                status_code = 200 if result.get("status") == "success" else 400
                self._respond_json(status_code, result)

            except Exception as e:
                traceback.print_exc(file=sys.stderr)
                self._respond_json(500, {
                    "status": "error",
                    "message": f"Server failed to process request: {e}",
                    "traceback": traceback.format_exc()
                })
        elif path == "/brain/plan":
            try:
                params = self._read_json_body()
                instruction = str(params.get("instruction") or params.get("prompt") or "")
                decision = DreamForgeEngine.plan(
                    instruction,
                    current_settings=params.get("current_settings") if isinstance(params.get("current_settings"), dict) else params,
                    selected_image=str(params.get("selected_image") or params.get("input_image") or ""),
                    gallery=params.get("gallery") if isinstance(params.get("gallery"), list) else [],
                    brain_provider=str(params.get("brain_provider") or "auto"),
                    brain_base_url=str(params.get("brain_base_url") or ""),
                    brain_model=str(params.get("brain_model") or ""),
                    brain_api_key=str(params.get("brain_api_key") or ""),
                )
                self._respond_json(200, decision)
            except Exception as e:
                traceback.print_exc(file=sys.stderr)
                self._respond_json(500, {
                    "status": "error",
                    "message": f"Brain planning failed: {e}",
                    "traceback": traceback.format_exc()
                })
        elif path in ("/dry-run", "/dry_run"):
            try:
                params = self._read_json_body()
                plan = DreamForgeEngine.dry_run(params)
                self._respond_json(200, plan)
            except Exception as e:
                traceback.print_exc(file=sys.stderr)
                self._respond_json(500, {
                    "status": "error",
                    "message": f"Dry run failed: {e}",
                    "traceback": traceback.format_exc()
                })
        else:
            self._respond_json(404, {"status": "error", "message": "Not Found"})


def run_server(port: int = 7777) -> None:
    """Start the multi-threaded HTTP server."""
    server_address = ("", port)
    
    # Enable ComfyUI boot automatically in the background
    from dreamforge_comfy_server import ensure_comfy_running
    try:
        print("[DreamForge Server] Ensuring ComfyUI server is booted...", file=sys.stderr)
        ensure_comfy_running(timeout_s=60.0)
    except Exception as e:
        print(f"[DreamForge Server Warning] Could not verify ComfyUI boot: {e}", file=sys.stderr)

    # Use ThreadingTCPServer to avoid blocking requests during generation
    ThreadingTCPServer.allow_reuse_address = True
    with ThreadingTCPServer(server_address, DreamForgeRESTHandler) as httpd:
        print(f"[DreamForge Server] REST API running at http://localhost:{port}/", file=sys.stderr)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[DreamForge Server] Shutting down REST API server...", file=sys.stderr)


if __name__ == "__main__":
    port_arg = 7777
    if len(sys.argv) > 1:
        try:
            port_arg = int(sys.argv[1])
        except ValueError:
            pass
    run_server(port_arg)
