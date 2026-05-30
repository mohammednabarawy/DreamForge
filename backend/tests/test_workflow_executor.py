from types import SimpleNamespace
from unittest.mock import patch

from dreamforge_workflow_executor import (
    execute_workflow_plan,
    patch_for_step,
    should_execute_workflow_plan,
)


def test_should_execute_workflow_plan_requires_flag_and_steps():
    job = SimpleNamespace(
        workflow_plan=[
            {"operation": "generate_image", "mode": "generate"},
            {"operation": "face_detail", "mode": "edit"},
        ],
        execute_workflow_plan=True,
    )
    assert should_execute_workflow_plan(job, None) is True


def test_should_not_execute_when_already_in_step():
    job = SimpleNamespace(
        workflow_plan=[{"operation": "a"}, {"operation": "b"}],
        execute_workflow_plan=True,
        _executing_plan_step=True,
    )
    assert should_execute_workflow_plan(job, None) is False


def test_patch_for_step_maps_face_detail():
    patch = patch_for_step(
        {"operation": "face_detail", "params": {}},
        prior_paths=["/tmp/prev.png"],
    )
    assert patch["workflow_mode"] == "face_detail"
    assert patch["input_image"] == "/tmp/prev.png"
    assert patch["_executing_plan_step"] is True


@patch("dreamforge_generation.run_generation")
def test_execute_workflow_plan_chains_steps(mock_run):
    mock_run.side_effect = [
        {"status": "success", "images": [{"path": "/tmp/scene.png"}]},
        {"status": "success", "images": [{"path": "/tmp/final.png"}]},
    ]
    job = SimpleNamespace(
        workflow_plan=[
            {"operation": "generate_image", "mode": "generate"},
            {"operation": "face_detail", "mode": "edit"},
        ],
        execute_workflow_plan=True,
    )
    result = execute_workflow_plan(
        base_args=SimpleNamespace(),
        data={"execute_workflow_plan": True, "workflow_plan": job.workflow_plan},
        job=job,
    )
    assert result["status"] == "success"
    assert result["output_paths"] == ["/tmp/final.png"]
    assert mock_run.call_count == 2
    second_data = mock_run.call_args_list[1].args[1]
    assert second_data["workflow_mode"] == "face_detail"
    assert second_data["input_image"] == "/tmp/scene.png"
