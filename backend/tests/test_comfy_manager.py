"""Tests for ComfyUI-Manager install routing."""

from __future__ import annotations

from unittest.mock import MagicMock

from dreamforge_comfy_manager import (
    ManagerInstallResult,
    resolve_pack_install_strategy,
)


def test_resolve_pack_install_strategy_required_is_pinned():
    entry = {
        "id": "ComfyUI_essentials",
        "url": "https://github.com/cubiq/ComfyUI_essentials",
        "version": "abc",
    }
    assert resolve_pack_install_strategy(entry, "ComfyUI_essentials") == "pinned"


def test_resolve_pack_install_strategy_optional_layerstyle_is_manager():
    entry = {
        "id": "ComfyUI_LayerStyle",
        "install_via": "manager",
    }
    assert resolve_pack_install_strategy(entry, "ComfyUI_LayerStyle") == "manager"


def test_resolve_pack_install_strategy_unknown_defaults_manager():
    assert resolve_pack_install_strategy(None, "SomeUnknownPack") == "manager"


def test_install_custom_node_packs_routes_optional_to_manager(monkeypatch):
    from dreamforge_desktop_bridge import cmd_install_custom_node_packs

    manager_calls: list[list[str]] = []
    pinned_calls: list[str] = []

    def fake_manager(pack_ids, **kwargs):
        manager_calls.append(list(pack_ids))
        return ManagerInstallResult(installed=list(pack_ids), messages=["manager ok"])

    def fake_pinned(entry, **kwargs):
        pinned_calls.append(str(entry["id"]))

    monkeypatch.setattr(
        "dreamforge_comfy_manager.install_packs_via_manager",
        fake_manager,
    )
    monkeypatch.setattr(
        "dreamforge_comfy_manager.fix_packs_via_manager",
        lambda pack_ids, **kwargs: ManagerInstallResult(installed=pack_ids),
    )
    monkeypatch.setattr("dreamforge_comfy_install.ensure_custom_node_pack", fake_pinned)
    monkeypatch.setattr(
        "dreamforge_comfy_server.restart_managed_comfy_server",
        lambda **kwargs: MagicMock(),
    )
    monkeypatch.setattr(
        "dreamforge_comfy_server.fetch_comfy_object_info",
        lambda **kwargs: {},
    )

    result = cmd_install_custom_node_packs(
        {
            "pack_ids": ["ComfyUI_essentials", "ComfyUI_LayerStyle"],
            "strategy": "auto",
            "restart_comfy": False,
            "skip_object_info": True,
        }
    )

    assert "ComfyUI_LayerStyle" in manager_calls[0]
    assert "ComfyUI_essentials" in pinned_calls
    assert "ComfyUI_LayerStyle" in result["installed"]
    assert "ComfyUI_essentials" in result["installed"]


def test_missing_custom_node_pack_entries_include_install_via(monkeypatch):
    from dreamforge_workflow_planner import missing_custom_node_pack_entries

    monkeypatch.setattr(
        "dreamforge_workflow_planner.assess_custom_node_pack",
        lambda pack_id, object_info=None: {
            "pack_id": pack_id,
            "ready": False,
            "url": "https://github.com/chflame163/ComfyUI_LayerStyle",
            "missing_nodes": ["LayerMask: SegformerB2ClothesUltra"],
            "required_nodes": ["LayerMask: SegformerB2ClothesUltra"],
        },
    )
    entries = missing_custom_node_pack_entries(["ComfyUI_LayerStyle"])
    assert len(entries) == 1
    assert entries[0]["install_via"] == "manager"


def test_missing_workflow_model_entries_for_outfit_transfer(monkeypatch, tmp_path):
    from dreamforge_comfy_manager import missing_workflow_model_entries, workflow_model_ready

    monkeypatch.setattr("dreamforge_comfy_manager._models_root", lambda: tmp_path)
    entries = missing_workflow_model_entries(edit_task="outfit_transfer")
    
    segformer = next((e for e in entries if e["catalog_id"] == "segformer_b2_clothes"), None)
    assert segformer is not None
    assert segformer["kind"] == "workflow_model"
    assert segformer["expected_path"] == str(tmp_path / "segformer_b2_clothes/model.safetensors")

    model_dir = tmp_path / "segformer_b2_clothes"
    model_dir.mkdir(parents=True, exist_ok=True)
    (model_dir / "config.json").write_bytes(b"x" * 200)
    (model_dir / "preprocessor_config.json").write_bytes(b"x" * 200)
    (model_dir / "model.safetensors").write_bytes(b"0" * (100 * 1024 * 1024 + 1))
    assert workflow_model_ready("segformer_b2_clothes") is True
    missing_now = [e["catalog_id"] for e in missing_workflow_model_entries(edit_task="outfit_transfer")]
    assert "segformer_b2_clothes" not in missing_now


