"""Audit ComfyUI built-in and custom-node requirements for DreamForge model families."""

from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from _paths import COMFY_ROOT, extend_sys_path

extend_sys_path()

BUILTIN_NODES = [
    "TextEncodeQwenImageEdit",
    "TextEncodeQwenImageEditPlus",
    "ModelSamplingAuraFlow",
    "CFGNorm",
    "ImageScaleToTotalPixels",
    "UNETLoader",
    "UnetLoaderGGUF",
    "CLIPLoader",
    "CLIPLoaderGGUF",
    "VAELoader",
    "DualCLIPLoader",
    "QuadrupleCLIPLoader",
    "EmptySD3LatentImage",
    "ReferenceLatent",
    "FluxGuidance",
    "ModelSamplingSD3",
    "EmptyHiDreamO1LatentImage",
    "HiDreamO1ReferenceImages",
    "KSampler",
    "VAEEncode",
    "LoadImage",
    "SaveImage",
]


def main() -> int:
    from dreamforge_comfy_client import ComfyClient
    from dreamforge_comfy_server import ensure_comfy_running
    from dreamforge_krita_recipes import COMFY_INSTALL_RECIPE
    from dreamforge_workflow_planner import assess_custom_node_pack

    server = ensure_comfy_running(timeout_s=90.0)
    info = ComfyClient(server.base_url).object_info(timeout_s=30.0)

    missing_builtin = [n for n in BUILTIN_NODES if n not in info]
    print(f"Comfy server: {server.base_url}")
    print(f"Registered nodes: {len(info)}")
    print(f"Missing built-in nodes: {missing_builtin or 'none'}")

    packs = COMFY_INSTALL_RECIPE["required_custom_nodes"] + COMFY_INSTALL_RECIPE.get(
        "optional_custom_nodes", []
    )
    not_ready = []
    for entry in packs:
        status = assess_custom_node_pack(entry["id"], object_info=info)
        pin = entry.get("version", "")
        custom_dir = COMFY_ROOT / "custom_nodes"
        installed = ""
        for path in custom_dir.iterdir() if custom_dir.is_dir() else []:
            norm = path.name.lower().replace("-", "").replace("_", "")
            pid = entry["id"].lower().replace("-", "").replace("_", "")
            if pid in norm or norm in pid:
                try:
                    import subprocess

                    installed = (
                        subprocess.check_output(
                            ["git", "-C", str(path), "rev-parse", "HEAD"],
                            text=True,
                        ).strip()
                    )
                except Exception:
                    installed = "unknown"
                break
        ok = status.get("ready")
        print(
            f"{'OK' if ok else 'FAIL'}: {entry['id']} "
            f"(pinned={pin[:8] if pin else '-'}, installed={installed[:8] if installed else '-'})"
        )
        if status.get("missing_nodes"):
            print(f"  missing_nodes: {status['missing_nodes']}")
        if not ok:
            not_ready.append({**status, "pinned": pin, "installed": installed, "url": entry.get("url")})

    report = {
        "missing_builtin": missing_builtin,
        "not_ready_packs": not_ready,
        "qwen_nodes": [k for k in info if "Qwen" in k or "qwen" in k.lower()],
    }
    print(json.dumps(report, indent=2))
    return 1 if missing_builtin or not_ready else 0


if __name__ == "__main__":
    raise SystemExit(main())
