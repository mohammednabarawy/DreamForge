from dreamforge_workflow_compatibility import analyze_workflow


def _native_graph():
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "model.safetensors"}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "a fox", "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": "blur", "clip": ["1", 1]}},
        "4": {"class_type": "EmptyLatentImage", "inputs": {"width": 512, "height": 512}},
        "5": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["4", 0], "steps": 20, "cfg": 6, "sampler_name": "euler", "scheduler": "normal"}},
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage", "inputs": {"images": ["6", 0]}},
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


def test_known_advanced_graph_is_not_native():
    graph = _native_graph()
    graph["8"] = {"class_type": "ControlNetLoader", "inputs": {"control_net_name": "depth.safetensors"}}
    assert analyze_workflow(graph)["state"] == "ADAPTABLE"


def test_disconnected_known_node_is_not_native():
    graph = _native_graph()
    graph["8"] = {"class_type": "CLIPTextEncode", "inputs": {"text": "unused", "clip": ["1", 1]}}
    assert analyze_workflow(graph)["state"] == "ADAPTABLE"
