#!/usr/bin/env python3
"""Smoke-test CLI, MCP, desktop bridge, and webui entrypoints after install."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from _paths import PROJECT_ROOT as PR, PYTHON_EXE  # noqa: E402

FAILURES: list[str] = []


def ok(name: str, detail: str = "") -> None:
    suffix = f" — {detail}" if detail else ""
    print(f"  OK  {name}{suffix}")


def fail(name: str, detail: str) -> None:
    FAILURES.append(f"{name}: {detail}")
    print(f"  FAIL {name}: {detail}")


def parse_json_output(text: str) -> dict | None:
    text = text.strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    if start == -1:
        return None
    try:
        obj, _ = json.JSONDecoder().raw_decode(text[start:])
        return obj
    except json.JSONDecodeError:
        return None


def run_json(cmd: list[str], *, cwd: Path | None = None) -> dict | None:
    result = subprocess.run(
        cmd,
        cwd=str(cwd or PROJECT_ROOT),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        fail("command", f"{' '.join(cmd)} exited {result.returncode}: {result.stderr.strip()[:200]}")
        return None
    parsed = parse_json_output(result.stdout)
    if parsed is None:
        fail("json", result.stdout.strip()[:200])
    return parsed


def run_checked(name: str, cmd: list[str], *, cwd: Path | None = None, detail: str = "") -> None:
    try:
        subprocess.run(
            cmd,
            cwd=str(cwd or PROJECT_ROOT),
            check=True,
            capture_output=True,
            text=True,
        )
        ok(name, detail or " ".join(cmd))
    except FileNotFoundError:
        fail(name, f"command not found: {cmd[0]}")
    except subprocess.CalledProcessError as exc:
        err = (exc.stderr or exc.stdout or "")[-800:].strip()
        fail(name, err[:400] or f"{' '.join(cmd)} exited {exc.returncode}")


def main() -> int:
    print("DreamForge entrypoint verification")
    print(f"  project: {PR}")
    print(f"  python:  {PYTHON_EXE}")

    py = str(PYTHON_EXE)
    if not Path(py).is_file():
        fail("python", f"Interpreter not found: {py}")
        return 1

    if not (BACKEND_ROOT / "dreamforge_cli_direct.py").is_file():
        fail("layout", "backend/dreamforge_cli_direct.py missing")
    else:
        ok("layout", "backend/ present")

    cli = run_json(
        [
            py,
            "-s",
            str(BACKEND_ROOT / "dreamforge_cli_direct.py"),
            "--dry-run",
            "--json",
            "--prompt",
            "verify",
            "--vram-profile",
            "16gb",
        ],
        cwd=BACKEND_ROOT,
    )
    if cli and (cli.get("ready") is True or cli.get("status") == "planned"):
        ok("cli", "dry-run")
    elif cli:
        fail("cli", f"dry-run not ready: {cli.get('status')}")

    bridge = run_json(
        [py, "-s", str(BACKEND_ROOT / "dreamforge_desktop_bridge.py"), "--once", '{"cmd":"ping"}'],
        cwd=BACKEND_ROOT,
    )
    if bridge and bridge.get("ok"):
        ok("desktop-bridge", "ping")
    elif bridge is not None:
        fail("desktop-bridge", str(bridge))

    paths = run_json(
        [py, "-s", str(BACKEND_ROOT / "dreamforge_desktop_bridge.py"), "--once", '{"cmd":"get_paths"}'],
        cwd=BACKEND_ROOT,
    )
    if paths and str(paths.get("backend_root", "")).replace("\\", "/").endswith("/backend"):
        ok("desktop-bridge", "get_paths")
    elif paths is not None:
        fail("desktop-bridge", f"unexpected paths: {paths}")

    try:
        from dreamforge_mcp_server import mcp, run_dreamforge_cli  # noqa: E402

        ok("mcp", f"import ({mcp.name})")
        mcp_result = run_dreamforge_cli(["--dry-run", "--prompt", "verify", "--vram-profile", "16gb"])
        if mcp_result and mcp_result.get("ready") is True:
            ok("mcp", "run_dreamforge_cli dry-run")
        elif mcp_result:
            fail("mcp", f"dry-run: {mcp_result.get('status')}")
    except Exception as exc:
        fail("mcp", str(exc))

    try:
        from types import SimpleNamespace

        from dreamforge_agent_tools import compile_negative_prompt, normalize_generation_params

        params = normalize_generation_params(
            {
                "scene_prompt_en": "cafe portrait",
                "negative_prompt": ["happy expression", "cartoon look"],
            }
        )
        if not (params.get("prompt") or "").strip():
            fail("agent-prompt", "scene fields did not compile to prompt")
        neg = compile_negative_prompt(params.get("negative_prompt", ""), SimpleNamespace(), None)
        if "happy expression" not in neg:
            fail("agent-prompt", "list negative_prompt not joined")
        else:
            ok("agent-prompt", "JSON list negative + scene fields")

        from types import SimpleNamespace as NS
        from dreamforge_cli_direct import _job_namespace

        kontext_job = _job_namespace(
            NS(),
            normalize_generation_params(
                {
                    "prompt": "portrait",
                    "model": "flux1-dev-kontext_fp8_scaled.safetensors",
                    "use_case": "image_edit",
                    "edit_type": "kontext",
                    "cn_selection": "Custom...",
                }
            ),
        )
        if getattr(kontext_job, "negative_prompt", None) == []:
            fail("agent-prompt", "negative_prompt coerced incorrectly")
        else:
            ok("agent-prompt", "kontext params normalized")
    except Exception as exc:
        fail("agent-prompt", str(exc))

    for name in ("entry_with_update.py", "launch.py", "webui.py"):
        path = BACKEND_ROOT / name
        try:
            subprocess.run([py, "-m", "py_compile", str(path)], check=True, capture_output=True, text=True)
            ok("webui", f"py_compile {name}")
        except subprocess.CalledProcessError as exc:
            fail("webui", f"{name}: {exc.stderr.strip()[:200]}")

    try:
        subprocess.run(
            [py, "-s", str(BACKEND_ROOT / "arabic_poster_pipeline.py"), "--help"],
            check=True,
            capture_output=True,
            text=True,
            cwd=BACKEND_ROOT,
        )
        ok("arabic-poster", "--help")
    except subprocess.CalledProcessError as exc:
        fail("arabic-poster", exc.stderr.strip()[:200])

    tauri_dir = PROJECT_ROOT / "apps" / "desktop" / "src-tauri"
    desktop_dir = PROJECT_ROOT / "apps" / "desktop"
    npm = shutil.which("npm")
    if npm and desktop_dir.is_dir():
        tsc_cmd = desktop_dir / "node_modules" / ".bin" / "tsc.cmd"
        tsc_module = desktop_dir / "node_modules" / "typescript" / "bin" / "tsc"
        if not tsc_cmd.is_file() or not tsc_module.is_file():
            fail("desktop", "npm dependencies are missing or stale; run setup.bat or npm install in apps/desktop")
        else:
            run_checked("desktop", [npm, "run", "build"], cwd=desktop_dir, detail="npm run build")
    elif desktop_dir.is_dir():
        ok("desktop", "skipped npm build (npm not installed)")

    if shutil.which("cargo") and tauri_dir.is_dir():
        try:
            subprocess.run(["cargo", "check"], cwd=str(tauri_dir), check=True, capture_output=True, text=True)
            ok("desktop", "cargo check")
        except subprocess.CalledProcessError as exc:
            err = (exc.stderr or exc.stdout or "")[-500:]
            if "dreamforge_core" in err:
                fail("desktop", "stale cargo cache — run: cd apps/desktop/src-tauri && cargo clean")
            else:
                fail("desktop", err.strip()[:200])
    else:
        ok("desktop", "skipped (cargo not installed)")

    print()
    if FAILURES:
        print(f"{len(FAILURES)} check(s) failed:")
        for item in FAILURES:
            print(f"  - {item}")
        return 1

    print("All entrypoint checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
