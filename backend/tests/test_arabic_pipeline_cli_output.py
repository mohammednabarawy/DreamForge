import json
from unittest.mock import patch

from arabic_poster_pipeline import (
    _extract_paths_from_cli_stdout,
    _run_dreamforge_inprocess,
)


def test_extract_paths_from_cli_json_payload():
    stdout = json.dumps(
        {
            "status": "success",
            "results": [
                {
                    "status": "success",
                    "images": [{"path": "D:/DreamForge/outputs/dreamforge/comfy/out.png"}],
                }
            ],
            "images": [{"path": "D:/DreamForge/outputs/dreamforge/comfy/out.png"}],
        }
    )
    paths = _extract_paths_from_cli_stdout(stdout)
    assert paths == ["D:/DreamForge/outputs/dreamforge/comfy/out.png"]


def test_extract_paths_from_legacy_output_marker():
    stdout = 'noise\n__OUTPUT_JSON__=["D:/tmp/a.png"]\n'
    assert _extract_paths_from_cli_stdout(stdout) == ["D:/tmp/a.png"]


@patch("dreamforge_generation.run_generation")
def test_run_dreamforge_inprocess_reuses_generation(mock_run):
    mock_run.return_value = {
        "status": "success",
        "images": [{"path": "D:/DreamForge/outputs/dreamforge/comfy/scene.png"}],
    }
    paths = _run_dreamforge_inprocess(
        "Scene generation",
        width=1024,
        height=1024,
        prompt="lobby",
        base_model="test.safetensors",
    )
    assert paths == ["D:/DreamForge/outputs/dreamforge/comfy/scene.png"]
    mock_run.assert_called_once()
    _args, kwargs = mock_run.call_args
    assert kwargs.get("stream_sink") is not None
    base_args = mock_run.call_args.args[0]
    assert base_args.prompt == "lobby"
    assert base_args.model == "test.safetensors"
