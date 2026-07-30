"""Model Health Check Utility for DreamForge.

Scans installed model directories to detect:
- 0-byte or corrupted model files
- Missing required companion assets (SDXL VAE, Flux CLIP, FaceID stack)
- Incomplete downloads (.part files left over)
- Generates actionable download/repair recommendations
"""

import json
from pathlib import Path
from typing import Any

from _paths import MODELS_ROOT
from dreamforge_cli_inventory import list_model_inventory
from dreamforge_identity import faceid_assets_available


def check_model_health() -> dict[str, Any]:
    inventory = list_model_inventory()
    categories = inventory.get("categories", {})

    corrupt_files: list[dict[str, Any]] = []
    incomplete_downloads: list[dict[str, Any]] = []
    installed_summary: dict[str, int] = {}
    families_found: set[str] = set()

    for category, files in categories.items():
        installed_summary[category] = len(files)
        for item in files:
            path_str = item.get("path")
            if not path_str:
                continue
            path = Path(path_str)
            if not path.exists() or path.stat().st_size == 0:
                corrupt_files.append({
                    "name": item.get("name"),
                    "path": path_str,
                    "category": category,
                    "reason": "0-byte or unreadable file",
                })
            family = item.get("family")
            if family:
                families_found.add(family)

    # Check for leftover .part files
    for part_file in MODELS_ROOT.rglob("*.part"):
        incomplete_downloads.append({
            "name": part_file.name,
            "path": str(part_file),
            "size_mb": round(part_file.stat().st_size / (1024 * 1024), 2),
        })

    # Check missing stack requirements
    missing_companions: list[dict[str, str]] = []

    # 1. SDXL VAE check
    has_sdxl = "sdxl" in families_found
    vae_files = categories.get("vae", [])
    has_sdxl_vae = any("sdxl" in f.get("name", "").lower() or "sdxl" in f.get("stem", "").lower() for f in vae_files)
    if has_sdxl and not has_sdxl_vae:
        missing_companions.append({
            "asset": "sdxl_vae",
            "family": "sdxl",
            "recommendation": "Download sdxl_vae.safetensors into models/vae/",
        })

    # 2. Flux CLIP encoders check
    has_flux = "flux" in families_found
    clip_files = categories.get("clip", []) + categories.get("text_encoders", [])
    has_clip_l = any("clip_l" in f.get("name", "").lower() for f in clip_files)
    has_t5xxl = any("t5" in f.get("name", "").lower() for f in clip_files)
    if has_flux and not (has_clip_l and has_t5xxl):
        missing_companions.append({
            "asset": "flux_text_encoders",
            "family": "flux",
            "recommendation": "Download clip_l.safetensors and t5xxl_fp8.safetensors into models/clip/",
        })

    # 3. FaceID stack check
    faceid_check = faceid_assets_available()
    if not faceid_check["ok"]:
        missing_companions.append({
            "asset": "faceid_stack",
            "family": "ipadapter_faceid",
            "missing_details": ", ".join(faceid_check["missing"]),
            "recommendation": "Run starter-pack installer or download missing FaceID assets",
        })

    status = "healthy"
    if corrupt_files or incomplete_downloads:
        status = "degraded"
    if missing_companions:
        status = "incomplete"

    return {
        "status": status,
        "installed_summary": installed_summary,
        "families_detected": list(families_found),
        "corrupt_files": corrupt_files,
        "incomplete_downloads": incomplete_downloads,
        "missing_companions": missing_companions,
    }


def main():
    report = check_model_health()
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
