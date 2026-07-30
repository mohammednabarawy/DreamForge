"""System Repair & Troubleshooting Utility for DreamForge.

Provides single-command repair operations:
- Clear temporary render cache & incomplete downloads (.part files)
- Re-verify ComfyUI custom nodes setup
- Repair configuration files (creates backup before reset)
- Validate Python environment & markers
"""

import json
import shutil
import time
from pathlib import Path
from typing import Any

from _paths import BACKEND_ROOT, MODELS_ROOT, TEMP_ROOT
from dreamforge_bootstrap_markers import write_node_deps_marker, write_python_stack_marker
from dreamforge_gpu_detect import detect_gpu


def run_system_repair(
    clear_cache: bool = True,
    reset_config: bool = False,
    reverify_nodes: bool = True,
) -> dict[str, Any]:
    logs: list[str] = []
    actions_taken: list[str] = []

    # 1. Clear temp/staging cache
    if clear_cache:
        logs.append("Cleaning temporary render cache and part files...")
        cleaned_files = 0
        cleaned_bytes = 0

        for part_file in MODELS_ROOT.rglob("*.part"):
            try:
                cleaned_bytes += part_file.stat().st_size
                part_file.unlink()
                cleaned_files += 1
            except Exception as e:
                logs.append(f"Failed to remove {part_file.name}: {e}")

        if TEMP_ROOT.exists():
            for item in TEMP_ROOT.glob("*"):
                try:
                    if item.is_file():
                        cleaned_bytes += item.stat().st_size
                        item.unlink()
                        cleaned_files += 1
                    elif item.is_dir():
                        shutil.rmtree(item)
                        cleaned_files += 1
                except Exception as e:
                    logs.append(f"Cache clean notice for {item.name}: {e}")

        cleaned_mb = round(cleaned_bytes / (1024 * 1024), 2)
        actions_taken.append(f"Purged {cleaned_files} temp/part items ({cleaned_mb} MB reclaimed)")

    # 2. Reset app config with backup
    if reset_config:
        config_path = BACKEND_ROOT / "config.txt"
        if config_path.exists():
            backup_path = BACKEND_ROOT / f"config.txt.bak.{int(time.time())}"
            try:
                shutil.copy2(config_path, backup_path)
                config_path.unlink()
                actions_taken.append(f"Reset config.txt (backed up to {backup_path.name})")
            except Exception as e:
                logs.append(f"Config reset failed: {e}")

    # 3. Re-verify runtime markers
    if reverify_nodes:
        try:
            write_python_stack_marker()
            write_node_deps_marker()
            actions_taken.append("Refreshed Python runtime stack & node dependency markers")
        except Exception as e:
            logs.append(f"Marker refresh failed: {e}")

    gpu_info = detect_gpu()

    return {
        "status": "success",
        "actions_taken": actions_taken,
        "gpu": gpu_info,
        "logs": logs,
    }


def main():
    report = run_system_repair()
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
