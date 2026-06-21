"""Tests for edit lineage metadata and user style profile bridge."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from dreamforge_desktop_bridge import handle_request
from dreamforge_edit_lineage import build_edit_lineage, compute_plan_hash


def test_compute_plan_hash_is_stable():
    job = SimpleNamespace(workflow_plan=[{"operation": "generate"}])
    data = {"workflow_plan": [{"operation": "generate"}], "plan_id": "abc"}
    first = compute_plan_hash(data, job)
    second = compute_plan_hash(data, job)
    assert first == second
    assert first is not None
    assert len(first) == 16


def test_build_edit_lineage_includes_sources_and_outputs():
    job = SimpleNamespace(workflow_plan=[{"operation": "inpaint"}])
    lineage = build_edit_lineage(
        job=job,
        data={"workflow_plan": job.workflow_plan},
        input_image="/tmp/ref.png",
        inpaint_mask="/tmp/mask.png",
        edit_type="inpaint",
        output_images=["/tmp/out.png"],
    )
    assert lineage["plan_hash"]
    assert lineage["source_images"] == ["/tmp/ref.png"]
    assert lineage["inpaint_mask"] == "/tmp/mask.png"
    assert lineage["output_images"] == ["/tmp/out.png"]


def test_user_style_profile_bridge_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "dreamforge_user_style_profile.PROFILE_PATH",
        tmp_path / "user_style_profile.json",
    )

    get_payload = handle_request('{"cmd":"get_user_style_profile"}')
    assert get_payload.get("ok") is True
    assert get_payload["profile"]["enabled"] is True

    save_payload = handle_request(
        json.dumps(
            {
                "cmd": "save_user_style_profile",
                "params": {"enabled": False},
            }
        )
    )
    assert save_payload.get("ok") is True
    assert save_payload["profile"]["enabled"] is False

    clear_payload = handle_request('{"cmd":"clear_user_style_profile"}')
    assert clear_payload.get("ok") is True
    assert clear_payload["profile"]["generation_count"] == 0

    export_payload = handle_request('{"cmd":"export_user_style_profile"}')
    assert export_payload.get("ok") is True
    assert "path" in export_payload
