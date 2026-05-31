from __future__ import annotations

import os
from pathlib import Path

import pytest


def test_cleanup_stale_managed_comfy_removes_dead_pidfile(tmp_path, monkeypatch):
    from dreamforge_comfy_server import (
        _clear_comfy_pidfile,
        _comfy_pidfile_path,
        _write_comfy_pidfile,
        cleanup_stale_managed_comfy,
    )

    pidfile = tmp_path / "comfy.server.pid"
    monkeypatch.setattr("dreamforge_comfy_server._COMFY_PIDFILE", pidfile)

    _write_comfy_pidfile(999_999)
    assert pidfile.is_file()

    cleanup_stale_managed_comfy(force=True)
    assert not pidfile.exists()


def test_register_managed_comfy_shutdown_is_idempotent(monkeypatch):
    import dreamforge_comfy_server as mod

    monkeypatch.setattr(mod, "_shutdown_registered", False)
    calls: list[str] = []

    def _stop(*_args, **_kwargs):
        calls.append("stop")

    monkeypatch.setattr(mod, "stop_managed_comfy_server", _stop)
    monkeypatch.setattr(mod.atexit, "register", lambda fn: calls.append("register"))

    mod.register_managed_comfy_shutdown()
    mod.register_managed_comfy_shutdown()

    assert calls.count("register") == 1


def test_find_foreign_comfy_pids_uses_http_probe_and_main_py(monkeypatch):
    import dreamforge_comfy_server as mod

    monkeypatch.setattr(mod, "_pids_running_comfy_main", lambda _root=None: [111])
    monkeypatch.setattr(mod, "_is_port_open", lambda port, host="127.0.0.1": port == 8188)
    monkeypatch.setattr(mod, "_is_comfy_http_server", lambda port, host="127.0.0.1": port == 8188)
    monkeypatch.setattr(mod, "_localhost_listening_pids", lambda port: [222] if port == 8188 else [])
    monkeypatch.setattr(mod, "_comfy_pidfile_path", lambda: Path("/nonexistent/pid"))

    pids = mod._find_foreign_comfy_pids(exclude_pids={os.getpid()})
    assert pids == [111, 222]


def test_cleanup_all_foreign_comfy_servers_kills_and_clears_pidfile(tmp_path, monkeypatch):
    import dreamforge_comfy_server as mod

    pidfile = tmp_path / "comfy.server.pid"
    monkeypatch.setattr(mod, "_COMFY_PIDFILE", pidfile)
    monkeypatch.setattr(mod, "_find_foreign_comfy_pids", lambda **kwargs: [4242])
    monkeypatch.setattr(mod, "_process_alive", lambda pid: pid == 4242)
    terminated: list[int] = []
    monkeypatch.setattr(mod, "_terminate_process_tree", lambda pid, force=True: terminated.append(pid))
    monkeypatch.setattr(mod, "_wait_for_ports_closed", lambda *_args, **_kwargs: None)

    killed = mod.cleanup_all_foreign_comfy_servers(force=True)
    assert killed == [4242]
    assert terminated == [4242]
    assert not pidfile.exists()


def test_is_comfy_http_server_accepts_system_stats_payload(monkeypatch):
    import dreamforge_comfy_server as mod

    class _Resp:
        def read(self):
            return b'{"system": {"ram": 1}, "devices": []}'

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(mod.urllib.request, "urlopen", lambda *_args, **_kwargs: _Resp())
    assert mod._is_comfy_http_server(8188) is True


def test_recover_managed_comfy_server_restarts_dead_process(monkeypatch):
    import dreamforge_comfy_server as mod

    class _FakeProc:
        def __init__(self):
            self.returncode = 1

        def poll(self):
            return self.returncode

    server = mod.ManagedComfyServer(mod.ComfyServerConfig())
    server.proc = _FakeProc()
    server.pid = 4242
    monkeypatch.setattr(mod, "_DEFAULT_SERVER", server)
    monkeypatch.setattr(mod, "ensure_dreamforge_extra_model_paths", lambda *_args, **_kwargs: None)
    started: list[float] = []

    def _fake_start(self, timeout_s: float = 30.0):
        started.append(float(timeout_s))
        self.proc = None
        self.pid = None

    monkeypatch.setattr(mod.ManagedComfyServer, "start", _fake_start)

    recovered = mod.recover_managed_comfy_server(timeout_s=45.0, reason="comfy_server_crashed")
    assert recovered is server
    assert started == [45.0]
