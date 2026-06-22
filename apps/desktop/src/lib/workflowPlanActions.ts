import type { GenerationSettings } from "./tauri-api";
import type { AgentPlanSnapshot, WorkflowReadiness } from "./studioBridge";
import {
  isEditFamilyMode,
  modelBasename,
  type StudioMode,
} from "./model-selection";

export type EditFamilyPlanState = "none" | "stale" | "not_ready" | "ready";

export function computePlanSettingsSnapshot(
  settings: GenerationSettings,
  studioMode: StudioMode,
): string {
  const payload = {
    studioMode,
    prompt: (settings.prompt ?? "").trim(),
    negative_prompt: (settings.negative_prompt ?? "").trim(),
    input_image: (settings.input_image ?? "").trim(),
    upscale_image: (settings.upscale_image ?? "").trim(),
    inpaint_mask_path: (settings.inpaint_mask_path ?? "").trim(),
    edit_type: settings.edit_type,
    edit_strength: settings.edit_strength,
    model: (settings.model ?? "").trim(),
    identity_mode: settings.identity_mode,
    face_preservation: settings.face_preservation,
    inpaint_grow: settings.inpaint_grow,
    inpaint_feather: settings.inpaint_feather,
    inpaint_mask_grow_by: settings.inpaint_mask_grow_by,
    preserve_character: settings.preserve_character,
    preserve_style: settings.preserve_style,
    preserve_text: settings.preserve_text,
    upscale_method: settings.upscale_method,
    reference_images: settings.reference_images,
  };
  return JSON.stringify(payload);
}

export function editFamilyPlanState(
  plan: AgentPlanSnapshot | null,
  studioMode: StudioMode | undefined,
  settingsSnapshot: string,
): EditFamilyPlanState {
  if (!isEditFamilyMode(studioMode)) return "none";
  if (!plan) return "none";
  if (plan.settings_snapshot !== settingsSnapshot) return "stale";
  if (plan.readiness?.ready === false) return "not_ready";
  return "ready";
}

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

