import type { StudioMode } from "./model-selection";
import { coerceReferenceSlots } from "./referenceSlots";
import type { GenerationSettings } from "./tauri-api";

const RAW_QWEN_MODES = new Set([
  "raw",
  "raw_plus",
  "preserve",
  "preserve_resolution",
  "exact",
]);

function isQwenEditJob(
  settings: GenerationSettings,
  studioMode: StudioMode,
  modelFamily: string,
): boolean {
  // Identity/compose routing may switch to a Qwen edit model after modelFamily
  // was captured, so trust an explicit qwen_edit edit_type regardless of family.
  const editType = (settings.edit_type ?? "").toLowerCase();
  if (editType === "qwen_edit") return true;
  const fam = modelFamily.toLowerCase();
  if (!fam.startsWith("qwen")) return false;
  if (studioMode === "edit") return true;
  return false;
}

/** Enable raw-latent Qwen Edit Plus when layout/text fidelity matters. */
export function applyQwenPreserveAtSubmit(
  settings: GenerationSettings,
  studioMode: StudioMode,
  modelFamily: string,
): GenerationSettings {
  if (!isQwenEditJob(settings, studioMode, modelFamily)) {
    return settings;
  }

  const mode = (settings.qwen_edit_mode ?? "auto").toLowerCase();
  if (RAW_QWEN_MODES.has(mode) || settings.qwen_preserve_resolution) {
    return {
      ...settings,
      qwen_preserve_resolution: true,
      qwen_edit_mode:
        mode === "auto" || mode === "plus" ? "raw_plus" : settings.qwen_edit_mode,
    };
  }

  const slots = coerceReferenceSlots(settings, studioMode);
  const extraRefs = Math.max(0, slots.length - 1);
  const hasBase = slots.some(
    (s) => s.role === "source_edit" || s.role === "restyle" || s.role === "inpaint",
  );
  const refCount = hasBase ? extraRefs : slots.length;
  const needsLayout =
    Boolean(settings.preserve_text) ||
    Boolean(settings.preserve_character && refCount >= 1) ||
    refCount >= 2;

  if (!needsLayout) {
    return settings;
  }

  return {
    ...settings,
    qwen_preserve_resolution: true,
    qwen_edit_mode: mode === "auto" ? "raw_plus" : settings.qwen_edit_mode,
  };
}
