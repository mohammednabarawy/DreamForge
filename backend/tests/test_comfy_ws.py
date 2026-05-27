"""Tests for Comfy WebSocket preview/progress helpers (Krita-style)."""

from __future__ import annotations

import struct

import pytest

from dreamforge_comfy_ws import ComfyProgressTracker, extract_preview_image_bytes
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
