import type { GenerationSettings } from "./tauri-api";

export type EnhanceTarget = "face" | "hands" | "eyes" | "auto";

export const ENHANCE_TARGETS: Array<{
  id: EnhanceTarget;
  label: string;
  short: string;
  hint: string;
  detailPrompt: string;
}> = [
  {
    id: "face",
    label: "Fix face",
    short: "Face",
    hint: "FaceDetailer pass on detected faces (Impact Pack).",
    detailPrompt: "detailed face, sharp eyes, natural skin, high quality portrait",
  },
  {
    id: "hands",
    label: "Fix hands",
    short: "Hands",
    hint: "FaceDetailer hand detector pass.",
    detailPrompt: "detailed hands, natural fingers, anatomically correct",
  },
  {
    id: "eyes",
    label: "Fix eyes",
    short: "Eyes",
    hint: "Auto-mask eyes region then inpaint with improve-detail intent.",
    detailPrompt: "sharp detailed eyes, clear iris, natural eyelashes",
  },
];

export function normalizeEnhanceTarget(
  value: string | undefined | null,
): EnhanceTarget | undefined {
  const key = (value ?? "").trim().toLowerCase();
  if (key === "face" || key === "hands" || key === "eyes" || key === "auto") {
    return key;
  }
  return undefined;
}

export function patchForEnhanceTarget(
  target: EnhanceTarget,
  imagePath: string,
  options: {
    detectionPrompt?: string;
    postUpscale?: boolean;
    detailPrompt?: string;
  } = {},
): Partial<GenerationSettings> {
  const preset = ENHANCE_TARGETS.find((item) => item.id === target);
  const detailPrompt =
    options.detailPrompt?.trim() ||
    options.detectionPrompt?.trim() ||
    preset?.detailPrompt ||
    ENHANCE_TARGETS[0].detailPrompt;

  const patch: Partial<GenerationSettings> = {
    enhance_auto_fix: true,
    enhance_target: target,
    enhance_detection_prompt: options.detectionPrompt?.trim() || undefined,
    enhance_post_upscale: Boolean(options.postUpscale),
    upscale_image: imagePath,
    input_image: imagePath,
    detail_prompt: detailPrompt,
    style: "image_edit",
  };

  if (target === "face" || target === "hands") {
    return {
      ...patch,
      workflow_mode: "face_detail",
      detail_target: target === "hands" ? "hand" : "face",
      cn_selection: "None",
      cn_type: "None",
      edit_type: "auto",
    };
  }

  return {
    ...patch,
    workflow_mode: "generate",
    reference_role: "inpaint",
    edit_type: "inpaint",
    cn_selection: "Custom...",
    cn_type: "inpaint",
    inpaint_intent: "improve_detail",
  };
}

export function applyAutoEnhanceAtSubmit(
  settings: GenerationSettings,
): GenerationSettings {
  if (!settings.enhance_auto_fix && !settings.enhance_target) {
    return settings;
  }
  const target = normalizeEnhanceTarget(settings.enhance_target) ?? "face";
  const src =
    settings.upscale_image?.trim() ||
    settings.input_image?.trim() ||
    settings.reference_image?.trim() ||
    "";
  if (!src) return settings;

  const base = patchForEnhanceTarget(target, src, {
    detectionPrompt: settings.enhance_detection_prompt,
    postUpscale: settings.enhance_post_upscale,
    detailPrompt: settings.detail_prompt,
  });

  return {
    ...settings,
    ...base,
    post_upscale_enabled: settings.enhance_post_upscale
      ? true
      : settings.post_upscale_enabled,
    post_upscale: settings.enhance_post_upscale
      ? settings.post_upscale ?? "ultimate_sd_upscale"
      : settings.post_upscale,
  };
}

export function clearAutoEnhancePatch(): Partial<GenerationSettings> {
  return {
    enhance_auto_fix: undefined,
    enhance_target: undefined,
    enhance_detection_prompt: undefined,
    enhance_post_upscale: undefined,
    workflow_mode: undefined,
    detail_target: undefined,
    detail_prompt: undefined,
  };
}
