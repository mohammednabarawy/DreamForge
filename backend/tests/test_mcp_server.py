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


def test_mcp_plan_capability_can_be_disabled(monkeypatch):
    import dreamforge_mcp_server as mcp_server

    monkeypatch.setenv("DREAMFORGE_MCP_CAPABILITIES", "read,execute")

    payload = json.loads(mcp_server.plan_workflow("cinematic portrait"))

    assert payload["status"] == "error"
    assert payload["code"] == "mcp_capability_denied"


def test_mcp_read_capability_can_be_disabled(monkeypatch):
    import dreamforge_mcp_server as mcp_server

    monkeypatch.setenv("DREAMFORGE_MCP_CAPABILITIES", "plan,execute")

    payload = json.loads(mcp_server.list_models())

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


def test_mcp_get_agent_catalog_includes_styles_and_loras():
    import dreamforge_mcp_server as mcp_server

    payload = json.loads(mcp_server.get_agent_catalog(style_limit=5, lora_limit=5))

    assert payload["status"] == "success"
    assert payload["generation_parameters"]["style"]["example"] == "product_ad"
    assert "product_ad" in payload["generation_parameters"]["style"]["values"]
    assert payload["style_recipes"]["sample"]
    assert "lora" in payload["generation_parameters"]
    assert "list_styles" in payload["mcp_tools"]["discover"]


def test_mcp_list_styles_returns_recipe_metadata():
    import dreamforge_mcp_server as mcp_server

    payload = json.loads(mcp_server.list_styles(limit=3))

    assert payload["status"] == "success"
    assert payload["parameter"] == "style"
    assert len(payload["styles"]) <= 3
    first = payload["styles"][0]
    assert "id" in first
    assert "label" in first


def test_mcp_list_loras_reports_usage_format():
    import dreamforge_mcp_server as mcp_server

    payload = json.loads(mcp_server.list_loras(limit=1))

    assert payload["status"] == "success"
    assert payload["format"] == "filename.safetensors:weight"
    if payload["loras"]:
        assert "usage" in payload["loras"][0]


def test_mcp_generate_passes_lora_stack(monkeypatch):
    import dreamforge_mcp_server as mcp_server

    captured = {}

    def fake_execute(params):
        captured["params"] = params
        return {"status": "success"}

    monkeypatch.setattr(mcp_server.DreamForgeEngine, "execute_job", fake_execute)

    payload = json.loads(
        mcp_server.generate_image(
            "studio product",
            style="product_ad",
            lora=["detail_tweaker_xl.safetensors:0.5"],
            approved=True,
        )
    )

    assert payload["status"] == "success"
    assert captured["params"]["lora"] == ["detail_tweaker_xl.safetensors:0.5"]
    assert captured["params"]["style"] == "product_ad"


def test_mcp_recommend_for_style_marks_recipe_models(monkeypatch):
    import dreamforge_mcp_server as mcp_server

    monkeypatch.setattr(
        mcp_server,
        "resolve_generation_model",
        lambda query: {"name": query, "family": "sdxl"} if "RealVis" in query else None,
    )

    payload = json.loads(mcp_server.recommend_for_style(style="product_ad", limit=3))

    assert payload["status"] == "success"
    assert payload["style"] == "product_ad"
    assert payload["recipe_models"]
    assert any(item["requested"] for item in payload["recipe_models"])
