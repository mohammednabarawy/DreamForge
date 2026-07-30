"""Tests for dreamforge_model_health module."""

from dreamforge_model_health import check_model_health


def test_check_model_health_runs():
    report = check_model_health()
    assert "status" in report
    assert "installed_summary" in report
    assert "families_detected" in report
    assert isinstance(report["corrupt_files"], list)
    assert isinstance(report["incomplete_downloads"], list)
    assert isinstance(report["missing_companions"], list)