export function labelRequiredInput(name: string | unknown): string {
  const key = typeof name === "string" ? name : String(name ?? "");
  return INPUT_LABELS[key] ?? key.replace(/_/g, " ");
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

export function stripUndefinedPatch(
  patch: Partial<GenerationSettings>,
): Partial<GenerationSettings> {
  const out: Partial<GenerationSettings> = {};
  for (const [key, value] of Object.entries(patch)) {
    if (value !== "") {
      (out as Record<string, unknown>)[key] = value;
    }
  }
  return out;
}

export function proposedPatchFromDryRunPlan(
  planPayload: Record<string, unknown>,
  baseSettings: GenerationSettings,
): Partial<GenerationSettings> {
  const raw = planPayload.proposed_patch ?? planPayload.proposed;
  if (raw && typeof raw === "object" && !Array.isArray(raw)) {
    return stripUndefinedPatch({
      ...baseSettings,
      ...(raw as Partial<GenerationSettings>),
    });
  }

  const modelField = planPayload.model;
  let model: string | undefined;
  if (typeof modelField === "string") {
    model = modelField;
  } else if (modelField && typeof modelField === "object") {
    const record = modelField as Record<string, unknown>;
    model = String(record.engine_name ?? record.name ?? "").trim() || undefined;
  }

  const settingsBlock =
    typeof planPayload.settings === "object" && planPayload.settings
      ? (planPayload.settings as Record<string, unknown>)
      : undefined;

  return stripUndefinedPatch({
    ...baseSettings,
    model: model ?? baseSettings.model,
    negative_prompt:
      typeof planPayload.negative_prompt === "string"
        ? planPayload.negative_prompt
        : baseSettings.negative_prompt,
    steps:
      typeof settingsBlock?.steps === "number"
        ? settingsBlock.steps
        : baseSettings.steps,
    cfg_scale:
      typeof settingsBlock?.cfg === "number"
        ? settingsBlock.cfg
        : baseSettings.cfg_scale,
    sampler:
      typeof settingsBlock?.sampler === "string"
        ? settingsBlock.sampler
        : baseSettings.sampler,
    scheduler:
      typeof settingsBlock?.scheduler === "string"
        ? settingsBlock.scheduler
        : baseSettings.scheduler,
  });
}

export function buildPlanSnapshotFromDryRun(args: {
  planPayload: Record<string, unknown>;
  workflowBlueprint: Record<string, unknown>;
  baseSettings: GenerationSettings;
  studioMode: StudioMode;
  readiness?: WorkflowReadiness;
  message?: string;
}): AgentPlanSnapshot {
  const proposed = proposedPatchFromDryRunPlan(args.planPayload, args.baseSettings);
  const mergedForSnapshot: GenerationSettings = { ...args.baseSettings, ...proposed };
  const mode =
    typeof args.planPayload.mode === "string"
      ? (args.planPayload.mode as StudioMode)
      : args.studioMode;

  return {
    source: "dry-run",
    message: args.message ?? "Dry-run plan",
    escalation_reason:
      typeof args.planPayload.escalation_reason === "string"
        ? args.planPayload.escalation_reason
        : undefined,
    mode,
    settings_snapshot: computePlanSettingsSnapshot(mergedForSnapshot, args.studioMode),
    proposed,
    operations: Array.isArray(args.planPayload.operations)
      ? args.planPayload.operations.map((item) => String(item))
      : undefined,
    readiness: args.readiness,
    mode_contract:
      typeof args.planPayload.mode_contract === "object" && args.planPayload.mode_contract
        ? (args.planPayload.mode_contract as AgentPlanSnapshot["mode_contract"])
        : undefined,
    workflow_blueprint: args.workflowBlueprint,
    workflow_plan: Array.isArray(args.planPayload.workflow_plan)
      ? (args.planPayload.workflow_plan as AgentPlanSnapshot["workflow_plan"])
      : undefined,
  };
}

export function planBlockedByLocalInputsOnly(
  readiness: WorkflowReadiness | undefined,
): boolean {
  const missing = safeStringList(readiness?.missing_inputs);
  if (!missing.length) return false;
  const local = new Set([
    "mask",
    "input_image",
    "prompt",
    "control_image",
    "reference_images",
    "upscale_image",
    "scene_prompt",
  ]);
  return missing.every((name) => local.has(name));
}

/** Inputs required only by optional add-on templates (poster/text/compositing). */
const OPTIONAL_PLAN_INPUTS = new Set([
  "text",
  "scene_prompt",
  "regions_or_layers",
  "direction_or_canvas_size",
  "target_size",
]);

export function planHasHardBlockers(
  readiness: WorkflowReadiness | undefined,
): boolean {
  if (!readiness) return false;
  if (safeStringList(readiness.missing_models).length) return true;
  if (safeStringList(readiness.missing_node_packs).length) return true;
  const missingInputs = safeStringList(readiness.missing_inputs);
  return missingInputs.some((name) => !OPTIONAL_PLAN_INPUTS.has(name));
}

/** Show the canvas plan card only when review or asset setup is actually needed. */
export function shouldSurfaceWorkflowPlan(plan: AgentPlanSnapshot | null): boolean {
  if (!plan) return false;
  const readiness = plan.readiness;
  if (!readiness) return false;
  if (planHasHardBlockers(readiness)) return true;
  if (readiness.ready === false && safeStringList(readiness.missing_inputs).length > 0) {
    return planHasHardBlockers(readiness);
  }
  if (safeStringList(readiness.recommended_actions).length > 0) return true;
  return false;
}

export function planBlocksDirectGenerate(
  _plan: AgentPlanSnapshot | null,
  _approvalRequired?: boolean,
  _options?: {
    studioMode?: StudioMode;
    settingsSnapshot?: string;
  },
): boolean {
  return false;
}

export function canRunApprovedPlan(
  plan: AgentPlanSnapshot | null,
  readiness: WorkflowReadiness | undefined,
): { ok: boolean; reason?: string } {
  if (!plan) return { ok: false, reason: "No plan to run" };
  if (readiness?.ready === false) {
    const missing = [
      ...safeStringList(readiness.missing_inputs).map(labelRequiredInput),
      ...safeStringList(readiness.missing_models),
      ...safeStringList(readiness.missing_node_packs),
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
  const missingInputs = safeStringList(readiness.missing_inputs);
  const missing = new Set(missingInputs);
  const names = [
    ...new Set([
      ...missingInputs,
      ...safeStringList(readiness.warnings).flatMap(
        (w) => w.match(/Missing required workflow input\(s\): ([^.]+)/)?.[1]?.split(", ") ?? [],
      ),
    ]),
  ].filter(Boolean);
  if (!names.length && missingInputs.length > 0) {
    return missingInputs.map((name) => ({
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

function safeStringList(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => String(item ?? "")).filter(Boolean) : [];
}
