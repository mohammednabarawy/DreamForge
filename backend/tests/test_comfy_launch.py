import pytest


@pytest.fixture(autouse=True)
def _no_speed_flags(monkeypatch):
    """Default tests to deterministic flags: no --fast, no attention backend."""
    monkeypatch.setenv("DREAMFORGE_COMFY_FAST", "off")
    monkeypatch.setenv("DREAMFORGE_COMFY_ATTENTION", "off")
    monkeypatch.setattr("dreamforge_comfy_launch.mps_available", lambda: False)
    monkeypatch.setattr("dreamforge_comfy_launch._kitchen_attention_usable", lambda index: False)


def _force_legacy(monkeypatch):
    """Pretend Dynamic VRAM is unavailable (torch < 2.8 / non-NVIDIA)."""
    monkeypatch.setattr("dreamforge_comfy_launch.supports_dynamic_vram", lambda: False)


def _force_dynamic(monkeypatch):
    """Pretend Dynamic VRAM is available (torch >= 2.8 on NVIDIA)."""
    monkeypatch.setattr("dreamforge_comfy_launch.supports_dynamic_vram", lambda: True)


# --- Legacy memory mode (torch < 2.8 or non-NVIDIA) -------------------------


def test_comfy_launch_16gb_windows_streams_to_avoid_oom(monkeypatch):
    from dreamforge_comfy_launch import comfy_launch_extra_args

    _force_legacy(monkeypatch)
    monkeypatch.setenv("DREAMFORGE_VRAM_PROFILE", "16gb")
    monkeypatch.setattr("dreamforge_comfy_launch.cuda_total_vram_gb", lambda: 15.9)
    monkeypatch.setattr("dreamforge_comfy_launch.platform.system", lambda: "Windows")
    # 16 GB Windows on old torch streams weights (lowvram) with a generous reserve
    # so large model families don't full-load and OOM-crash on back-to-back runs.
    assert comfy_launch_extra_args() == ("--lowvram", "--reserve-vram", "3")


def test_comfy_launch_16gb_non_windows_uses_default(monkeypatch):
    from dreamforge_comfy_launch import comfy_launch_extra_args

    _force_legacy(monkeypatch)
    monkeypatch.setenv("DREAMFORGE_VRAM_PROFILE", "16gb")
    monkeypatch.setattr("dreamforge_comfy_launch.cuda_total_vram_gb", lambda: 15.9)
    monkeypatch.setattr("dreamforge_comfy_launch.platform.system", lambda: "Linux")
    assert comfy_launch_extra_args() == ()


def test_comfy_launch_12gb_uses_lowvram(monkeypatch):
    from dreamforge_comfy_launch import comfy_launch_extra_args

    _force_legacy(monkeypatch)
    monkeypatch.setenv("DREAMFORGE_VRAM_PROFILE", "16gb")
    monkeypatch.setattr("dreamforge_comfy_launch.cuda_total_vram_gb", lambda: 12.0)
    monkeypatch.setattr("dreamforge_comfy_launch.platform.system", lambda: "Windows")
    assert comfy_launch_extra_args() == ("--lowvram", "--reserve-vram", "1.25")


def test_comfy_launch_8gb_windows(monkeypatch):
    from dreamforge_comfy_launch import comfy_launch_extra_args

    _force_legacy(monkeypatch)
    monkeypatch.setenv("DREAMFORGE_VRAM_PROFILE", "8gb")
    monkeypatch.setattr("dreamforge_comfy_launch.cuda_total_vram_gb", lambda: 8.0)
    monkeypatch.setattr("dreamforge_comfy_launch.platform.system", lambda: "Windows")
    assert comfy_launch_extra_args() == ("--lowvram", "--reserve-vram", "1")


def test_comfy_launch_24gb_uses_highvram(monkeypatch):
    from dreamforge_comfy_launch import comfy_launch_extra_args

    _force_legacy(monkeypatch)
    monkeypatch.setenv("DREAMFORGE_VRAM_PROFILE", "16gb")
    monkeypatch.setattr("dreamforge_comfy_launch.cuda_total_vram_gb", lambda: 24.0)
    monkeypatch.setattr("dreamforge_comfy_launch.platform.system", lambda: "Windows")
    assert comfy_launch_extra_args() == ("--highvram", "--reserve-vram", "1.5")


def test_comfy_launch_cpu_profile(monkeypatch):
    from dreamforge_comfy_launch import comfy_launch_extra_args

    monkeypatch.setenv("DREAMFORGE_VRAM_PROFILE", "no_gpu")
    assert comfy_launch_extra_args() == ("--cpu",)


# --- Dynamic VRAM mode (torch >= 2.8 on NVIDIA) -----------------------------


