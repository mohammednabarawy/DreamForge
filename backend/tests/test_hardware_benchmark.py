from dreamforge_hardware_benchmark import _p95, run_policy_benchmark


def test_policy_benchmark_covers_all_supported_classes():
    results = run_policy_benchmark()
    names = {result["hardware_class"] for result in results}
    assert "cpu_only" in names
    assert "nvidia_32gb_plus" in names
    assert "amd_rocm_linux_16gb_plus" in names
    assert "apple_silicon_32gb_plus" in names
    assert all(result["generation_executed"] is False for result in results)


def test_p95_uses_nearest_rank_not_always_maximum():
    assert _p95([float(value) for value in range(1, 21)]) == 19.0
