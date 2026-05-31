"""Safe local AgentRuntime for planning and approved GPU execution."""

from __future__ import annotations

import os
from typing import Any

from dreamforge_engine import DreamForgeEngine
from dreamforge_plan_execution import build_execution_params_from_brain_decision

DEFAULT_AGENT_CAPABILITIES = frozenset({"read", "plan", "execute"})


def agent_capabilities_from_env() -> set[str]:
    raw = os.environ.get("DREAMFORGE_AGENT_CAPABILITIES", "")
    if not raw:
        return set(DEFAULT_AGENT_CAPABILITIES)
    return {item.strip().lower() for item in raw.split(",") if item.strip()}


class AgentRuntime:
    """
    Capability-gated runtime for external agents.

    Exposes task-level tools over DreamForgeEngine without arbitrary shell or
    filesystem access.
    """

    def __init__(
        self,
        *,
        capabilities: set[str] | None = None,
        approval_required: bool = True,
    ) -> None:
        self.capabilities = set(capabilities or agent_capabilities_from_env())
        self.approval_required = approval_required

    def describe(self) -> dict[str, Any]:
        return {
            "status": "success",
            "local_only_image_backend": True,
            "capabilities": sorted(self.capabilities),
            "execution_requires_approval": self.approval_required,
            "arbitrary_shell": False,
            "arbitrary_filesystem": False,
            "tools": [
                "get_agent_catalog",
                "plan",
                "execute",
                "generate",
                "edit",
                "inpaint",
                "upscale",
                "list_models",
                "list_styles",
                "list_loras",
                "list_outputs",
                "analyze_project",
            ],
        }

    def _capability_error(self, capability: str, tool: str) -> dict[str, Any]:
        return {
            "status": "error",
            "code": "agent_capability_denied",
            "message": f"Tool '{tool}' requires the '{capability}' capability.",
            "capabilities": sorted(self.capabilities),
        }

    def _approval_required(self, tool: str) -> dict[str, Any]:
        return {
            "status": "needs_approval",
            "code": "agent_execution_requires_approval",
            "message": f"Approve this local DreamForge job, then call '{tool}' again with approved=true.",
            "local_only_image_backend": True,
        }

    def _require_capability(self, capability: str, tool: str) -> dict[str, Any] | None:
        if capability in self.capabilities:
            return None
        return self._capability_error(capability, tool)

    def _require_execution(self, tool: str, *, approved: bool) -> dict[str, Any] | None:
        blocked = self._require_capability("execute", tool)
        if blocked:
            return blocked
        if self.approval_required and not approved:
            return self._approval_required(tool)
        return None

    def plan(self, instruction: str, **kwargs: Any) -> dict[str, Any]:
        blocked = self._require_capability("plan", "plan")
        if blocked:
            return blocked
        return DreamForgeEngine.plan(instruction, **kwargs)

    def execute(
        self,
        params: dict[str, Any],
        *,
        approved: bool = False,
        tool: str = "execute",
    ) -> dict[str, Any]:
        blocked = self._require_execution(tool, approved=approved)
        if blocked:
            return blocked
        return DreamForgeEngine.execute_job(dict(params))

    def execute_brain_decision(
        self,
        decision: dict[str, Any],
        *,
        current_settings: dict[str, Any] | None = None,
        approved: bool = False,
        tool: str = "execute",
    ) -> dict[str, Any]:
        blocked = self._require_execution(tool, approved=approved)
        if blocked:
            return blocked
        params = build_execution_params_from_brain_decision(
            decision,
            current_settings=current_settings,
            approved=True,
        )
        if params.get("status") == "needs_approval":
            return params
        return DreamForgeEngine.execute_job(params)

    def generate(self, prompt: str, *, approved: bool = False, **kwargs: Any) -> dict[str, Any]:
        blocked = self._require_execution("generate", approved=approved)
        if blocked:
            return blocked
        return DreamForgeEngine.generate(prompt, **kwargs)

    def edit(
        self,
        input_image: str,
        prompt: str,
        *,
        approved: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        blocked = self._require_execution("edit", approved=approved)
        if blocked:
            return blocked
        return DreamForgeEngine.edit(input_image, prompt, **kwargs)

    def inpaint(
        self,
        input_image: str,
        mask_image: str,
        prompt: str,
        *,
        approved: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        blocked = self._require_execution("inpaint", approved=approved)
        if blocked:
            return blocked
        return DreamForgeEngine.inpaint(input_image, mask_image, prompt, **kwargs)

    def upscale(self, image_path: str, *, approved: bool = False, **kwargs: Any) -> dict[str, Any]:
        blocked = self._require_execution("upscale", approved=approved)
        if blocked:
            return blocked
        return DreamForgeEngine.upscale(image_path, **kwargs)

    def list_models(self) -> dict[str, Any]:
        blocked = self._require_capability("read", "list_models")
        if blocked:
            return blocked
        return DreamForgeEngine.list_models()

    def list_outputs(self, **kwargs: Any) -> dict[str, Any]:
        blocked = self._require_capability("read", "list_outputs")
        if blocked:
            return blocked
        return DreamForgeEngine.list_outputs(**kwargs)

    def analyze_project(self) -> dict[str, Any]:
        blocked = self._require_capability("read", "analyze_project")
        if blocked:
            return blocked
        return DreamForgeEngine.analyze_project()
