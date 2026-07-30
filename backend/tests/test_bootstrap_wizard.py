"""Tests for bootstrap setup wizard and update check."""

from dreamforge_bootstrap import check_first_run_setup, check_github_updates


def test_check_first_run_setup():
    res = check_first_run_setup()
    assert isinstance(res, dict)
    assert "gpu" in res
    assert "vram_profile" in res


def test_check_github_updates():
    res = check_github_updates()
    assert isinstance(res, dict)
    assert "update_available" in res
    assert "current_version" in res
