from pathlib import Path

from dreamforge_embedded_python import preserve_executable_path


def test_preserve_executable_path_does_not_dereference_venv_symlink(tmp_path):
    base = tmp_path / "base-python"
    base.write_text("", encoding="utf-8")
    venv_python = tmp_path / "venv" / "bin" / "python"
    venv_python.parent.mkdir(parents=True)
    venv_python.symlink_to(base)

    assert preserve_executable_path(venv_python) == venv_python
    assert preserve_executable_path(venv_python) != venv_python.resolve()
