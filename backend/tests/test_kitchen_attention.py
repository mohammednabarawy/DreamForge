from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from dreamforge_comfy_client import ComfyExecutionError
import dreamforge_generation as generation


def test_kitchen_failure_retries_same_graph_once(monkeypatch):
    graph = {"1": {"class_type": "KSampler", "inputs": {"seed": 42, "steps": 8}}}
    original = deepcopy(graph)
    error = ComfyExecutionError("unsupported head_dim", details={"status": {"messages": [
        ["execution_error", {"traceback": ["File D:\\runtime\\comfy_kitchen\\sage_attention.py, in _validate_inputs"]}]
    ]}})
    run = Mock(side_effect=[error, ("prompt", "output")])
    monkeypatch.setattr(generation, "_run_comfy_workflow_once", run)
    managed = SimpleNamespace(_attached_external=False, config=SimpleNamespace(extra_args=("--use-ck-attention",)))
    monkeypatch.setattr("dreamforge_comfy_server.get_default_comfy_server", lambda: managed)
    restart = Mock(return_value=SimpleNamespace(base_url="http://127.0.0.1:8188"))
    monkeypatch.setattr("dreamforge_comfy_server.restart_managed_comfy_server", restart)
    monkeypatch.setattr("dreamforge_comfy_launch.comfy_launch_extra_args", lambda: ("--use-pytorch-cross-attention",))
    monkeypatch.setenv("DREAMFORGE_COMFY_ATTENTION", "auto")
    kwargs = dict(streaming=True, job_id="test", sample_steps=8, stream_sink=None, on_event=None)
    result = generation._run_comfy_workflow_with_retry(object(), graph, **kwargs)
    assert result[1:] == ("prompt", "output")
    assert graph == original and run.call_count == 2
    assert restart.call_args.kwargs["extra_args"] == ("--use-pytorch-cross-attention",)
    # A repeated kernel error must surface, and unrelated model errors never retry.
    run.reset_mock(side_effect=True)
    run.side_effect = error
    with pytest.raises(ComfyExecutionError):
        generation._run_comfy_workflow_with_retry(object(), graph, **kwargs)
    assert run.call_count == 2
    run.reset_mock(side_effect=True)
    run.side_effect = ComfyExecutionError("int8_linear model load failed")
    with pytest.raises(ComfyExecutionError):
        generation._run_comfy_workflow_with_retry(object(), graph, **kwargs)
    assert run.call_count == 1
    managed._attached_external = True
    run.reset_mock(side_effect=True)
    run.side_effect = error
    with pytest.raises(ComfyExecutionError):
        generation._run_comfy_workflow_with_retry(object(), graph, **kwargs)
    assert run.call_count == 1


def test_small_generation_keeps_native_sdpa_without_changing_sampling(monkeypatch):
    from dreamforge_comfy_launch import apply_small_image_attention_policy

    monkeypatch.setenv("DREAMFORGE_COMFY_ATTENTION", "auto")
    original = {"1": {"class_type": "KSampler", "inputs": {
        "model": ["0", 0], "seed": 42, "steps": 8,
    }}}
    options = dict(mode="txt2img", family="sd15", width=512, height=512,
                   kitchen_enabled=True, object_info={"ModelAttentionBackend": {}})
    graph = deepcopy(original)
    assert apply_small_image_attention_policy(graph, **options)
    patch = graph[graph["1"]["inputs"]["model"][0]]
    assert patch["inputs"] == {"model": ["0", 0], "attention": "pytorch attention"}
    assert graph["1"]["inputs"]["seed"] == 42 and graph["1"]["inputs"]["steps"] == 8
    assert not apply_small_image_attention_policy(graph, **options)
    for override in ({"mode": "custom_tool"}, {"family": "krea2"}, {"width": 1024, "height": 1024},
                     {"object_info": {}}, {"kitchen_enabled": False}):
        graph = deepcopy(original)
        assert not apply_small_image_attention_policy(graph, **{**options, **override})
        assert graph == original
    monkeypatch.setenv("DREAMFORGE_COMFY_ATTENTION", "kitchen")
    assert not apply_small_image_attention_policy(deepcopy(original), **options)


