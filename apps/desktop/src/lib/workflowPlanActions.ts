import type { GenerationSettings } from "./tauri-api";
import type { AgentPlanSnapshot, WorkflowReadiness } from "./studioBridge";
import { modelBasename } from "./model-selection";

const INPUT_LABELS: Record<string, string> = {
  prompt: "Prompt",
  scene_prompt: "Scene prompt",
  input_image: "Input image",
  control_image: "Control image",
  mask: "Inpaint mask",
  reference_images: "Reference image(s)",
  text: "Composite text",
  regions_or_layers: "Composition regions",
  model: "Base model",
};

export function labelRequiredInput(name: string): string {
  return INPUT_LABELS[name] ?? name.replace(/_/g, " ");
}

export function resolvePlannedSettings(
  plan: AgentPlanSnapshot,
  base: GenerationSettings,
): GenerationSettings {
  const patch = { ...(plan.proposed ?? {}), ...(plan.applied ?? {}) };
  const merged: GenerationSettings = { ...base, ...patch };
  if (plan.workflow_plan?.length) {
    merged.workflow_plan = plan.workflow_plan as GenerationSettings["workflow_plan"];
    merged.execute_workflow_plan = plan.workflow_plan.length > 1;
  }
  return merged;
}

export function plannedModelLabel(plan: AgentPlanSnapshot): string | null {
  const model =
    plan.applied?.model ??
    plan.proposed?.model ??
    plan.workflow_plan?.find((step) => step.params && typeof step.params.model === "string")
      ?.params?.model;
  if (typeof model !== "string" || !model.trim()) return null;
  return modelBasename(model);
}

export function planBlocksDirectGenerate(
  plan: AgentPlanSnapshot | null,
  approvalRequired: boolean | undefined,
): boolean {
  if (!plan || approvalRequired === false) return false;
  return true;
}

export function canRunApprovedPlan(
  plan: AgentPlanSnapshot | null,
  readiness: WorkflowReadiness | undefined,
): { ok: boolean; reason?: string } {
  if (!plan) return { ok: false, reason: "No plan to run" };
  if (readiness?.ready === false) {
    const missing = [
      ...(readiness.missing_inputs ?? []).map(labelRequiredInput),
      ...(readiness.missing_models ?? []),
      ...(readiness.missing_node_packs ?? []),
    ];
    if (missing.length) {
      return { ok: false, reason: `Resolve: ${missing.slice(0, 3).join(", ")}` };
    }
    return { ok: false, reason: "Plan is not ready yet" };
  }
  return { ok: true };
}

export function requiredInputRows(readiness: WorkflowReadiness | undefined): Array<{
  name: string;
  label: string;
  satisfied: boolean;
}> {
  if (!readiness) return [];
  const missing = new Set(readiness.missing_inputs ?? []);
  const names = [
    ...new Set([
      ...(readiness.missing_inputs ?? []),
      ...(readiness.warnings ?? [])
        .flatMap((w) => w.match(/Missing required workflow input\(s\): ([^.]+)/)?.[1]?.split(", ") ?? []),
    ]),
  ].filter(Boolean);
  if (!names.length && (readiness.missing_inputs?.length ?? 0) > 0) {
    return (readiness.missing_inputs ?? []).map((name) => ({
      name,
      label: labelRequiredInput(name),
      satisfied: false,
    }));
  }
  return names.map((name) => ({
    name,
    label: labelRequiredInput(name),
    satisfied: !missing.has(name),
  }));
}
