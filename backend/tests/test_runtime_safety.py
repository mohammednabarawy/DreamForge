import io
import os
import zipfile
from pathlib import Path

import pytest
import dreamforge_bootstrap as bootstrap
import dreamforge_embedded_python as embedded
import dreamforge_cli_inventory as inventory


def archive(files):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as zf:
        for path, data in files.items():
            zf.writestr("repo-commit/" + path, data)
    return stream.getvalue()


def test_archive_failure_preserves_existing_runtime(tmp_path, monkeypatch):
    dest = tmp_path / "comfyui"
    dest.mkdir()
    (dest / "main.py").write_bytes(b"old")
    (dest / "custom_nodes").mkdir()
    (dest / "custom_nodes" / "user.py").write_bytes(b"custom")
    before = {str(p.relative_to(dest)): p.read_bytes() for p in dest.rglob("*") if p.is_file()}
    for payload in (b"bad zip", archive({"../../escape.py": "bad"})):
        monkeypatch.setattr(bootstrap, "_download_bytes", lambda *a, **kw: payload)
        with pytest.raises((ValueError, zipfile.BadZipFile)):
            bootstrap.checkout_github_commit("https://github.com/Comfy-Org/ComfyUI", "new", dest)
        assert before == {str(p.relative_to(dest)): p.read_bytes() for p in dest.rglob("*") if p.is_file()}
    payload = archive({"main.py": "new", "z.py": "new"})
    monkeypatch.setattr(bootstrap, "_download_bytes", lambda *a, **kw: payload)
    replace = os.replace
    def fail_last(source, target):
        if Path(target).name == "z.py":
            raise PermissionError("locked")
        return replace(source, target)
    monkeypatch.setattr(bootstrap.os, "replace", fail_last)
    with pytest.raises(PermissionError):
        bootstrap.checkout_github_commit("https://github.com/Comfy-Org/ComfyUI", "new", dest)
    assert before == {str(p.relative_to(dest)): p.read_bytes() for p in dest.rglob("*") if p.is_file()}


def test_archive_success_keeps_user_files_and_backup(tmp_path, monkeypatch):
    dest = tmp_path / "comfyui"
    (dest / "custom_nodes").mkdir(parents=True)
    (dest / "custom_nodes" / "user.py").write_bytes(b"custom")
    (dest / "main.py").write_bytes(b"old")
    payload = archive({"main.py": "new", "custom_nodes/user.py": "upstream"})
    monkeypatch.setattr(bootstrap, "_download_bytes", lambda *a, **kw: payload)
    bootstrap.checkout_github_commit("https://github.com/Comfy-Org/ComfyUI", "new", dest)
    assert (dest / "main.py").read_bytes() == b"new"
    assert (dest / "custom_nodes/user.py").read_bytes() == b"custom"
    assert next((tmp_path / ".dreamforge-backups").rglob("main.py")).read_bytes() == b"old"
    (dest / ".git").mkdir()
    with pytest.raises(RuntimeError, match="preserved"):
        bootstrap.checkout_github_commit("https://github.com/Comfy-Org/ComfyUI", "other", dest)


def test_edit_readiness_uses_selected_model_and_lora(monkeypatch):
    monkeypatch.setattr(inventory, "resolve_generation_model", lambda name: {"name": name, "family": name})
    monkeypatch.setattr(inventory, "check_model_dependencies", lambda model: [])
    monkeypatch.setattr(inventory, "companion_file_present", lambda *a, **kw: False)
    missing = inventory.check_studio_resources("edit", model_name="krea2")
    assert [m["id"] for m in missing] == ["lora_krea2_identity_edit_v1_2"]
    assert "55bdbc7985fe5a9bc8e0f179a5101bbe32c98086" in missing[0]["url"]
    assert inventory.check_studio_resources("edit", model_name="qwen_image_edit") == []
    monkeypatch.setattr(inventory, "companion_file_present", lambda *a, **kw: True)
    assert inventory.check_studio_resources("edit", model_name="krea2") == []


def test_gpu_install_constrains_versions_and_detects_regressions(monkeypatch):
    good = {"versions": {"torch": "2.8.0+cu128"}, "working": {"torch": True, "gpu": True}}
    monkeypatch.setattr(embedded, "gpu_stack_snapshot", lambda python: good)
    monkeypatch.setattr(embedded, "_pip_conflicts", lambda python: {"pre-existing conflict"})
    with embedded.protected_gpu_install(Path("python")) as env:
        assert "torch==2.8.0+cu128" in Path(env["PIP_CONSTRAINT"]).read_text()
    with pytest.raises(RuntimeError, match="validation failed"):
        with embedded.protected_gpu_install(Path("python")):
            monkeypatch.setattr(embedded, "gpu_stack_snapshot", lambda python: {
                "versions": {"torch": "2.9.0"}, "working": {"torch": True, "gpu": False},
            })


def test_failed_resolver_does_not_install(monkeypatch):
    from contextlib import nullcontext
    import subprocess
    calls = []
    monkeypatch.setattr(embedded, "protected_gpu_install", lambda python: nullcontext({}))
    def fail(command, **kwargs):
        calls.append(command)
        raise subprocess.CalledProcessError(1, command)
    monkeypatch.setattr(bootstrap.subprocess, "check_call", fail)
    with pytest.raises(subprocess.CalledProcessError):
        bootstrap._pip_install(Path("python"), ["-r", "requirements.txt"])
    assert len(calls) == 1 and "--dry-run" in calls[0]
