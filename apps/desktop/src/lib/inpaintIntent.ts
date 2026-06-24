import type { GenerationSettings, ModelGalleryItem } from "./tauri-api";
import {
  DEFAULT_FLUX_FILL_MODEL,
  isFluxFillModel,
  selectFluxFillModel,
} from "./inpaintModel";

export type InpaintIntent = "default" | "improve_detail" | "modify_content";

export const INPAINT_INTENTS: Array<{
  id: InpaintIntent;
  label: string;
  short: string;
  hint: string;
}> = [
  {
    id: "default",
    label: "Default",
    short: "Default",
    hint: "Balanced Flux Fill inpaint with surrounding context.",
  },
  {
    id: "improve_detail",
    label: "Improve detail",
    short: "Detail",
    hint: "Refine masked details — lower strength, minimal context bleed.",
  },
  {
    id: "modify_content",
    label: "Modify content",
    short: "Modify",
    hint: "Replace masked content — full strength, masked-only context.",
  },
];

const PRESETS: Record<
  InpaintIntent,
  Pick<
    GenerationSettings,
    "edit_strength" | "inpaint_grow" | "inpaint_feather" | "inpaint_mask_grow_by"
  > & { requiresFillEngine: boolean }
> = {
  default: {
    edit_strength: 0.88,
    inpaint_grow: 4,
    inpaint_feather: 4,
    inpaint_mask_grow_by: 20,
    requiresFillEngine: true,
  },
  improve_detail: {
    edit_strength: 0.52,
    inpaint_grow: 2,
    inpaint_feather: 2,
    inpaint_mask_grow_by: 6,
    requiresFillEngine: false,
  },
  modify_content: {
    edit_strength: 1.0,
    inpaint_grow: 0,
    inpaint_feather: 0,
    inpaint_mask_grow_by: 0,
    requiresFillEngine: true,
  },
};

export function normalizeInpaintIntent(
  value: string | undefined | null,
): InpaintIntent {
  const intent = (value ?? "default").trim().toLowerCase();
  if (intent === "improve_detail" || intent === "modify_content") return intent;
  return "default";
}

export function inpaintIntentPreset(intent: InpaintIntent) {
  return PRESETS[intent];
}

export function patchForInpaintIntent(intent: InpaintIntent): Partial<GenerationSettings> {
  const preset = PRESETS[intent];
  return {
    inpaint_intent: intent,
    edit_strength: preset.edit_strength,
    inpaint_grow: preset.inpaint_grow,
    inpaint_feather: preset.inpaint_feather,
    inpaint_mask_grow_by: preset.inpaint_mask_grow_by,
  };
}

function modelHaystack(item: ModelGalleryItem): string {
  return `${item.family} ${item.caption} ${item.engine_name} ${item.relative_path}`.toLowerCase();
}

/** Flux dev FP8 for improve-detail passes; otherwise Flux Fill. */
export function selectInpaintModelForIntent(
  gallery: ModelGalleryItem[],
  intent: InpaintIntent,
  current?: string,
): string {
  const preset = PRESETS[intent];
  if (preset.requiresFillEngine) {
    return current?.trim() || selectFluxFillModel(gallery) || DEFAULT_FLUX_FILL_MODEL;
  }
  const needles = ["flux1-dev-fp8", "flux1-dev", "flux-dev", "flux_dev"];
  const hit = gallery.find((item) => {
    const hay = modelHaystack(item);
    return (
      needles.some((needle) => hay.includes(needle)) &&
      !hay.includes("fill") &&
      !hay.includes("kontext")
    );
  });
  if (hit?.engine_name) return hit.engine_name;
  if (current?.trim()) {
    const item = gallery.find((m) => m.engine_name === current);
    if (item && !isFluxFillModel(item)) return current.trim();
  }
  return selectFluxFillModel(gallery) || DEFAULT_FLUX_FILL_MODEL;
}

export function applyInpaintIntentAtSubmit(
  settings: GenerationSettings,
  gallery: ModelGalleryItem[],
): GenerationSettings {
  const intent = normalizeInpaintIntent(settings.inpaint_intent);
  const preset = PRESETS[intent];
  const model = selectInpaintModelForIntent(gallery, intent, settings.model);
  return {
    ...settings,
    inpaint_intent: intent,
    model,
    edit_type: "inpaint",
    cn_selection: "Custom...",
    cn_type: "inpaint",
    edit_strength: settings.edit_strength ?? preset.edit_strength,
    inpaint_grow: settings.inpaint_grow ?? preset.inpaint_grow,
    inpaint_feather: settings.inpaint_feather ?? preset.inpaint_feather,
    inpaint_mask_grow_by:
      settings.inpaint_mask_grow_by ?? preset.inpaint_mask_grow_by,
  };
}

export function showInpaintAdditionalPrompt(intent: InpaintIntent): boolean {
  return intent === "improve_detail" || intent === "modify_content";
}
