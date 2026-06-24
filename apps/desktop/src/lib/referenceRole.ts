import type { StudioMode } from "./model-selection";
import type { GenerationSettings } from "./tauri-api";
import type { ReferenceImageMode } from "./referenceImage";

export type ReferenceRole =
  | "image_prompt"
  | "restyle"
  | "source_edit"
  | "inpaint"
  | "upscale"
  | "structure";

const VALID_ROLES = new Set<ReferenceRole>([
  "image_prompt",
  "restyle",
  "source_edit",
  "inpaint",
  "upscale",
  "structure",
]);

export function isReferenceRole(value: string | undefined | null): value is ReferenceRole {
  return Boolean(value && VALID_ROLES.has(value as ReferenceRole));
}

/** Map UI attach mode + studio tab to an explicit image role. */
export function referenceRoleFromAttach(
  mode: ReferenceImageMode,
  studioMode: StudioMode,
): ReferenceRole {
  if (mode === "upscale") return "upscale";
  if (mode === "inpaint") return "inpaint";
  if (studioMode === "generate" || studioMode === "agent") return "restyle";
  return "source_edit";
}

/** Infer role from legacy image fields when reference_role is absent. */
export function inferReferenceRole(
  settings: GenerationSettings,
  studioMode: StudioMode = "generate",
): ReferenceRole | undefined {
  const explicit = (settings.reference_role ?? "").trim().toLowerCase();
  if (isReferenceRole(explicit)) return explicit;

  const workflowMode = (settings.workflow_mode ?? "").toLowerCase();
  const editType = (settings.edit_type ?? "").toLowerCase();
  const cnType = (settings.cn_type ?? "").toLowerCase();
  const hasInput = Boolean(settings.input_image?.trim());
  const hasRef = Boolean(
    settings.reference_image?.trim() ||
      settings.reference_images?.some((item) => item.trim()),
  );
  const hasUpscale = Boolean(settings.upscale_image?.trim());
  const hasMask = Boolean(settings.inpaint_mask_path?.trim());

  if (studioMode === "upscale" || (hasUpscale && !hasInput)) {
    return hasUpscale || hasInput ? "upscale" : undefined;
  }
  if (
    studioMode === "inpaint" ||
    hasMask ||
    editType === "inpaint" ||
    cnType === "inpaint"
  ) {
    if (workflowMode === "generate") {
      return hasInput || hasRef ? "restyle" : undefined;
    }
    return hasInput || hasMask ? "inpaint" : undefined;
  }
  if (
    workflowMode === "ipadapter" ||
    workflowMode === "reference" ||
    workflowMode === "reference_ipadapter"
  ) {
    return hasRef || hasInput ? "image_prompt" : undefined;
  }
  if (workflowMode === "generate" && (hasInput || hasRef)) {
    return "restyle";
  }
  if (studioMode === "generate" || studioMode === "agent") {
    return hasInput || hasRef ? "restyle" : undefined;
  }
  if (hasInput || hasRef) {
    return "source_edit";
  }
  return undefined;
}

/** Human-readable route label for the active image role. */
export function routeBadgeLabel(
  settings: GenerationSettings,
  studioMode: StudioMode,
  modelFamily?: string,
): string | null {
  const role = inferReferenceRole(settings, studioMode);
  if (!role) return null;

  const family = (modelFamily ?? "").toLowerCase();
  switch (role) {
    case "image_prompt":
      return "Creating with image prompt";
    case "restyle":
      return "Restyling source image";
    case "source_edit":
      if (family.includes("kontext")) return "Editing with Flux Kontext";
      if (family === "qwen_image_edit") return "Editing with Qwen Edit";
      return "Editing source image";
    case "inpaint":
      return "Inpainting region";
    case "upscale":
      return "Upscaling target image";
    case "structure":
      return "Structure guidance";
    default:
      return null;
  }
}

export const PRO_GENERATE_REFERENCE_ROLES: Array<{
  id: Extract<ReferenceRole, "image_prompt" | "restyle" | "structure">;
  label: string;
  short: string;
}> = [
  { id: "image_prompt", label: "Image prompt", short: "Prompt" },
  { id: "restyle", label: "Restyle / img2img", short: "Restyle" },
  { id: "structure", label: "Structure / ControlNet", short: "Structure" },
];

export function proReferenceRolesForStudio(
  studioMode: StudioMode,
): Array<{ id: ReferenceRole; label: string; short: string }> {
  if (studioMode === "generate" || studioMode === "agent") {
    return PRO_GENERATE_REFERENCE_ROLES;
  }
  if (studioMode === "edit") {
    return [{ id: "source_edit", label: "Edit model", short: "Edit" }];
  }
  return [];
}
