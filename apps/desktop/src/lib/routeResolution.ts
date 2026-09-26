import { isEditFamilyMode, type StudioMode } from "./model-selection";
import type { GenerationSettings } from "./tauri-api";
import { inferReferenceRole } from "./referenceRole";
import { clearLegacyIdentitySettings } from "./identityPreserve";

export type { ReferenceRole } from "./referenceRole";
export {
  inferReferenceRole,
  referenceRoleFromAttach,
  routeBadgeLabel,
} from "./referenceRole";
export type EffectiveTask =
  | "generate"
  | "edit"
  | "inpaint"
  | "upscale"
  | "agent";

export type OutputKind = "gen" | "edit" | "inpaint" | "upscale";

export type EffectiveRoute = {
  task: EffectiveTask;
  sourcePath?: string;
  isGenerateReference: boolean;
  outputKind: OutputKind;
};

/** Generate tab with a reference image should stay on img2img generate, not edit/upscale. */
export function isGenerateReferenceWorkflow(
  settings: GenerationSettings,
): boolean {
  const role = inferReferenceRole(settings, "generate");
  if (role === "restyle" || role === "image_prompt") {
    return Boolean(
      settings.input_image?.trim() ||
        settings.reference_image?.trim() ||
        settings.reference_images?.some((item) => item.trim()),
    );
  }
  const workflowMode = (settings.workflow_mode ?? "").toLowerCase();
  const hasRef = Boolean(
    settings.input_image?.trim() ||
      settings.reference_image?.trim() ||
      settings.reference_images?.some((item) => item.trim()),
  );
  return workflowMode === "generate" && hasRef;
}
export function resolveEffectiveRoute(
  studioMode: StudioMode,
  settings: GenerationSettings,
): EffectiveRoute {
  if (studioMode === "inpaint" || studioMode === "toolbox") {
    return resolveEffectiveRoute("edit", settings);
  }
  if (studioMode === "agent") {
    return {
      task: "agent",
      sourcePath:
        settings.input_image?.trim() ||
        settings.reference_image?.trim() ||
        settings.upscale_image?.trim(),
      isGenerateReference: isGenerateReferenceWorkflow(settings),
      outputKind: "gen",
    };
  }

  if (studioMode === "generate") {
    const role = inferReferenceRole(settings, studioMode);
    const sourcePath =
      settings.input_image?.trim() ||
      settings.reference_image?.trim() ||
      undefined;
    return {
      task: "generate",
      sourcePath,
      isGenerateReference:
        role === "restyle" ||
        role === "image_prompt" ||
        isGenerateReferenceWorkflow(settings) ||
        Boolean(sourcePath),
      outputKind: "gen",
    };
  }
  if (studioMode === "upscale") {
    return {
      task: "upscale",
      sourcePath:
        settings.upscale_image?.trim() || settings.input_image?.trim(),
      isGenerateReference: false,
      outputKind: "upscale",
    };
  }

  return {
    task: "edit",
    sourcePath: settings.input_image?.trim(),
    isGenerateReference: false,
    outputKind:
      settings.edit_type === "inpaint" && settings.inpaint_mask_path?.trim()
        ? "inpaint"
        : "edit",
  };
}

/** Strip stale routing fields so studio_mode stays authoritative. */
export function sanitizeSettingsForStudioMode(
  studioMode: StudioMode,
  settings: GenerationSettings,
): GenerationSettings {
  if (studioMode === "inpaint" || studioMode === "toolbox") {
    return sanitizeSettingsForStudioMode("edit", settings);
  }
  const next = { ...clearLegacyIdentitySettings(settings, studioMode) };
  next.custom_tool_id = undefined;

  if (isEditFamilyMode(studioMode)) {
    if (studioMode === "upscale") {
      next.input_image = undefined;
      next.inpaint_mask_path = undefined;
      return next;
    }
    next.upscale_image = undefined;
    next.upscale_method = undefined;
    next.workflow_mode = "edit";
    next.reference_role = next.inpaint_mask_path?.trim() ? "inpaint" : "source_edit";
    if (next.inpaint_mask_path?.trim()) {
      next.edit_type = "inpaint";
      next.cn_selection = "Custom...";
      next.cn_type = "inpaint";
    }
    return next;
  }

  if (studioMode !== "generate" && studioMode !== "agent") {
    return next;
  }

  next.upscale_image = undefined;
  next.upscale_method = undefined;
  next.inpaint_mask_path = undefined;
  // Edit/inpaint task presets and outpaint controls must not leak into text-to-image.
  next.edit_task = undefined;
  next.inpaint_intent = undefined;
  next.inpaint_additional_prompt = undefined;
  next.inpaint_hard_mask = undefined;
  next.outpaint_direction = undefined;
  next.outpaint_amount = undefined;
  next.outpaint_feathering = undefined;
  const editType = (next.edit_type ?? "").toLowerCase();
  if (editType === "outpaint" || editType === "inpaint") {
    next.edit_type = "auto";
  }
  if ((next.cn_type ?? "").toLowerCase() === "outpaint") {
    next.cn_type = "None";
    next.cn_selection = "None";
  }

  const hasRef = Boolean(
    next.input_image?.trim() ||
      next.reference_image?.trim() ||
      next.reference_images?.some((item) => item.trim()),
  );

  if (!hasRef) {
    next.reference_role = undefined;
    return next;
  }

  if (hasRef) {
    if (next.reference_role === "image_prompt") {
      next.workflow_mode = next.workflow_mode ?? "ipadapter";
    } else {
      next.workflow_mode = next.workflow_mode ?? "generate";
    }
    next.reference_role =
      next.reference_role ??
      inferReferenceRole(next, studioMode) ??
      "restyle";
    if (next.edit_type === "inpaint") {
      next.edit_type = "auto";
    }
    if ((next.cn_type ?? "").toLowerCase() === "upscale") {
      next.cn_type = "img2img";
      next.cn_selection = "Custom...";
    }
    if (next.style === "image_edit") {
      next.style = "none";
    }
  }

  return next;
}
