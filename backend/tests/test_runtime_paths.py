import os
import sys
import zipfile
from pathlib import Path

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

os.environ["DREAMFORGE_SKIP_RUNTIME_PATHS"] = "1"

from dreamforge_embedded_python import (  # noqa: E402
    EMBED_DIR_NAME,
    embedded_python_dir,
    embedded_python_exe,
    resolve_install_root,
)
from dreamforge_bootstrap import extract_github_zip  # noqa: E402
from dreamforge_runtime_paths import (  # noqa: E402
    RuntimeConfig,
    ensure_model_subdirs,
    load_runtime_config,
    save_runtime_config,
    validate_models_folder,
)


def test_validate_models_folder_writable(tmp_path):
    models = tmp_path / "models"
    result = validate_models_folder(models, create=True)
    assert result["ok"] is True
    assert (models / "checkpoints").is_dir()


def test_validate_models_folder_detects_known_subdirs(tmp_path):
    models = tmp_path / "models"
    (models / "checkpoints").mkdir(parents=True)
    (models / "loras").mkdir()
    result = validate_models_folder(models)
    assert result["ok"] is True
    assert "checkpoints" in result["known_subdirs"]


def test_runtime_config_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("DREAMFORGE_DATA_ROOT", str(tmp_path))
    cfg = RuntimeConfig(
        data_root=str(tmp_path),
        models_root=str(tmp_path / "models"),
        models_source="managed",
        setup_complete=False,
    )
    path = save_runtime_config(cfg, tmp_path)
    assert path.is_file()
    loaded = load_runtime_config(tmp_path)
    assert loaded.models_source == "managed"
    assert loaded.setup_complete is False


def test_extract_github_zip_flattens_single_top_level(tmp_path):
    archive = tmp_path / "repo.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("ComfyUI-main/main.py", "print('ok')\n")
        zf.writestr("ComfyUI-main/README.md", "hello")
    payload = archive.read_bytes()
    dest = tmp_path / "comfy"
    extract_github_zip(payload, dest)
    assert (dest / "main.py").is_file()


def test_embedded_python_uses_python_embeded_dir_name(tmp_path, monkeypatch):
    monkeypatch.setenv("DREAMFORGE_INSTALL_ROOT", str(tmp_path))
    assert EMBED_DIR_NAME == "python_embeded"
    assert embedded_python_dir() == tmp_path / "python_embeded"
    assert embedded_python_exe() == tmp_path / "python_embeded" / "python.exe"


def test_resolve_install_root_from_backend_env(monkeypatch):
    monkeypatch.setenv("DREAMFORGE_BACKEND_ROOT", r"D:\DreamForge\backend")
    root = resolve_install_root()
    assert str(root).endswith("DreamForge") or root.name == "DreamForge"


def test_python_exe_prefers_install_root_embedded(monkeypatch, tmp_path):
    install = tmp_path / "DreamForge"
    backend = install / "backend"
    backend.mkdir(parents=True)
    embed = install / "python_embeded"
    embed.mkdir()
    (embed / "python.exe").write_text("", encoding="utf-8")
    monkeypatch.setenv("DREAMFORGE_BACKEND_ROOT", str(backend))
    monkeypatch.setenv("DREAMFORGE_INSTALL_ROOT", str(install))
    monkeypatch.setenv("DREAMFORGE_DATA_ROOT", str(tmp_path / "AppData" / "DreamForge"))
    from _paths import refresh_path_constants, resolve_python_exe

    refresh_path_constants()
    exe = resolve_python_exe()
    assert exe == embed / "python.exe"


def test_validate_empty_writable_external_folder(tmp_path):
    models = tmp_path / "external_models"
    models.mkdir()
    result = validate_models_folder(models, create=False)
    assert result["ok"] is True
    assert not result["errors"]
    assert result["warnings"]


def test_resolve_install_root_ignores_tauri_debug_target(monkeypatch, tmp_path):
    install = tmp_path / "DreamForge"
    backend = install / "backend"
    backend.mkdir(parents=True)
    embed = install / "python_embeded"
    embed.mkdir()
    (embed / "python.exe").write_text("", encoding="utf-8")
    target_debug = tmp_path / "apps" / "desktop" / "src-tauri" / "target" / "debug"
    target_debug.mkdir(parents=True)
    monkeypatch.setenv("DREAMFORGE_INSTALL_ROOT", str(target_debug))
    monkeypatch.setenv("DREAMFORGE_BACKEND_ROOT", str(target_debug / "backend"))
    from dreamforge_runtime_paths import resolve_install_root

    monkeypatch.setattr(
        "dreamforge_runtime_paths.REPO_ROOT",
        install,
        raising=False,
    )
    monkeypatch.setattr(
        "dreamforge_runtime_paths.BACKEND_ROOT",
        backend,
        raising=False,
    )
    assert resolve_install_root() == install.resolve()

