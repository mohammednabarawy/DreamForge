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


def test_attention_selection_persists_only_valid_measurements(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import json
    import dreamforge_hardware_benchmark as benchmark
    monkeypatch.setattr("dreamforge_comfy_server.get_default_comfy_server", lambda: SimpleNamespace(_attached_external=False))
    monkeypatch.setattr("dreamforge_comfy_launch._kitchen_attention_usable", lambda index: True)
    monkeypatch.setattr("dreamforge_cli_inventory.resolve_generation_model", lambda name: {"family": "sd15"})
    monkeypatch.setattr(benchmark, "_attention_key", lambda *args: "runtime-model-size")
    cache = tmp_path / "attention.json"
    monkeypatch.setattr(benchmark, "_attention_cache_path", lambda: cache)
    def sample(**kwargs):
        return {"generation_executed": True, "warmup": {"output_valid": True},
                "summary": {"all_outputs_valid": True,
                            "median_s": 10 if kwargs["attention_backend"] == "pytorch" else 8}}
    monkeypatch.setattr(benchmark, "run_generation_benchmark", sample)
    result = benchmark.run_attention_benchmark(model="test", runs=3, steps=4, width=512, height=512)
    assert result["selected_attention"] == "kitchen"
    assert benchmark.measured_attention_backend({}, "txt2img", 512, 512) == "kitchen"
    before = cache.read_bytes()
    monkeypatch.setattr(benchmark, "run_generation_benchmark", lambda **kw: {"error": "failed"})
    assert benchmark.run_attention_benchmark(model="test", runs=3, steps=4, width=512, height=512)["error"]
    assert cache.read_bytes() == before
    monkeypatch.setattr(benchmark, "_attention_key", lambda *args: "updated-runtime")
    assert benchmark.measured_attention_backend({}, "txt2img", 512, 512) is None
    cache.write_text("[]")
    assert benchmark.measured_attention_backend({}, "txt2img", 512, 512) is None


def test_attention_key_changes_with_model_runtime_and_dimensions(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import dreamforge_hardware_benchmark as benchmark
    import sys
    torch = SimpleNamespace(cuda=SimpleNamespace(get_device_properties=None), version=SimpleNamespace(cuda="test"))
    monkeypatch.setitem(sys.modules, "torch", torch)
    import _paths
    for name in ("main.py", "requirements.txt", "comfy/ldm/modules/attention.py"):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("test")
    weight = tmp_path / "model.safetensors"
    weight.write_bytes(b"model")
    monkeypatch.setattr(_paths, "COMFY_ROOT", tmp_path)
    monkeypatch.setattr("dreamforge_preflight._resolve_model_path", lambda model: weight)
    monkeypatch.setattr(torch.cuda, "get_device_properties", lambda index: SimpleNamespace(name="GPU", total_memory=16, uuid="gpu-id"))
    versions = {"torch": "2.8", "comfy-kitchen": "0.2", "comfy-aimdo": "0.4"}
    monkeypatch.setattr(benchmark.importlib.metadata, "version", lambda name: versions[name])
    monkeypatch.setattr(benchmark, "_attention_driver_version", lambda: "test-driver")
    key = benchmark._attention_key({}, "txt2img", 512, 512)
    assert key != benchmark._attention_key({}, "txt2img", 768, 768)
    assert key != benchmark._attention_key({}, "krea2_edit", 512, 512)
    with monkeypatch.context() as environment:
        environment.setenv("DREAMFORGE_DISABLE_DYNAMIC_VRAM", "1")
        assert key != benchmark._attention_key({}, "txt2img", 512, 512)
    versions["comfy-kitchen"] = "0.3"
    assert key != benchmark._attention_key({}, "txt2img", 512, 512)
    versions["comfy-kitchen"] = "0.2"
    weight.write_bytes(b"new model")
    assert key != benchmark._attention_key({}, "txt2img", 512, 512)
