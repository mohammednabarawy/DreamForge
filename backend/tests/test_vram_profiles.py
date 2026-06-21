from dreamforge_vram_profiles import (
    apply_desktop_vram_env,
    detect_mac_vram_profile,
    normalize_vram_profile,
    profile_tier,
    profile_vram_budget_gb,
)


def test_mac_profile_tiers():
    assert profile_tier("mps_24gb") == "16gb"
    assert profile_tier("mps_16gb") == "16gb"
    assert profile_tier("mps_8gb") == "8gb"
    assert profile_tier("mps_4gb") == "5gb"


def test_mac_budgets():
    assert profile_vram_budget_gb("mps_24gb") == 24.0
    assert profile_vram_budget_gb("mps_8gb") == 8.0


def test_legacy_mps_alias(monkeypatch):
    monkeypatch.setattr(
        "dreamforge_vram_profiles.mps_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "dreamforge_vram_profiles.detect_mac_vram_profile",
        lambda: "mps_16gb",
    )
    assert normalize_vram_profile("mps") == "mps_16gb"


def test_detect_mac_from_ram(monkeypatch):
    monkeypatch.setattr(
        "dreamforge_vram_profiles._system_ram_gb",
        lambda: 18.0,
    )
    assert detect_mac_vram_profile() == "mps_16gb"


def test_desktop_mode_aliases_map_to_tier(monkeypatch):
    monkeypatch.setattr(
        "dreamforge_vram_profiles.mps_available",
        lambda: False,
    )
    assert normalize_vram_profile("normal") == "16gb"
    assert normalize_vram_profile("low") == "8gb"
    assert normalize_vram_profile("no") == "5gb"


def test_apply_desktop_vram_env(monkeypatch):
    monkeypatch.setattr(
        "dreamforge_vram_profiles.mps_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "dreamforge_vram_profiles.detect_vram_profile",
        lambda: "mps_16gb",
    )
    import os

    resolved = apply_desktop_vram_env("auto")
    assert resolved == "mps_16gb"
    assert os.environ["DREAMFORGE_VRAM_PROFILE"] == "mps_16gb"
    assert os.environ["DREAMFORGE_DESKTOP_VRAM_MODE"] == "16gb"


def test_comfy_launch_extra_args_recommended_on_16gb(monkeypatch):
    from dreamforge_vram_profiles import comfy_launch_extra_args

    monkeypatch.setenv("DREAMFORGE_VRAM_PROFILE", "16gb")
    monkeypatch.setattr("dreamforge_comfy_launch.mps_available", lambda: False)
    monkeypatch.setattr("dreamforge_comfy_launch.platform.system", lambda: "Windows")
    monkeypatch.setattr("dreamforge_comfy_launch.cuda_total_vram_gb", lambda: 16.0)
    assert comfy_launch_extra_args() == ("--lowvram", "--reserve-vram", "2")


def test_comfy_launch_extra_args_lowvram_reserves_vram_on_8gb(monkeypatch):
    from dreamforge_vram_profiles import comfy_launch_extra_args

    monkeypatch.setenv("DREAMFORGE_VRAM_PROFILE", "8gb")
    monkeypatch.setattr("dreamforge_comfy_launch.mps_available", lambda: False)
    monkeypatch.setattr("dreamforge_comfy_launch.platform.system", lambda: "Windows")
    monkeypatch.setattr("dreamforge_comfy_launch.cuda_total_vram_gb", lambda: 8.0)
    assert comfy_launch_extra_args() == ("--lowvram", "--reserve-vram", "1")


def test_comfy_launch_extra_args_cpu_profile(monkeypatch):
    from dreamforge_vram_profiles import comfy_launch_extra_args

    monkeypatch.setenv("DREAMFORGE_VRAM_PROFILE", "no_gpu")
    monkeypatch.setattr("dreamforge_vram_profiles.mps_available", lambda: False)
    assert comfy_launch_extra_args() == ("--cpu",)