def test_dynamic_vram_16gb_windows_drops_lowvram(monkeypatch):
    from dreamforge_comfy_launch import comfy_launch_extra_args

    _force_dynamic(monkeypatch)
    monkeypatch.setenv("DREAMFORGE_VRAM_PROFILE", "16gb")
    monkeypatch.setattr("dreamforge_comfy_launch.cuda_total_vram_gb", lambda: 15.9)
    monkeypatch.setattr("dreamforge_comfy_launch.platform.system", lambda: "Windows")
    # No --lowvram (no-op under Dynamic VRAM) and no --disable-dynamic-vram;
    # aimdo manages offload, --reserve-vram becomes its headroom target.
    assert comfy_launch_extra_args() == ("--reserve-vram", "1.5")


def test_dynamic_vram_24gb_keeps_dynamic_not_highvram(monkeypatch):
    from dreamforge_comfy_launch import comfy_launch_extra_args

    _force_dynamic(monkeypatch)
    monkeypatch.setenv("DREAMFORGE_VRAM_PROFILE", "16gb")
    monkeypatch.setattr("dreamforge_comfy_launch.cuda_total_vram_gb", lambda: 24.0)
    monkeypatch.setattr("dreamforge_comfy_launch.platform.system", lambda: "Windows")
    # --highvram would disable Dynamic VRAM, so it must NOT be emitted.
    assert comfy_launch_extra_args() == ("--reserve-vram", "1")


def test_dynamic_vram_includes_fast_and_attention(monkeypatch):
    from dreamforge_comfy_launch import comfy_launch_extra_args

    _force_dynamic(monkeypatch)
    monkeypatch.setenv("DREAMFORGE_VRAM_PROFILE", "16gb")
    monkeypatch.setenv("DREAMFORGE_COMFY_FAST", "fp16_accumulation")
    monkeypatch.setenv("DREAMFORGE_COMFY_ATTENTION", "auto")
    monkeypatch.setenv("DREAMFORGE_COMFY_BACKEND", "cuda")
    monkeypatch.setenv("DREAMFORGE_COMFY_FAST_BENCHMARK_OK", "1")
    monkeypatch.setenv("DREAMFORGE_COMPUTE_CAPABILITY", "8.9")
    monkeypatch.setattr("dreamforge_comfy_launch.cuda_total_vram_gb", lambda: 15.9)
    monkeypatch.setattr("dreamforge_comfy_launch.platform.system", lambda: "Windows")
    monkeypatch.setattr(
        "dreamforge_comfy_launch._module_available",
        lambda name: name == "sageattention",
    )
    assert comfy_launch_extra_args() == (
        "--reserve-vram",
        "1.5",
        "--fast",
        "fp16_accumulation",
        "--use-sage-attention",
    )


def test_never_emits_disable_dynamic_vram(monkeypatch):
    from dreamforge_comfy_launch import comfy_launch_extra_args

    _force_dynamic(monkeypatch)
    monkeypatch.setenv("DREAMFORGE_VRAM_PROFILE", "auto")
    monkeypatch.setattr("dreamforge_comfy_launch.cuda_total_vram_gb", lambda: 15.9)
    monkeypatch.setattr("dreamforge_comfy_launch.platform.system", lambda: "Windows")
    assert "--disable-dynamic-vram" not in comfy_launch_extra_args()


# --- Optional speed flag helpers --------------------------------------------


def test_fast_args_off(monkeypatch):
    from dreamforge_comfy_launch import fast_args

    monkeypatch.setenv("DREAMFORGE_COMFY_FAST", "off")
    assert fast_args() == []


def test_fast_args_all_is_bare_flag(monkeypatch):
    from dreamforge_comfy_launch import fast_args

    monkeypatch.setenv("DREAMFORGE_COMFY_FAST", "all")
    assert fast_args() == ["--fast"]


def test_fast_args_default(monkeypatch):
    from dreamforge_comfy_launch import fast_args

    monkeypatch.delenv("DREAMFORGE_COMFY_FAST", raising=False)
    monkeypatch.setenv("DREAMFORGE_COMFY_BACKEND", "cuda")
    monkeypatch.delenv("DREAMFORGE_FAST_BENCHMARK_OK", raising=False)
    monkeypatch.delenv("DREAMFORGE_COMFY_FAST_BENCHMARK_OK", raising=False)
    assert fast_args() == []
    monkeypatch.setenv("DREAMFORGE_COMFY_FAST_BENCHMARK_OK", "1")
    monkeypatch.setenv("DREAMFORGE_COMPUTE_CAPABILITY", "8.9")
    assert fast_args() == ["--fast", "fp16_accumulation"]


