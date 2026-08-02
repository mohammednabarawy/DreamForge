"""Hardware detection shared by the worker, diagnostics, and model routing."""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
from typing import Any

from dreamforge_vram_profiles import hardware_class, normalize_vram_profile


def _ram_snapshot() -> tuple[int, int]:
    try:
        import psutil

        vm = psutil.virtual_memory()
        return int(vm.total / (1024 * 1024)), int(vm.available / (1024 * 1024))
    except Exception:
        return 0, 0


def _base_info() -> dict[str, Any]:
    total_ram, available_ram = _ram_snapshot()
    return {
        "vendor": "Unknown",
        "device_name": "CPU Fallback",
        "device_count": 0,
        "selected_device_index": None,
        "devices": [],
        "vram_mb": 0,
        "vram_gb": 0.0,
        "free_vram_mb": None,
        "backend": "cpu",
        "gpu_architecture": None,
        "compute_capability": None,
        "driver_info": "",
        "torch_version": None,
        "cuda_version": None,
        "hip_version": None,
        "os": platform.system(),
        "total_ram_mb": total_ram,
        "available_ram_mb": available_ram,
        "recommended_profile": "no_gpu",
        "hardware_class": "cpu_only",
        "support_level": "cpu",
        "detection_sources": [],
        "confidence": "low",
        "warnings": [],
        "fallback_reason": None,
    }


def _finalize(info: dict[str, Any]) -> dict[str, Any]:
    info["hardware_class"] = hardware_class(
        vendor=info.get("vendor"), backend=info.get("backend"),
        vram_gb=info.get("vram_gb"), os_name=info.get("os"),
        mps=info.get("backend") == "mps",
    )
    return info


def _classify_device(name: str, hip: bool) -> tuple[str, str, str]:
    lower = name.lower()
    if hip or any(token in lower for token in ("amd", "radeon", "gfx")):
        return "AMD", "rocm", "experimental"
    if any(token in lower for token in ("nvidia", "geforce", "rtx", "gtx", "quadro", "tesla")):
        return "NVIDIA", "cuda", "supported"
    if "intel" in lower or "arc" in lower:
        return "Intel", "oneapi", "experimental"
    return "CUDA Device", "cuda", "experimental"


