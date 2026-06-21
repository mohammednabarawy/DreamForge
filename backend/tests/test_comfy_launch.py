import pytest


def test_comfy_launch_16gb_windows_reserves_two_gb(monkeypatch):
    from dreamforge_comfy_launch import comfy_launch_extra_args

    monkeypatch.setenv("DREAMFORGE_VRAM_PROFILE", "16gb")
    monkeypatch.setattr("dreamforge_comfy_launch.mps_available", lambda: False)
    monkeypatch.setattr("dreamforge_comfy_launch.cuda_total_vram_gb", lambda: 15.9)
    monkeypatch.setattr("dreamforge_comfy_launch.platform.system", lambda: "Windows")
    assert comfy_launch_extra_args() == ("--lowvram", "--reserve-vram", "2")


def test_comfy_launch_12gb_uses_lowvram(monkeypatch):
    from dreamforge_comfy_launch import comfy_launch_extra_args

    monkeypatch.setenv("DREAMFORGE_VRAM_PROFILE", "16gb")
    monkeypatch.setattr("dreamforge_comfy_launch.mps_available", lambda: False)
    monkeypatch.setattr("dreamforge_comfy_launch.cuda_total_vram_gb", lambda: 12.0)
    monkeypatch.setattr("dreamforge_comfy_launch.platform.system", lambda: "Windows")
    assert comfy_launch_extra_args() == ("--lowvram", "--reserve-vram", "1.25")


def test_comfy_launch_8gb_windows(monkeypatch):
    from dreamforge_comfy_launch import comfy_launch_extra_args

    monkeypatch.setenv("DREAMFORGE_VRAM_PROFILE", "8gb")
    monkeypatch.setattr("dreamforge_comfy_launch.mps_available", lambda: False)
    monkeypatch.setattr("dreamforge_comfy_launch.cuda_total_vram_gb", lambda: 8.0)
    monkeypatch.setattr("dreamforge_comfy_launch.platform.system", lambda: "Windows")
    assert comfy_launch_extra_args() == ("--lowvram", "--reserve-vram", "1")


def test_comfy_launch_cpu_profile(monkeypatch):
    from dreamforge_comfy_launch import comfy_launch_extra_args

    monkeypatch.setenv("DREAMFORGE_VRAM_PROFILE", "no_gpu")
    monkeypatch.setattr("dreamforge_comfy_launch.mps_available", lambda: False)
    assert comfy_launch_extra_args() == ("--cpu",)
