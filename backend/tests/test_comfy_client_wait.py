from dreamforge_comfy_client import ComfyExecutionError, _extract_comfy_execution_error


def test_extract_comfy_execution_error_from_execution_error_message():
    node = {
        "outputs": {},
        "status": {
            "status_str": "error",
            "completed": True,
            "messages": [
                [
                    "execution_error",
                    {
                        "node_type": "CheckpointLoaderSimple",
                        "exception_message": "The paging file is too small for this operation to complete.",
                    },
                ]
            ],
        },
    }
    message = _extract_comfy_execution_error(node)
    assert message is not None
    assert "CheckpointLoaderSimple" in message
    assert "paging file" in message


def test_extract_comfy_execution_error_ignores_incomplete_prompt():
    node = {
        "outputs": {},
        "status": {"status_str": "running", "completed": False, "messages": []},
    }
    assert _extract_comfy_execution_error(node) is None


def test_extract_comfy_execution_error_returns_none_when_outputs_present():
    node = {
        "outputs": {"9": {"images": [{"filename": "out.png"}]}},
        "status": {"status_str": "success", "completed": True, "messages": []},
    }
    assert _extract_comfy_execution_error(node) is None


def test_comfy_execution_error_carries_prompt_id():
    err = ComfyExecutionError("boom", prompt_id="abc123")
    assert err.prompt_id == "abc123"
    assert str(err) == "boom"