def test_workflow_model_directory_for_annotators_uses_comfy_root(monkeypatch, tmp_path):
    from dreamforge_comfy_manager import workflow_model_directory

    comfy_root = tmp_path / "engines" / "comfyui"
    comfy_root.mkdir(parents=True)
    monkeypatch.setattr("dreamforge_comfy_manager._comfy_root", lambda: comfy_root)

    depth_dir = workflow_model_directory("depth_anything_v2_vitl")
    assert depth_dir == (
        comfy_root
        / "custom_nodes/comfyui_controlnet_aux/ckpts/depth-anything/Depth-Anything-V2-Large"
    )


def test_missing_workflow_model_entries_for_portrait_master(monkeypatch, tmp_path):
    from dreamforge_comfy_manager import missing_workflow_model_entries

    comfy_root = tmp_path / "comfy"
    comfy_root.mkdir()
    monkeypatch.setattr("dreamforge_comfy_manager._comfy_root", lambda: comfy_root)
    monkeypatch.setattr("dreamforge_comfy_manager._models_root", lambda: tmp_path / "models")

    entries = missing_workflow_model_entries(edit_task="portrait_master")
    depth = next((item for item in entries if item["catalog_id"] == "depth_anything_v2_vitl"), None)
    assert depth is not None
    assert depth["filename"] == "depth_anything_v2_vitl.pth"
    assert "custom_nodes" in depth["expected_path"]
    assert depth["download_tier"] == "B"


def test_install_workflow_models_direct_download(monkeypatch, tmp_path):
    from dreamforge_comfy_manager import install_workflow_models, workflow_model_ready

    monkeypatch.setattr("dreamforge_comfy_manager._models_root", lambda: tmp_path)
    monkeypatch.setattr(
        "dreamforge_comfy_server.probe_comfy_http_base_url",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("offline")),
    )

    def fake_download(url, dest, *, min_bytes=1024):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"x" * max(min_bytes, 1024))

    monkeypatch.setattr("dreamforge_companion_download._download_file", fake_download)

    result = install_workflow_models(["segformer_b2_clothes"], prefer_manager=True)
    assert "segformer_b2_clothes" in result.installed
    assert workflow_model_ready("segformer_b2_clothes")


def test_cmd_install_workflow_models(monkeypatch, tmp_path):
    from dreamforge_desktop_bridge import cmd_install_workflow_models

    monkeypatch.setattr(
        "dreamforge_comfy_manager.install_workflow_models",
        lambda catalog_ids, **kwargs: __import__(
            "dreamforge_comfy_manager", fromlist=["ManagerInstallResult"]
        ).ManagerInstallResult(installed=list(catalog_ids), messages=["ok"]),
    )
    monkeypatch.setattr("dreamforge_comfy_manager.workflow_model_ready", lambda catalog_id: True)

    payload = cmd_install_workflow_models({"catalog_ids": ["segformer_b2_clothes"]})
    assert payload["ok"] is True
    assert payload["installed"] == ["segformer_b2_clothes"]


def test_manager_install_error_marks_security_block():
    from dreamforge_comfy_manager import manager_install_error

    entry = manager_install_error("SomePack", "HTTP 403 Security policy violation")
    assert entry["code"] == "manager_security_blocked"
    assert "hint" in entry


def test_make_progress_sink_writes_jsonl(tmp_path):
    from dreamforge_comfy_manager import make_progress_sink

    progress_file = tmp_path / "progress.jsonl"
    messages: list[str] = []
    sink = make_progress_sink(messages, progress_file=progress_file)
    sink("Installing pack A")
    sink("Downloading dependency")
    assert messages == ["Installing pack A", "Downloading dependency"]
    lines = progress_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert "Installing pack A" in lines[0]


def test_run_cm_cli_streams_lines(monkeypatch):
    from dreamforge_comfy_manager import _run_cm_cli

    class FakeStdout:
        def __init__(self):
            self._lines = ["line one\n", "line two\n"]

        def __iter__(self):
            return iter(self._lines)

    class FakeProc:
        stdout = FakeStdout()

        def wait(self):
            return 0

    captured: list[str] = []

    monkeypatch.setattr(
        "dreamforge_comfy_manager.ensure_comfyui_manager",
        lambda **kwargs: None,
    )
    monkeypatch.setattr("dreamforge_comfy_manager.manager_cm_cli_path", lambda: __import__("pathlib").Path("cm-cli.py"))
    monkeypatch.setattr("subprocess.Popen", lambda *args, **kwargs: FakeProc())

    completed = _run_cm_cli(["install", "ComfyUI_LayerStyle"], progress=captured.append)
    assert completed.returncode == 0
    assert captured == ["ComfyUI-Manager: install ComfyUI_LayerStyle", "line one", "line two"]
