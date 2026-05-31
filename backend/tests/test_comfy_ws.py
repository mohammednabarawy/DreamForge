"""Tests for Comfy WebSocket preview/progress helpers (Krita-style)."""

from __future__ import annotations

import struct

import pytest

from dreamforge_comfy_ws import ComfyProgressTracker, ComfyPromptStreamSession, extract_preview_image_bytes
from dreamforge_comfy_server import parse_comfy_startup_url


def test_parse_comfy_startup_url():
    line = "To see the GUI go to: http://127.0.0.1:8189"
    assert parse_comfy_startup_url(line) == "http://127.0.0.1:8189"


def test_extract_preview_png_frame():
    png_header = b"\x89PNG\r\n\x1a\n" + b"x" * 16
    payload = struct.pack(">II", 1, 2) + png_header
    parsed = extract_preview_image_bytes(payload)
    assert parsed is not None
    data, fmt = parsed
    assert fmt == 2
    assert data == png_header


def test_extract_preview_jpeg_frame():
    jpeg = b"\xff\xd8\xff" + b"x" * 20
    payload = struct.pack(">II", 1, 1) + jpeg
    parsed = extract_preview_image_bytes(payload)
    assert parsed is not None
    data, fmt = parsed
    assert fmt == 1
    assert data == jpeg


def test_extract_preview_unencoded_frame():
    jpeg = b"\xff\xd8\xff" + b"z" * 10
    payload = struct.pack(">II", 2, 1) + jpeg
    parsed = extract_preview_image_bytes(payload)
    assert parsed is not None
    data, fmt = parsed
    assert fmt == 1
    assert data == jpeg


def test_extract_preview_with_metadata_frame():
    meta = b'{"node_id":"3"}'
    jpeg = b"\xff\xd8\xff" + b"y" * 12
    inner = struct.pack(">I", len(meta)) + meta + jpeg
    payload = struct.pack(">I", 4) + inner
    parsed = extract_preview_image_bytes(payload)
    assert parsed is not None
    data, fmt = parsed
    assert fmt == 1
    assert data == jpeg


def test_progress_tracker_weighted_value():
    tracker = ComfyProgressTracker(sample_count=10, node_count=2)
    for _ in range(5):
        tracker.handle({"type": "progress", "data": {"prompt_id": "job-1"}}, prompt_id="job-1")
    assert 0.0 < tracker.value < 1.0
    tracker.handle({"type": "executing", "data": {"prompt_id": "job-1"}}, prompt_id="job-1")
    assert tracker.value > 0.1
    tracker.handle({"type": "progress", "data": {"prompt_id": "other"}}, prompt_id="job-1")
    assert tracker._samples == 5


def test_wait_until_done_accepts_history_poll_done():
    session = ComfyPromptStreamSession("http://127.0.0.1:8188", "client-1", timeout_s=5.0)
    session.set_prompt_id("prompt-1")
    session._connected.set()

    def history_poll(prompt_id: str) -> str:
        assert prompt_id == "prompt-1"
        return "done"

    session.wait_until_done(history_poll=history_poll)


def test_wait_until_done_history_poll_error():
    session = ComfyPromptStreamSession("http://127.0.0.1:8188", "client-1", timeout_s=5.0)
    session.set_prompt_id("prompt-1")
    session._connected.set()

    with pytest.raises(RuntimeError, match="boom"):
        session.wait_until_done(history_poll=lambda _pid: "error:boom")


def test_count_comfy_prompt_nodes():
    from dreamforge_comfy_ws import count_comfy_prompt_nodes

    assert count_comfy_prompt_nodes({}) == 1
    assert count_comfy_prompt_nodes({"1": {}, "2": {}, "3": {}}) == 3


def test_guess_sample_count_from_prompt():
    from dreamforge_comfy_ws import guess_sample_count_from_prompt

    prompt = {
        "1": {"class_type": "KSampler", "inputs": {"steps": 12}},
        "2": {"class_type": "KSamplerAdvanced", "inputs": {"steps": 20, "start_at_step": 5}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": "hello"}},
    }
    assert guess_sample_count_from_prompt(prompt, fallback=10) == 27
    assert guess_sample_count_from_prompt({}, fallback=8) == 8


def test_prompt_id_from_job_id():
    from dreamforge_comfy_ws import prompt_id_from_job_id

    job_uuid = "550e8400-e29b-41d4-a716-446655440000"
    assert prompt_id_from_job_id(job_uuid) == job_uuid
    assert prompt_id_from_job_id("not-a-uuid") is None
    assert prompt_id_from_job_id("") is None


def test_live_preview_path_is_job_scoped():
    from dreamforge_comfy_ws import live_preview_path

    assert live_preview_path().name == "preview.jpg"
    assert live_preview_path("job-123").name == "preview-job-123.jpg"


def test_write_live_preview_writes_job_and_legacy(tmp_path, monkeypatch):
    from dreamforge_comfy_ws import write_live_preview

    monkeypatch.setattr("dreamforge_comfy_ws.PROJECT_ROOT", tmp_path)
    jpeg = b"\xff\xd8\xff" + b"x" * 64
    path = write_live_preview(jpeg, job_id="abc123")
    assert path.name == "preview-abc123.jpg"
    assert path.is_file()
    assert (tmp_path / "outputs" / "preview.jpg").is_file()


def test_start_raises_stored_connect_error(monkeypatch):
    monkeypatch.setattr("dreamforge_comfy_ws.ensure_websockets_available", lambda: None)

    def fake_run(self) -> None:
        self._error = RuntimeError("connect refused")
        self._connected.set()

    monkeypatch.setattr(ComfyPromptStreamSession, "_run", fake_run)
    session = ComfyPromptStreamSession("http://127.0.0.1:8188", "client-1")
    with pytest.raises(RuntimeError, match="connect refused"):
        session.start()
