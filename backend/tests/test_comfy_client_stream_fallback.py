from unittest.mock import MagicMock, patch

from dreamforge_comfy_client import ComfyClient, ComfyPromptResult


def test_history_poll_state_done_when_outputs_present():
    client = ComfyClient("http://127.0.0.1:8188")
    client.history = MagicMock(return_value={"abc": {"outputs": {"9": {"images": []}}}})
    assert client.history_poll_state("abc") == "done"


def test_run_prompt_with_stream_falls_back_to_http_without_requeue():
    client = ComfyClient("http://127.0.0.1:8188")
    prompt_result = ComfyPromptResult(prompt_id="prompt-1")
    client.prompt = MagicMock(return_value=prompt_result)
    client.wait_for_outputs = MagicMock(return_value={"outputs": {"9": {"images": []}}})

    with patch("dreamforge_comfy_ws.ComfyPromptStreamSession") as session_cls:
        session = session_cls.return_value
        session.wait_until_done.side_effect = TimeoutError("ws timeout")

        res, node = client.run_prompt_with_stream(
            {"1": {"class_type": "Empty"}},
            on_event=lambda _payload: None,
        )

    assert res.prompt_id == "prompt-1"
    assert node["outputs"]
    client.prompt.assert_called_once()
    client.wait_for_outputs.assert_called_once_with(
        "prompt-1",
        timeout_s=600.0,
        poll_s=0.5,
    )
