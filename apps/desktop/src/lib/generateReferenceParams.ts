import type { StudioMode } from "./model-selection";
import type { GenerationSettings } from "./tauri-api";
import { ipAdapterAssetsReady } from "./easyModeRouting";
import type { ModelDependencyItem } from "./tauri-api";
import { defaultReferenceEditStrength } from "./referenceImage";
import { inferReferenceRole } from "./referenceRole";

export type ReferenceRoleApplyResult = {
  params: GenerationSettings;
  warning?: string;
};

export const IMAGE_PROMPT_FALLBACK_WARNING =
  "IP-Adapter assets missing — using restyle (img2img) instead";

/** Models that use native reference conditioning instead of IP-Adapter (Generate). */
export function modelUsesNativeImagePrompt(modelFamily: string): boolean {
  const fam = modelFamily.toLowerCase();
  return fam === "hidream_o1";
}

/** Apply explicit reference_role routing at submit time (Pro overrides win). */
export function applyExplicitReferenceRoleParams(
  params: GenerationSettings,
  studioMode: StudioMode,
  modelFamily: string,
  options: {
    ipAdapterReady?: boolean;
    modelMissing?: ModelDependencyItem[];
    studioMissing?: ModelDependencyItem[];
    imagePromptMissing?: ModelDependencyItem[];
  } = {},
): ReferenceRoleApplyResult {
  const ipReady =
    options.ipAdapterReady ??
    ipAdapterAssetsReady(
      options.modelMissing,
      options.studioMissing,
      options.imagePromptMissing,
    );

  if (studioMode !== "generate" && studioMode !== "agent") {
    return {
      params: applyEditFamilyReferenceRoleParams(params, studioMode, modelFamily),
    };
  }

  const role = inferReferenceRole(params, studioMode);
  const refPath =
    params.input_image?.trim() || params.reference_image?.trim() || "";
  if (!refPath && role !== "image_prompt") {
    return { params };
  }

  if (role === "image_prompt") {
    if (!ipReady && !modelUsesNativeImagePrompt(modelFamily)) {
      return {
        params: buildRestyleSubmitParams(params, modelFamily, refPath),
        warning: IMAGE_PROMPT_FALLBACK_WARNING,
      };
    }
    const referencePath = params.reference_image?.trim() || refPath;
    return {
      params: {
        ...params,
        reference_role: "image_prompt",
        workflow_mode: "ipadapter",
        reference_image: referencePath,
        input_image: undefined,
        cn_selection: "None",
        cn_type: "None",
        edit_type: "auto",
        face_preservation: undefined,
        identity_mode: undefined,
      },
    };
  }

  if (role === "restyle") {
    return {
      params: buildRestyleSubmitParams(params, modelFamily, refPath),
    };
  }

  if (role === "structure") {
    const structurePath = params.reference_image?.trim() || refPath;
    const rawCn = (params.cn_type ?? "canny").toLowerCase();
    const cnType =
      rawCn === "img2img" || rawCn === "none" || rawCn === "auto" ? "canny" : rawCn;
    return {
      params: {
        ...params,
        reference_role: "structure",
        workflow_mode: "controlnet",
        reference_image: structurePath,
        input_image: undefined,
        cn_selection: "Custom...",
        cn_type: cnType,
        edit_type: "auto",
        face_preservation: undefined,
        identity_mode: undefined,
      },
    };
  }

  return {
    params: applyLegacyGenerateReferenceAutoRoute(params, modelFamily, refPath),
  };
}

function buildRestyleSubmitParams(
  params: GenerationSettings,
  modelFamily: string,
  refPath: string,
): GenerationSettings {
  return {
    ...params,
    reference_role: "restyle",
    workflow_mode: "generate",
    input_image: refPath,
    reference_image: params.reference_image?.trim() || refPath,
    cn_selection: "Custom...",
    cn_type: "img2img",
    edit_type: "auto",
    edit_strength:
      params.edit_strength ??
      defaultReferenceEditStrength(params, modelFamily),
    face_preservation: undefined,
    identity_mode: undefined,
  };
}

function applyEditFamilyReferenceRoleParams(
  params: GenerationSettings,
  studioMode: StudioMode,
  modelFamily: string,
): GenerationSettings {
  const role = inferReferenceRole(params, studioMode);
  if (role !== "source_edit") return params;
  if (!params.input_image?.trim()) return params;

  const family = modelFamily.toLowerCase();
  if (family.includes("kontext")) {
    return {
      ...params,
      reference_role: "source_edit",
      edit_type: "kontext",
      cn_selection: "None",
      cn_type: "None",
      edit_strength: params.edit_strength ?? 0.92,
    };
  }
  if (family === "qwen_image_edit" && params.edit_type !== "inpaint") {
    return {
      ...params,
      reference_role: "source_edit",
      edit_type: "qwen_edit",
      cn_selection: "None",
      cn_type: "None",
      edit_strength: params.edit_strength ?? 1.0,
    };
  }
  return { ...params, reference_role: "source_edit" };
}

/** Legacy auto-routing when reference_role is unset (Pro attach without role chip). */
function applyLegacyGenerateReferenceAutoRoute(
  params: GenerationSettings,
  modelFamily: string,
  refPath: string,
): GenerationSettings {
  const family = modelFamily.toLowerCase();
  if (family.includes("kontext") && refPath) {
    return {
      ...params,
      input_image: refPath,
      edit_type: "kontext",
      cn_selection: "None",
      cn_type: "None",
      edit_strength: params.edit_strength ?? 0.92,
    };
  }
  if (family === "qwen_image_edit" && refPath) {
    const next: GenerationSettings = {
      ...params,
      input_image: refPath,
      edit_type: "qwen_edit",
      cn_selection: "None",
      cn_type: "None",
    };
    if (next.edit_strength == null || next.edit_strength <= 0) {
      next.edit_strength = 1.0;
    }
    return next;
  }
  if (refPath) {
    return {
      ...params,
      input_image: refPath,
      cn_selection: "Custom...",
      cn_type: "img2img",
      edit_type:
        params.edit_type === "kontext" || params.edit_type === "qwen_edit"
          ? "auto"
          : (params.edit_type ?? "auto"),
      workflow_mode: "generate",
      edit_strength:
        params.edit_strength ??
        defaultReferenceEditStrength(params, modelFamily),
      face_preservation: undefined,
      identity_mode: undefined,
    };
  }
  return params;
}
