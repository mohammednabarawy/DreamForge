from dreamforge_workflow_compatibility import analyze_workflow


def _native_graph():
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "model.safetensors"}},
        "2": {"class_type": "KSampler", "inputs": {"model": ["1", 0]}},
        "3": {"class_type": "SaveImage", "inputs": {"images": ["2", 0]}},
    }


def test_known_api_graph_is_native():
    result = analyze_workflow(_native_graph())
    assert result["state"] == "NATIVE"
    assert result["can_execute"] is True
    assert result["dependencies"] == ["model.safetensors"]


def test_ui_graph_is_adaptable():
    result = analyze_workflow({"nodes": [{"id": 1, "type": "CheckpointLoaderSimple"}, {"id": 2, "type": "KSampler"}, {"id": 3, "type": "SaveImage"}]})
    assert result["state"] == "ADAPTABLE"
    assert result["format"] == "ui"


def test_unknown_node_is_comfy_only():
    result = analyze_workflow({**_native_graph(), "4": {"class_type": "SomeCustomMagic", "inputs": {}}})
    assert result["state"] == "COMFY_ONLY"
    assert result["can_execute"] is False


def test_command_node_is_invalid_and_blocked():
    result = analyze_workflow({"1": {"class_type": "ExecutePython", "inputs": {"code": "print(1)"}}})
    assert result["state"] == "INVALID"
    assert result["security"]["blocked"] is True
