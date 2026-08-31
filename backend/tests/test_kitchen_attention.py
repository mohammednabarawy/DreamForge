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