def test_fast_args_disabled_for_non_nvidia_backend(monkeypatch):
    from dreamforge_comfy_launch import fast_args

    monkeypatch.delenv("DREAMFORGE_COMFY_FAST", raising=False)
    monkeypatch.setenv("DREAMFORGE_COMFY_BACKEND", "rocm")
    assert fast_args() == []


def test_attention_flag_prefers_sage(monkeypatch):
    from dreamforge_comfy_launch import attention_flag

    monkeypatch.setenv("DREAMFORGE_COMFY_ATTENTION", "auto")
    monkeypatch.setattr(
        "dreamforge_comfy_launch._module_available",
        lambda name: name in {"sageattention", "flash_attn"},
    )
    monkeypatch.setenv("DREAMFORGE_COMFY_BACKEND", "cuda")
    monkeypatch.setenv("DREAMFORGE_COMFY_FAST_BENCHMARK_OK", "1")
    monkeypatch.setenv("DREAMFORGE_COMPUTE_CAPABILITY", "8.9")
    assert attention_flag() == "--use-sage-attention"


def test_sage_flash_auto_requires_benchmark_gate(monkeypatch):
    from dreamforge_comfy_launch import attention_flag

    monkeypatch.setenv("DREAMFORGE_COMFY_ATTENTION", "auto")
    monkeypatch.setenv("DREAMFORGE_COMFY_BACKEND", "cuda")
    monkeypatch.delenv("DREAMFORGE_COMFY_FAST_BENCHMARK_OK", raising=False)
    monkeypatch.setattr("dreamforge_comfy_launch._module_available", lambda name: True)
    assert attention_flag() is None


def test_selected_cuda_device_reaches_launch_args(monkeypatch):
    from dreamforge_comfy_launch import apply_runtime_optimization_env, comfy_launch_extra_args

    monkeypatch.setattr(
        "dreamforge_gpu_detect.detect_gpu",
        lambda: {
            "backend": "cuda",
            "hardware_class": "nvidia_24gb_plus",
            "selected_device_index": 1,
            "detection_sources": ["torch.cuda"],
        },
    )
    monkeypatch.setattr("dreamforge_comfy_launch.mps_available", lambda: False)
    monkeypatch.setattr("dreamforge_comfy_launch.cuda_total_vram_gb", lambda: 24.0)
    monkeypatch.setattr("dreamforge_comfy_launch.supports_dynamic_vram", lambda: False)
    monkeypatch.setenv("DREAMFORGE_COMFY_FAST", "off")
    monkeypatch.setenv("DREAMFORGE_COMFY_DEVICE_INDEX", "restore-after-test")
    apply_runtime_optimization_env()
    args = comfy_launch_extra_args()
    assert args[args.index("--cuda-device") + 1] == "1"


def test_attention_flag_off(monkeypatch):
    from dreamforge_comfy_launch import attention_flag

    monkeypatch.setenv("DREAMFORGE_COMFY_ATTENTION", "off")
    monkeypatch.setattr("dreamforge_comfy_launch._module_available", lambda name: True)
    assert attention_flag() is None


def test_kitchen_attention_selection_and_safe_fallback(monkeypatch):
    from dreamforge_comfy_launch import attention_flag

    monkeypatch.setenv("DREAMFORGE_COMFY_BACKEND", "cuda")
    monkeypatch.setenv("DREAMFORGE_COMFY_DEVICE_INDEX", "1")
    monkeypatch.setenv("DREAMFORGE_COMFY_ATTENTION", "auto")
    monkeypatch.setattr("dreamforge_comfy_launch._module_available", lambda name: True)
    monkeypatch.setattr("dreamforge_comfy_launch._kitchen_attention_usable", lambda index: index == 1)
    assert attention_flag() == "--use-ck-attention"
    monkeypatch.setenv("DREAMFORGE_COMFY_ATTENTION", "pytorch")
    assert attention_flag() == "--use-pytorch-cross-attention"
    monkeypatch.setenv("DREAMFORGE_COMFY_ATTENTION", "sage")
    assert attention_flag() == "--use-sage-attention"
    monkeypatch.setenv("DREAMFORGE_COMFY_ATTENTION", "kitchen")
    monkeypatch.setattr("dreamforge_comfy_launch._kitchen_attention_usable", lambda index: False)
    assert attention_flag() == "--use-pytorch-cross-attention"
    monkeypatch.setenv("DREAMFORGE_COMFY_BACKEND", "rocm")
    monkeypatch.setattr("dreamforge_comfy_launch._kitchen_attention_usable", lambda index: True)
    assert attention_flag() == "--use-pytorch-cross-attention"
