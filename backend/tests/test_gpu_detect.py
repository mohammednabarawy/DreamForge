import sys
import types

from dreamforge_gpu_detect import _base_info, _finalize, _non_torch_graphics, _torch_detect


def test_finalize_classifies_requested_hardware_buckets():
    cases = [
        ("NVIDIA", "cuda", 5, "nvidia_4_6gb"),
        ("NVIDIA", "cuda", 8, "nvidia_8gb"),
        ("NVIDIA", "cuda", 12, "nvidia_12gb"),
        ("NVIDIA", "cuda", 16, "nvidia_16gb"),
        ("NVIDIA", "cuda", 24, "nvidia_24gb_plus"),
        ("AMD", "rocm", 6, "amd_4_8gb"),
        ("AMD", "rocm", 8, "amd_8_12gb"),
        ("AMD", "rocm", 16, "amd_rocm_linux_16gb_plus"),
        ("Apple", "mps", 8, "apple_silicon_8gb"),
        ("Apple", "mps", 16, "apple_silicon_16gb"),
        ("Apple", "mps", 24, "apple_silicon_24gb_plus"),
        ("Apple", "mps", 32, "apple_silicon_32gb_plus"),
    ]
    for vendor, backend, gb, expected in cases:
        result = _finalize({
            "vendor": vendor,
            "backend": backend,
            "vram_gb": gb,
            "os": "Linux" if backend == "rocm" else "Windows",
        })
        assert result["hardware_class"] == expected


def test_cpu_fallback_is_explicit():
    result = _finalize({"vendor": "Unknown", "backend": "cpu", "vram_gb": 0, "os": "Windows"})
    assert result["hardware_class"] == "cpu_only"


def test_torch_detection_selects_best_secondary_adapter(monkeypatch):
    props = [
        types.SimpleNamespace(name="Intel UHD", total_memory=1 * 1024**3, major=0),
        types.SimpleNamespace(name="NVIDIA RTX 4090", total_memory=24 * 1024**3, major=8),
    ]
    cuda = types.SimpleNamespace(
        is_available=lambda: True, device_count=lambda: 2,
        get_device_properties=lambda index: props[index],
        mem_get_info=lambda index: ((512 if index == 0 else 20 * 1024) * 1024**2, props[index].total_memory),
        get_device_capability=lambda index: (8, 9),
    )
    fake_torch = types.SimpleNamespace(
        __version__="2.8.0", version=types.SimpleNamespace(cuda="12.8", hip=None),
        cuda=cuda, backends=types.SimpleNamespace(mps=types.SimpleNamespace(is_available=lambda: False)),
    )
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    info = _base_info()
    assert _torch_detect(info) is True
    assert info["selected_device_index"] == 1
    assert info["device_name"] == "NVIDIA RTX 4090"
    assert info["device_count"] == 2


def test_windows_fallback_selects_amd_after_intel(monkeypatch):
    rows = '[{"Name":"Intel UHD","AdapterRAM":1073741824},{"Name":"AMD Radeon RX 7900 XTX","AdapterRAM":25769803776}]'
    monkeypatch.setattr("dreamforge_gpu_detect.platform.system", lambda: "Windows")
    monkeypatch.setattr("dreamforge_gpu_detect.shutil.which", lambda name: "powershell.exe" if name == "powershell" else None)
    monkeypatch.setattr("dreamforge_gpu_detect.subprocess.check_output", lambda *args, **kwargs: rows)
    info = _base_info()
    assert _non_torch_graphics(info) is True
    assert info["vendor"] == "AMD"
    assert info["selected_device_index"] == 1
