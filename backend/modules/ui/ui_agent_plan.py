"""
DreamForge WebUI – Agent Plan panel.

Provides a Gradio Accordion within the main tab that lets the user:
  1. Type a natural-language instruction.
  2. Call DreamForgeEngine.plan() to get a structured JSON plan.
  3. Review the plan.
  4. Click "Approve & Run" to execute the planned workflow.

This mirrors the Desktop app's Agent mode, bringing plan-preview parity
to the Gradio WebUI.
"""
from __future__ import annotations

import json
import traceback

import gradio as gr

from dreamforge_plan_execution import build_execution_params_from_brain_decision


def _request_plan(instruction: str) -> str:
    """Call the engine to get a structured plan for the instruction."""
    if not instruction or not instruction.strip():
        return json.dumps({"status": "error", "message": "Please enter an instruction."}, indent=2)
    try:
        from dreamforge_engine import DreamForgeEngine

        decision = DreamForgeEngine.plan(instruction)
        return json.dumps(decision, indent=2, ensure_ascii=False)
    except Exception as exc:
        traceback.print_exc()
        return json.dumps({"status": "error", "message": str(exc)}, indent=2)


def _approve_and_run(plan_json_str: str) -> str:
    """Execute a previously-approved plan through the engine."""
    if not plan_json_str or not plan_json_str.strip():
        return json.dumps({"status": "error", "message": "No plan to execute."}, indent=2)
    try:
        plan = json.loads(plan_json_str)
    except json.JSONDecodeError as exc:
        return json.dumps({"status": "error", "message": f"Invalid JSON: {exc}"}, indent=2)

    from dreamforge_agent_runtime import AgentRuntime

    try:
        exec_params = build_execution_params_from_brain_decision(plan, approved=True)
        if exec_params.get("status") == "needs_approval":
            return json.dumps(exec_params, indent=2, ensure_ascii=False)

        runtime = AgentRuntime(approval_required=False)
        result = runtime.execute(exec_params, approved=True, tool="approve_and_run")
        return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as exc:
        traceback.print_exc()
        return json.dumps({"status": "error", "message": str(exc)}, indent=2)


def create_agent_plan_accordion() -> gr.Accordion:
    """
    Build and return a Gradio Accordion that can be embedded in the main UI.

    Returns the accordion component.  The caller should place it inside
    the relevant Gradio context (e.g. below the prompt area).
    """
    with gr.Accordion(label="🧠 Agent Plan (preview)", open=False) as accordion:
        gr.Markdown(
            "Type a natural-language instruction and the AI brain will produce a structured plan. "
            "Review the plan, then click **Approve & Run** to execute it."
        )
        agent_instruction = gr.Textbox(
            label="Instruction",
            placeholder="e.g. Edit the last image: make the sky more dramatic and add film grain",
            lines=2,
        )
        plan_btn = gr.Button(value="🔍 Plan", variant="secondary")
        plan_output = gr.Code(
            label="Proposed plan",
            language="json",
            interactive=True,
            lines=12,
        )
        run_btn = gr.Button(value="✅ Approve & Run", variant="primary")
        run_output = gr.Code(
            label="Execution result",
            language="json",
            interactive=False,
            lines=8,
        )

        plan_btn.click(
            fn=_request_plan,
            inputs=[agent_instruction],
            outputs=[plan_output],
        )
        run_btn.click(
            fn=_approve_and_run,
            inputs=[plan_output],
            outputs=[run_output],
        )

    return accordion
