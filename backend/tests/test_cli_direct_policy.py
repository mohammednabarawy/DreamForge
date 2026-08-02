from types import SimpleNamespace


def test_direct_cli_initializes_runtime_policy_before_boot(monkeypatch):
    import dreamforge_comfy_launch
    import dreamforge_comfy_server
    import dreamforge_engine
    import dreamforge_vram_profiles
    from dreamforge_cli_direct import process_single

    calls = []
    monkeypatch.setattr(dreamforge_vram_profiles, "apply_desktop_vram_env", lambda profile: calls.append(("vram", profile)) or "8gb")
    monkeypatch.setattr(dreamforge_comfy_launch, "apply_runtime_optimization_env", lambda: calls.append(("runtime",)) or {})
    monkeypatch.setattr(dreamforge_comfy_server, "boot_managed_comfy_server", lambda: calls.append(("boot",)))
    monkeypatch.setattr(dreamforge_engine.DreamForgeEngine, "execute_job", staticmethod(lambda params, stream_sink=None: {"status": "success", "params": params}))

    result = process_single(SimpleNamespace(vram_profile="auto", style_reference=None), {"prompt": "smoke"})
    assert result["status"] == "success"
    assert [call[0] for call in calls] == ["vram", "runtime", "boot"]


def test_direct_cli_main_does_not_boot_before_process_single(monkeypatch):
    import dreamforge_cli_direct as cli

    cli_args = SimpleNamespace(
        subcommand=None, hires=False, reference_mode="", workflow_mode=None,
        json=False, list_models=False, list_fonts=False, list_inventory=False,
        list_styles=False, recommend_models=False, check_model_deps=None,
        classify_models=False, organize=False, organize_apply=False,
        brain_plan=False, dry_run=False, batch=None,
    )
    main_globals = cli.main.__globals__
    monkeypatch.setitem(main_globals, "parse_cli", lambda: main_globals.__setitem__("args", cli_args))
    monkeypatch.setitem(main_globals, "handle_inventory_arguments", lambda _args: False)
    calls = []
    monkeypatch.setitem(main_globals, "process_single", lambda _args, data=None: calls.append("process") or {"status": "success", "images": []})

    cli.main()
    assert calls == ["process"]
