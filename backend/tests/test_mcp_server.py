import json


def test_mcp_generate_requires_explicit_approval(monkeypatch):
    import dreamforge_mcp_server as mcp_server

    called = {"count": 0}
    monkeypatch.setattr(
        mcp_server.DreamForgeEngine,
        "execute_job",
        lambda _params: called.__setitem__("count", called["count"] + 1) or {"status": "success"},
    )

    payload = json.loads(mcp_server.generate_image("local portrait"))

    assert payload["status"] == "needs_approval"
    assert payload["code"] == "mcp_execution_requires_approval"
    assert called["count"] == 0


def test_mcp_generate_approved_uses_engine_queue(monkeypatch):
    import dreamforge_mcp_server as mcp_server

    captured = {}
    def fake_execute(params):
        captured["params"] = params
        return {"status": "success"}

    monkeypatch.setattr(
        mcp_server.DreamForgeEngine,
        "execute_job",
        fake_execute,
    )

    payload = json.loads(mcp_server.generate_image("local portrait", approved=True))

    assert payload["status"] == "success"
    assert captured["params"]["prompt"] == "local portrait"


def test_mcp_execute_capability_can_be_disabled(monkeypatch):
    import dreamforge_mcp_server as mcp_server

    monkeypatch.setenv("DREAMFORGE_MCP_CAPABILITIES", "read,plan")

    payload = json.loads(mcp_server.generate_image("local portrait", approved=True))

    assert payload["status"] == "error"
    assert payload["code"] == "mcp_capability_denied"


def test_mcp_capabilities_report_no_arbitrary_shell_or_filesystem():
    import dreamforge_mcp_server as mcp_server

    payload = json.loads(mcp_server.get_mcp_capabilities())

    assert payload["arbitrary_shell"] is False
    assert payload["arbitrary_filesystem"] is False
    assert payload["execution_requires_approval"] is True


def test_mcp_create_workflow_returns_blueprint_not_raw_graph():
    import dreamforge_mcp_server as mcp_server

    payload = json.loads(
        mcp_server.create_workflow(
            "composite a product poster",
            mode="area_composition",
            settings={"region_prompts": ["0,0,512,512:left", "512,0,512,512:right"]},
        )
    )

    assert payload["status"] == "success"
    assert "workflow_blueprint" in payload
    assert "workflow_graph" not in payload
    assert "area_composition" in payload["workflow_blueprint"]["template_ids"]


def test_mcp_sessions_resource_is_structured(monkeypatch):
    import dreamforge_mcp_server as mcp_server

    monkeypatch.setattr(
        mcp_server.DreamForgeEngine,
        "list_outputs",
        lambda limit=500, **_kwargs: {
            "projects": [
                {"session": "alpha"},
                {"session": "alpha"},
                {"session": "beta"},
            ],
            "total": 3,
        },
    )

    payload = json.loads(mcp_server.list_sessions_resource())

    assert payload["status"] == "success"
    assert payload["sessions"] == [
        {"id": "alpha", "output_count": 2},
        {"id": "beta", "output_count": 1},
    ]
