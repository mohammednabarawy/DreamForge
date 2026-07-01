"""Convert ComfyUI UI workflow JSON to API prompt format (stdin -> stdout).

Must run with COMFY_ROOT on sys.path so custom node INPUT_TYPES are available.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _bootstrap_comfy() -> None:
    comfy_root = Path(os.environ.get("COMFY_ROOT", ".")).resolve()
    if not comfy_root.is_dir():
        raise SystemExit(f"COMFY_ROOT is not a directory: {comfy_root}")
    os.chdir(comfy_root)
    comfy_str = str(comfy_root)
    if comfy_str not in sys.path:
        sys.path.insert(0, comfy_str)
    tools_dir = Path(__file__).resolve().parent
    tools_str = str(tools_dir)
    if tools_str not in sys.path:
        sys.path.insert(0, tools_str)


def _init_comfy_nodes() -> None:
    import asyncio
    import contextlib
    import io

    import nodes

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        asyncio.run(nodes.init_extra_nodes(init_custom_nodes=True, init_api_nodes=False))
    noise = buffer.getvalue().strip()
    if noise:
        print(noise, file=sys.stderr)


def main() -> int:
    _bootstrap_comfy()
    _init_comfy_nodes()
    from comfy_ui_workflow_converter import WorkflowConverter

    raw = sys.stdin.read()
    if not raw.strip():
        raise SystemExit("Expected UI workflow JSON on stdin")
    data = json.loads(raw)
    if WorkflowConverter.is_api_format(data):
        api = data if "nodes" not in data else data
        root = data.get("prompt") if isinstance(data.get("prompt"), dict) else data
        print(json.dumps(root))
        return 0
    api = WorkflowConverter.convert_to_api(data)
    print(json.dumps(api))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
