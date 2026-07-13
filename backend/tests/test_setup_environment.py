import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "setup_environment.py"
SPEC = importlib.util.spec_from_file_location("dreamforge_setup_environment", SCRIPT)
assert SPEC and SPEC.loader
setup_environment = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(setup_environment)


def test_python_compatibility_rejects_rosetta_on_apple_silicon(monkeypatch):
    python = Path("/fake/python")
    monkeypatch.setattr(setup_environment, "_python_version", lambda _python: (3, 12))
    monkeypatch.setattr(setup_environment, "_macos_host_arch", lambda: "arm64")
    monkeypatch.setattr(setup_environment, "_python_machine", lambda _python: "x86_64")

    assert setup_environment._python_is_compatible(python) is False


def test_python_compatibility_accepts_other_supported_platforms(monkeypatch):
    python = Path("/fake/python")
    monkeypatch.setattr(setup_environment, "_python_version", lambda _python: (3, 10))
    monkeypatch.setattr(setup_environment, "_macos_host_arch", lambda: None)

    assert setup_environment._python_is_compatible(python) is True


def test_incompatible_venv_is_preserved_before_rebuild(tmp_path, monkeypatch):
    venv = tmp_path / "venv"
    venv.mkdir()
    (venv / "old-environment.txt").write_text("keep", encoding="utf-8")
    monkeypatch.setattr(setup_environment, "VENV_DIR", venv)
    monkeypatch.setattr(setup_environment, "find_python", lambda: None)

    backup = setup_environment._preserve_incompatible_venv()

    assert backup == tmp_path / "venv.incompatible"
    assert not venv.exists()
    assert (backup / "old-environment.txt").read_text(encoding="utf-8") == "keep"
