import type { GenerationSettings } from "./tauri-api";
import type { StudioMode } from "./model-selection";

const DEFAULT_TEMPLATE_BY_MODE: Record<string, string> = {
  generate: "create.default",
  edit: "edit.kontext",
  inpaint: "inpaint.flux_fill",
  upscale: "enhance.ultimate_sd",
};

/** Client-side default template id (mirrors backend creative_templates.json). */
export function defaultTemplateIdForMode(
  studioMode: StudioMode,
  postUpscaleEnabled?: boolean,
): string | undefined {
  const mode = studioMode === "agent" ? "generate" : studioMode;
  const base = DEFAULT_TEMPLATE_BY_MODE[mode];
  if (!base) return undefined;
  if (postUpscaleEnabled && (mode === "edit" || mode === "inpaint")) {
    return `${base}.enhance2x`;
  }
  return base;
}

/** Apply implicit template + post-upscale chain flags before submit. */
export function applyCreativeTemplateDefaults(
  settings: GenerationSettings,
  studioMode: StudioMode,
): GenerationSettings {
  const postEnabled = Boolean(settings.post_upscale_enabled);
  const templateId =
    settings.template_id?.trim() ||
    defaultTemplateIdForMode(studioMode, postEnabled);
  const next: GenerationSettings = { ...settings };
  if (templateId) next.template_id = templateId;
  if (postEnabled && (studioMode === "edit" || studioMode === "inpaint")) {
    next.post_upscale = next.post_upscale ?? "ultimate_sd_upscale";
    next.upscale_image = undefined;
    next.upscale_method = undefined;
  } else if (!postEnabled && studioMode !== "upscale") {
    next.post_upscale = undefined;
  }
  return next;
}
