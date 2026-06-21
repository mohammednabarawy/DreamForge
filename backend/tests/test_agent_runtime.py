from dreamforge_agent_runtime import AgentRuntime
from dreamforge_brain import heuristic_brain_decision
from dreamforge_plan_execution import build_execution_params_from_brain_decision
from dreamforge_user_style_profile import (
    apply_planning_hints,
    clear_profile,
    load_profile,
    record_successful_job,
    save_profile,
)


def test_build_execution_params_merges_patch_and_workflow_plan():
    decision = heuristic_brain_decision(
        "Make her smile, remove background people, upscale to 4K",
        current_settings={"model": "flux1-schnell-fp8.safetensors"},
        selected_image="D:/tmp/photo.png",
        gallery=[],
    )
    params = build_execution_params_from_brain_decision(
        decision,
        current_settings={"seed": 42, "model": "flux1-schnell-fp8.safetensors"},
        approved=True,
    )

    assert params["execute_workflow_plan"] is True
    assert isinstance(params["workflow_plan"], list)
    assert params["model"] == "flux1-schnell-fp8.safetensors"
    assert params["seed"] == 42
    assert params["use_comfy_server"] is True
    assert params["input_image"] == "D:/tmp/photo.png"


def test_build_execution_params_requires_approval_when_flagged():
    decision = {
        "requires_approval": True,
        "patch": {"prompt": "remove the logo"},
        "workflow_plan": [],
    }
    payload = build_execution_params_from_brain_decision(decision, approved=False)

    assert payload["status"] == "needs_approval"
    assert payload["code"] == "plan_execution_requires_approval"


def test_agent_runtime_blocks_execution_without_approval(monkeypatch):
    called = {"count": 0}

    def fake_execute(_params):
        called["count"] += 1
        return {"status": "success"}

    import dreamforge_agent_runtime as runtime_module

    monkeypatch.setattr(runtime_module.DreamForgeEngine, "execute_job", fake_execute)

    runtime = AgentRuntime(capabilities={"execute"}, approval_required=True)
    payload = runtime.generate("local portrait")

    assert payload["status"] == "needs_approval"
    assert called["count"] == 0


def test_agent_runtime_executes_when_approved(monkeypatch):
    captured = {}

    def fake_execute(params):
        captured["params"] = params
        return {"status": "success"}

    import dreamforge_agent_runtime as runtime_module

    monkeypatch.setattr(runtime_module.DreamForgeEngine, "execute_job", fake_execute)

    runtime = AgentRuntime(capabilities={"execute"}, approval_required=True)
    payload = runtime.generate("local portrait", approved=True)

    assert payload["status"] == "success"
    assert captured["params"]["prompt"] == "local portrait"


def test_agent_runtime_execute_brain_decision(monkeypatch):
    decision = heuristic_brain_decision(
        "repair face details and sharpen the eyes",
        current_settings={"input_image": "D:/tmp/portrait.png"},
        selected_image="D:/tmp/portrait.png",
        gallery=[],
    )
    captured = {}

    def fake_execute(params):
        captured["params"] = params
        return {"status": "success"}

    import dreamforge_agent_runtime as runtime_module

    monkeypatch.setattr(runtime_module.DreamForgeEngine, "execute_job", fake_execute)

    runtime = AgentRuntime(capabilities={"execute"}, approval_required=False)
    payload = runtime.execute_brain_decision(decision, approved=True)

    assert payload["status"] == "success"
    assert captured["params"]["workflow_mode"] == "face_detail"


def test_user_style_profile_records_and_applies_hints(tmp_path, monkeypatch):
    import dreamforge_user_style_profile as profile_module

    profile_path = tmp_path / "profile.json"
    monkeypatch.setattr(profile_module, "PROFILE_PATH", profile_path)

    record_successful_job(
        {
            "model": "flux1-schnell-fp8.safetensors",
            "styles": ["Style: sai-cinematic"],
            "aspect_ratio": "1024x1024",
            "workflow_mode": "hires",
        },
        {"status": "success"},
    )

    profile = load_profile()
    assert profile.generation_count == 1
    assert "flux1-schnell-fp8.safetensors" in profile.favorite_models

    hints = apply_planning_hints({})
    assert hints["model"] == "flux1-schnell-fp8.safetensors"
    assert hints["aspect_ratio"] == "1024x1024"

    save_profile(clear_profile())
    assert load_profile().generation_count == 0