def test_measured_policy_respects_manual_choice_and_workflow_nodes(monkeypatch):
    from dreamforge_comfy_launch import apply_small_image_attention_policy
    monkeypatch.setenv("DREAMFORGE_COMFY_ATTENTION", "auto")
    monkeypatch.setattr("dreamforge_hardware_benchmark.measured_attention_backend", lambda *args: "kitchen")
    graph = {"1": {"class_type": "KSampler", "inputs": {"model": ["0", 0], "seed": 3}}}
    options = dict(mode="txt2img", family="sd15", width=512, height=512, model={},
                   kitchen_enabled=True, object_info={"ModelAttentionBackend": {
                       "input": {"required": {"attention": [["pytorch attention", "comfy kitchen attention"]]}}}})
    options["model"] = {"name": "model"}
    assert apply_small_image_attention_policy(graph, **options) == "kitchen"
    assert graph["2"]["inputs"]["attention"] == "comfy kitchen attention"
    assert not apply_small_image_attention_policy(graph, **options)
    graph = {"1": {"class_type": "KSampler", "inputs": {"model": ["0", 0], "seed": 3}}}
    monkeypatch.setenv("DREAMFORGE_COMFY_ATTENTION", "pytorch")
    assert not apply_small_image_attention_policy(graph, **options)
    assert len(graph) == 1


def test_kitchen_probe_is_bounded_and_native_failure_is_safe(monkeypatch):
    import subprocess
    import dreamforge_comfy_launch as launch
    run = Mock(return_value=SimpleNamespace(returncode=0, stderr=""))
    monkeypatch.setattr(launch.subprocess, "run", run)
    launch._kitchen_attention_usable.cache_clear()
    try:
        assert launch._kitchen_attention_usable(1)
        assert launch._kitchen_attention_usable(1)
        assert run.call_count == 1
        args, kwargs = run.call_args
        assert args[0][-1] == "1" and kwargs["timeout"] == 60
        assert kwargs["capture_output"]
        for failure in (SimpleNamespace(returncode=0xC0000005, stderr="native failure"),
                        subprocess.TimeoutExpired("probe", 60)):
            launch._kitchen_attention_usable.cache_clear()
            run.side_effect = failure if isinstance(failure, Exception) else None
            run.return_value = failure
            assert not launch._kitchen_attention_usable(1)
    finally:
        launch._kitchen_attention_usable.cache_clear()


def test_dynamic_vram_failure_retries_legacy_once_without_changing_image_settings(monkeypatch):
    import dreamforge_comfy_launch as launch
    graph = {"1": {"class_type": "KSampler", "inputs": {"seed": 42, "steps": 8}}}
    original = deepcopy(graph)
    error = ComfyExecutionError("CLIPTextEncode: VBAR allocation failed")
    run = Mock(side_effect=[error, ("prompt", "output")])
    monkeypatch.setattr(generation, "_run_comfy_workflow_once", run)
    managed = SimpleNamespace(_attached_external=False)
    monkeypatch.setattr("dreamforge_comfy_server.get_default_comfy_server", lambda: managed)
    restart = Mock(return_value=SimpleNamespace(base_url="http://127.0.0.1:8189"))
    monkeypatch.setattr("dreamforge_comfy_server.restart_managed_comfy_server", restart)
    monkeypatch.setenv("DREAMFORGE_DISABLE_DYNAMIC_VRAM", "")
    monkeypatch.setenv("DREAMFORGE_VRAM_PROFILE", "16gb")
    monkeypatch.setenv("DREAMFORGE_COMFY_FAST", "off")
    monkeypatch.setenv("DREAMFORGE_COMFY_ATTENTION", "off")
    monkeypatch.setattr(launch, "mps_available", lambda: False)
    monkeypatch.setattr(launch, "comfy_memory_tier", lambda *a: "16gb")
    monkeypatch.setattr(launch, "platform", SimpleNamespace(system=lambda: "Windows"))
    kwargs = dict(streaming=True, job_id="test", sample_steps=8, stream_sink=None, on_event=None)
    generation._run_comfy_workflow_with_retry(object(), graph, **kwargs)
    assert graph == original and run.call_count == 2
    assert "--disable-dynamic-vram" in restart.call_args.kwargs["extra_args"]
    assert "--lowvram" in restart.call_args.kwargs["extra_args"]
    assert generation.os.environ["DREAMFORGE_VRAM_PROFILE"] == "16gb"
    managed._attached_external = True
    restart.reset_mock()
    run.side_effect = error
    with pytest.raises(ComfyExecutionError):
        generation._run_comfy_workflow_with_retry(object(), graph, **kwargs)
    restart.assert_not_called()
