"""Comprehensive GPU auto-detection service for DreamForge.

Inspects PyTorch CUDA / ROCm / MPS / system subprocesses to detect:
- GPU Vendor (NVIDIA, AMD, Intel, Apple, CPU)
- Device Name & Count
- Total & Free VRAM (in MB and GB)
- Driver / Compute API details
- Recommended DreamForge VRAM profile
"""

import os
import platform
import subprocess

from dreamforge_vram_profiles import detect_vram_profile, normalize_vram_profile


def detect_gpu() -> dict:
    """Return detailed GPU hardware info and recommended VRAM profile."""
    info = {
        "vendor": "Unknown",
        "device_name": "CPU Fallback",
        "device_count": 0,
        "vram_mb": 0,
        "vram_gb": 0.0,
        "backend": "cpu",
        "driver_info": "",
        "recommended_profile": "no_gpu",
    }

    # 1. Try PyTorch CUDA / ROCm
    try:
        import torch

        if torch.cuda.is_available():
            info["device_count"] = torch.cuda.device_count()
            props = torch.cuda.get_device_properties(0)
            info["device_name"] = props.name
            info["vram_mb"] = int(props.total_memory / (1024 * 1024))
            info["vram_gb"] = round(props.total_memory / (1024 * 1024 * 1024), 2)
            
            name_lower = props.name.lower()
            if "nvidia" in name_lower or "geforce" in name_lower or "rtx" in name_lower or "gtx" in name_lower or "quadro" in name_lower or "tesla" in name_lower:
                info["vendor"] = "NVIDIA"
                info["backend"] = "cuda"
            elif "amd" in name_lower or "radeon" in name_lower or "gfx" in name_lower:
                info["vendor"] = "AMD"
                info["backend"] = "rocm"
            elif "intel" in name_lower or "arc" in name_lower:
                info["vendor"] = "Intel"
                info["backend"] = "oneapi"
            else:
                info["vendor"] = "CUDA Device"
                info["backend"] = "cuda"

            info["recommended_profile"] = detect_vram_profile()
            return info

        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            info["vendor"] = "Apple"
            info["device_name"] = f"Apple Silicon ({platform.processor() or 'M-Series'})"
            info["device_count"] = 1
            info["backend"] = "mps"
            
            try:
                import psutil
                sys_ram = psutil.virtual_memory().total
                info["vram_mb"] = int(sys_ram / (1024 * 1024))
                info["vram_gb"] = round(sys_ram / (1024 * 1024 * 1024), 2)
            except Exception:
                pass

            info["recommended_profile"] = detect_vram_profile()
            return info
    except Exception:
        pass

    # 2. Subprocess fallback (nvidia-smi / wmic)
    if platform.system() == "Windows":
        try:
            out = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=gpu_name,memory.total", "--format=csv,noheader,nounits"],
                encoding="utf-8",
                errors="ignore",
                timeout=3,
            ).strip()
            if out:
                line = out.splitlines()[0]
                parts = line.split(",")
                if len(parts) >= 2:
                    info["vendor"] = "NVIDIA"
                    info["device_name"] = parts[0].strip()
                    info["vram_mb"] = int(parts[1].strip())
                    info["vram_gb"] = round(info["vram_mb"] / 1024, 2)
                    info["backend"] = "cuda"
                    info["recommended_profile"] = normalize_vram_profile("16gb" if info["vram_mb"] >= 14000 else "8gb" if info["vram_mb"] >= 7000 else "5gb")
                    return info
        except Exception:
            pass

    info["recommended_profile"] = "no_gpu"
    return info


if __name__ == "__main__":
    import json
    print(json.dumps(detect_gpu(), indent=2))
