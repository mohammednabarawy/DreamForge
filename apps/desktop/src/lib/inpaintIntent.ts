import type { GenerationSettings, ModelGalleryItem } from "./tauri-api";
import {
  DEFAULT_FLUX_FILL_MODEL,
  isFluxFillModel,
  selectFluxFillModel,
} from "./inpaintModel";

export type InpaintIntent = "default" | "improve_detail" | "modify_content";
export type EditTask = NonNullable<GenerationSettings["edit_task"]>;

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
    hint: "Replace masked content — full strength with blended edges.",
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
    requiresFillEngine: true,
  },
  modify_content: {
    edit_strength: 1.0,
    inpaint_grow: 8,
    inpaint_feather: 8,
    inpaint_mask_grow_by: 16,
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

export const EDIT_TASKS: Array<{
  id: EditTask;
  label: string;
  short: string;
  hint: string;
  inpaintIntent?: InpaintIntent;
  inpaintOnly?: boolean;
}> = [
  {
    id: "remove",
    label: "Remove",
    short: "Remove",
    hint: "Remove masked content and continue the background naturally.",
    inpaintIntent: "modify_content",
    inpaintOnly: true,
  },
  {
    id: "replace",
    label: "Replace",
    short: "Replace",
    hint: "Replace the masked area with the prompt description.",
    inpaintIntent: "modify_content",
    inpaintOnly: true,
  },
  {
    id: "repair",
    label: "Repair",
    short: "Repair",
    hint: "Fix masked details while preserving identity and surroundings.",
    inpaintIntent: "improve_detail",
    inpaintOnly: true,
  },
  {
    id: "refine",
    label: "Refine",
    short: "Refine",
    hint: "Polish masked details with a lighter detail-preserving pass.",
    inpaintIntent: "improve_detail",
    inpaintOnly: true,
  },
  {
    id: "extend",
    label: "Extend",
    short: "Extend",
    hint: "Prepare a canvas-extension task; full outpaint controls are coming in a later phase.",
    inpaintIntent: "default",
    inpaintOnly: true,
  },
  {
    id: "global_edit",
    label: "Global edit",
    short: "Global",
    hint: "Apply a global instruction edit to the source image.",
  },
];

export function normalizeEditTask(value: string | undefined | null): EditTask | undefined {
  const task = (value ?? "").trim().toLowerCase();
  return EDIT_TASKS.some((item) => item.id === task) ? (task as EditTask) : undefined;
}

export function patchForEditTask(task: EditTask): Partial<GenerationSettings> {
  if (!EDIT_TASKS.some((entry) => entry.id === task)) return {};
  const patch: Partial<GenerationSettings> = {
    edit_task: task,
    inpaint_intent: undefined,
    edit_strength: undefined,
    inpaint_grow: undefined,
    inpaint_feather: undefined,
    inpaint_mask_grow_by: undefined,
  };
  if (task === "extend") {
    patch.edit_type = "outpaint";
    patch.cn_type = "outpaint";
    patch.cn_selection = "Custom...";
    patch.outpaint_direction = patch.outpaint_direction ?? "right";
    patch.outpaint_amount = patch.outpaint_amount ?? 256;
    patch.outpaint_feathering = patch.outpaint_feathering ?? 40;
  } else if (task !== "global_edit") {
    patch.edit_type = "inpaint";
    patch.cn_type = "inpaint";
    patch.cn_selection = "Custom...";
    patch.outpaint_direction = undefined;
    patch.outpaint_amount = undefined;
    patch.outpaint_feathering = undefined;
  } else {
    patch.edit_type = undefined;
    patch.cn_type = undefined;
    patch.cn_selection = undefined;
    patch.outpaint_direction = undefined;
    patch.outpaint_amount = undefined;
    patch.outpaint_feathering = undefined;
  }
  return patch;
}

/** Always route inpaint intents through Flux Fill. */
export function selectInpaintModelForIntent(
  gallery: ModelGalleryItem[],
  _intent: InpaintIntent,
  current?: string,
): string {
  const trimmed = current?.trim();
  const currentItem = trimmed
    ? gallery.find((m) => m.engine_name === trimmed)
    : undefined;
  if (currentItem && isFluxFillModel(currentItem)) {
    return trimmed!;
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