def _torch_detect(info: dict[str, Any]) -> bool:
    try:
        import torch

        info["torch_version"] = getattr(torch, "__version__", None)
        info["cuda_version"] = getattr(torch.version, "cuda", None)
        info["hip_version"] = getattr(torch.version, "hip", None)
        if torch.cuda.is_available():
            hip = bool(info["hip_version"])
            count = max(1, int(torch.cuda.device_count()))
            devices: list[dict[str, Any]] = []
            for index in range(count):
                try:
                    props = torch.cuda.get_device_properties(index)
                    name = str(getattr(props, "name", f"CUDA device {index}"))
                    vendor, backend, support = _classify_device(name, hip)
                    total_mb = int(float(props.total_memory) / (1024 * 1024))
                    free_mb = None
                    try:
                        free, total = torch.cuda.mem_get_info(index)
                        free_mb = int(free / (1024 * 1024))
                        total_mb = int(total / (1024 * 1024))
                    except Exception:
                        pass
                    capability = None
                    try:
                        capability = ".".join(map(str, torch.cuda.get_device_capability(index)))
                    except Exception:
                        pass
                    devices.append({
                        "index": index,
                        "vendor": vendor,
                        "backend": backend,
                        "device_name": name,
                        "vram_mb": total_mb,
                        "free_vram_mb": free_mb,
                        "compute_capability": capability,
                        "gpu_architecture": getattr(props, "major", None),
                        "support_level": support,
                    })
                except Exception as exc:
                    info["warnings"].append(f"GPU {index} properties unavailable: {exc}")
            if not devices:
                return False
            def device_score(device: dict[str, Any]) -> tuple[int, int, int]:
                vendor_score = {"NVIDIA": 3, "AMD": 2, "Intel": 1}.get(device["vendor"], 0)
                return vendor_score, int(device.get("free_vram_mb") or 0), int(device.get("vram_mb") or 0)
            selected = max(devices, key=device_score)
            info.update({
                "vendor": selected["vendor"],
                "device_name": selected["device_name"],
                "device_count": len(devices),
                "selected_device_index": selected["index"],
                "devices": devices,
                "vram_mb": selected["vram_mb"],
                "vram_gb": round(float(selected["vram_mb"]) / 1024, 2),
                "free_vram_mb": selected["free_vram_mb"],
                "backend": selected["backend"],
                "gpu_architecture": selected["gpu_architecture"],
                "compute_capability": selected["compute_capability"],
                "support_level": selected["support_level"],
                "detection_sources": ["torch.cuda", "torch.device_properties", "all_adapters"],
                "confidence": "high",
            })
            info["recommended_profile"] = normalize_vram_profile(
                "32gb" if info["vram_gb"] >= 30 else
                "24gb" if info["vram_gb"] >= 22 else
                "16gb" if info["vram_gb"] >= 14 else
                "12gb" if info["vram_gb"] >= 10.5 else
                "8gb" if info["vram_gb"] >= 7 else "5gb"
            )
            return True
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            ram_gb = (info["total_ram_mb"] or 0) / 1024
            info.update({
                "vendor": "Apple", "device_name": f"Apple Silicon ({platform.processor() or 'M-Series'})",
                "device_count": 1, "backend": "mps", "vram_mb": info["total_ram_mb"],
                "vram_gb": round(ram_gb, 2), "support_level": "supported",
                "detection_sources": ["torch.backends.mps", "system_memory"], "confidence": "high",
                "recommended_profile": normalize_vram_profile(
                    "mps_32gb" if ram_gb >= 30 else "mps_24gb" if ram_gb >= 22 else
                    "mps_16gb" if ram_gb >= 14 else "mps_8gb"
                ),
            })
            return True
    except Exception as exc:
        info["warnings"].append(f"PyTorch detection unavailable: {exc}")
    return False


def _nvidia_smi(info: dict[str, Any]) -> bool:
    if not shutil.which("nvidia-smi"):
        return False
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=gpu_name,memory.total,driver_version", "--format=csv,noheader,nounits"],
            encoding="utf-8", errors="ignore", timeout=3,
        ).strip()
        if not out:
            return False
        rows = []
        for line in out.splitlines():
            parts = [part.strip() for part in line.split(",")]
            if len(parts) >= 2:
                try:
                    rows.append({"name": parts[0], "mb": int(float(parts[1])), "driver": parts[2] if len(parts) > 2 else ""})
                except ValueError:
                    continue
        if not rows:
            return False
        selected = max(rows, key=lambda row: row["mb"])
        name, mb, driver = selected["name"], selected["mb"], selected["driver"]
        info.update({
            "vendor": "NVIDIA", "device_name": name, "device_count": len(rows),
            "selected_device_index": rows.index(selected),
            "devices": [{"index": i, "vendor": "NVIDIA", "backend": "cuda", "device_name": row["name"], "vram_mb": row["mb"], "free_vram_mb": None, "support_level": "supported"} for i, row in enumerate(rows)],
            "vram_mb": mb, "vram_gb": round(mb / 1024, 2), "backend": "cuda",
            "driver_info": driver, "support_level": "supported",
            "detection_sources": ["nvidia-smi"], "confidence": "medium",
            "recommended_profile": normalize_vram_profile(
                "32gb" if mb >= 30 * 1024 else "24gb" if mb >= 22 * 1024 else
                "16gb" if mb >= 14 * 1024 else "12gb" if mb >= 10.5 * 1024 else
                "8gb" if mb >= 7 * 1024 else "5gb"
            ),
        })
        return True
    except Exception as exc:
        info["warnings"].append(f"nvidia-smi detection failed: {exc}")
        return False


def _non_torch_graphics(info: dict[str, Any]) -> bool:
    """Best-effort vendor fallback when the installed Torch cannot initialize a GPU."""
    if platform.system() == "Windows" and shutil.which("powershell"):
        try:
            raw = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command",
                 "Get-CimInstance Win32_VideoController | Select-Object Name,AdapterRAM | ConvertTo-Json -Compress"],
                encoding="utf-8", errors="ignore", timeout=5,
            )
            rows = json.loads(raw)
            rows = rows if isinstance(rows, list) else [rows]
            candidates = []
            for index, row in enumerate(rows):
                name = str(row.get("Name") or "")
                lower = name.lower()
                if "nvidia" in lower or "geforce" in lower or "rtx" in lower or "gtx" in lower:
                    vendor, backend, support = "NVIDIA", "cuda", "supported"
                elif "amd" in lower or "radeon" in lower:
                    vendor, backend, support = "AMD", "rocm", "experimental"
                elif "intel" in lower or "arc" in lower:
                    vendor, backend, support = "Intel", "oneapi", "experimental"
                else:
                    continue
                mb = int(row.get("AdapterRAM") or 0) // (1024 * 1024)
                candidates.append({"index": index, "vendor": vendor, "backend": backend, "support_level": support, "device_name": name, "vram_mb": mb})
            if candidates:
                selected = max(candidates, key=lambda item: ({"NVIDIA": 3, "AMD": 2, "Intel": 1}[item["vendor"]], item["vram_mb"]))
                info.update({
                    "vendor": selected["vendor"], "device_name": selected["device_name"], "backend": selected["backend"],
                    "device_count": len(candidates), "selected_device_index": selected["index"],
                    "devices": candidates, "vram_mb": selected["vram_mb"], "vram_gb": round(selected["vram_mb"] / 1024, 2),
                    "support_level": selected["support_level"], "confidence": "medium",
                    "detection_sources": ["Win32_VideoController", "all_adapters"],
                    "warnings": [f"{selected['vendor']} GPU detected but PyTorch did not expose a usable backend"],
                    "fallback_reason": "GPU detected by OS, but the installed PyTorch runtime did not expose a usable accelerator",
                    "recommended_profile": normalize_vram_profile(
                        "32gb" if selected["vram_mb"] >= 30 * 1024 else "24gb" if selected["vram_mb"] >= 22 * 1024 else
                        "16gb" if selected["vram_mb"] >= 14 * 1024 else "12gb" if selected["vram_mb"] >= 10.5 * 1024 else
                        "8gb" if selected["vram_mb"] >= 7 * 1024 else "5gb"
                    ) if selected["vram_mb"] else "no_gpu",
                })
                return True
        except Exception:
            pass
    for tool, args in (("rocminfo", ["rocminfo"]), ("lspci", ["lspci", "-nn"])):
        if not shutil.which(tool):
            continue
        try:
            raw = subprocess.check_output(args, encoding="utf-8", errors="ignore", timeout=5)
            if "amd" in raw.lower() or "radeon" in raw.lower() or "gfx" in raw.lower():
                info.update({
                    "vendor": "AMD", "device_name": "AMD GPU (runtime fallback)", "backend": "rocm",
                    "support_level": "experimental", "confidence": "low",
                    "detection_sources": [tool],
                    "warnings": ["AMD hardware found, but VRAM could not be read from the fallback tool"],
                    "fallback_reason": "AMD runtime fallback could not read VRAM; using conservative ROCm policy",
                })
                return True
        except Exception:
            pass
    return False


def detect_gpu() -> dict[str, Any]:
    """Return one canonical, JSON-safe hardware snapshot."""
    info = _base_info()
    if _torch_detect(info) or _nvidia_smi(info) or _non_torch_graphics(info):
        return _finalize(info)
    if platform.system() == "Linux" and shutil.which("rocminfo"):
        info["detection_sources"].append("rocminfo")
        info["warnings"].append("ROCm tool found but PyTorch did not expose a usable device")
        info["support_level"] = "experimental"
    info["warnings"].append("No accelerated backend detected; generation will use CPU mode")
    info["fallback_reason"] = "No usable CUDA, ROCm, MPS, or other accelerated backend was detected"
    return _finalize(info)


if __name__ == "__main__":
    print(json.dumps(detect_gpu(), indent=2))
