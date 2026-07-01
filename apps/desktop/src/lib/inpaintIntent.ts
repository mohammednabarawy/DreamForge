import type { GenerationSettings, ModelGalleryItem } from "./tauri-api";
import {
  PHOTO_RESTORE_SAMPLING,
  selectPhotoRestoreModel,
} from "./photoRestore";
import {
  DEFAULT_FLUX_FILL_MODEL,
  isFluxFillModel,
  selectFluxFillModel,
} from "./inpaintModel";
import { DEFAULT_QWEN_EDIT_MODEL, selectQwenEditModel } from "./editModel";
import { qwenEdit2511LightningPatch } from "./qwenEditDefaults";

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
  {
    id: "photo_restore",
    label: "Restore photo",
    short: "Restore",
    hint: "Restore old, damaged, or low-quality photos with structure-preserving ControlNet.",
  },
  {
    id: "outfit_transfer",
    label: "Outfit transfer",
    short: "Outfit",
    hint: "Use the source person plus an outfit reference; add a mask for Flux Fill fallback.",
    inpaintIntent: "modify_content",
  },
  {
    id: "cutout_compose",
    label: "Cutout compose",
    short: "Cutout",
    hint: "Remove background from subject and harmonize lighting with a new background canvas.",
    inpaintIntent: "modify_content",
  },
];

export function normalizeEditTask(value: string | undefined | null): EditTask | undefined {
  const task = (value ?? "").trim().toLowerCase();
  return EDIT_TASKS.some((item) => item.id === task) ? (task as EditTask) : undefined;
}

export function patchForEditTask(
  task: EditTask,
  gallery: ModelGalleryItem[] = [],
  options: { isInpaint?: boolean; hasMask?: boolean } = {},
): Partial<GenerationSettings> {
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
  } else if (task === "photo_restore") {
    const restoreModel = selectPhotoRestoreModel(gallery);
    patch.edit_type = undefined;
    patch.cn_type = undefined;
    patch.cn_selection = undefined;
    patch.outpaint_direction = undefined;
    patch.outpaint_amount = undefined;
    patch.outpaint_feathering = undefined;
    patch.inpaint_mask_path = undefined;
    patch.model = restoreModel || undefined;
    patch.steps = PHOTO_RESTORE_SAMPLING.steps;
    patch.cfg_scale = PHOTO_RESTORE_SAMPLING.cfg_scale;
    patch.sampler = PHOTO_RESTORE_SAMPLING.sampler;
    patch.scheduler = PHOTO_RESTORE_SAMPLING.scheduler;
    patch.edit_strength = PHOTO_RESTORE_SAMPLING.edit_strength;
    patch.depth_strength = PHOTO_RESTORE_SAMPLING.depth_strength;
    patch.lineart_strength = PHOTO_RESTORE_SAMPLING.lineart_strength;
    patch.face_preservation = true;
  } else if (task === "outfit_transfer") {
    patch.outpaint_direction = undefined;
    patch.outpaint_amount = undefined;
    patch.outpaint_feathering = undefined;
    if (options.isInpaint || options.hasMask) {
      const intent = "modify_content";
      const preset = PRESETS[intent];
      patch.inpaint_intent = intent;
      patch.model = selectInpaintModelForIntent(gallery, intent);
      patch.edit_type = "inpaint";
      patch.cn_selection = "Custom...";
      patch.cn_type = "inpaint";
      patch.edit_strength = preset.edit_strength;
      patch.inpaint_grow = preset.inpaint_grow;
      patch.inpaint_feather = preset.inpaint_feather;
      patch.inpaint_mask_grow_by = preset.inpaint_mask_grow_by;
    } else {
      Object.assign(patch, qwenEdit2511LightningPatch());
      patch.model = selectQwenEditModel(gallery) || DEFAULT_QWEN_EDIT_MODEL;
      patch.qwen_edit_mode = "plus";
      patch.reference_role = "source_edit";
      patch.inpaint_mask_path = undefined;
    }
  } else if (task === "cutout_compose") {
    patch.outpaint_direction = undefined;
    patch.outpaint_amount = undefined;
    patch.outpaint_feathering = undefined;
    patch.edit_type = undefined;
    patch.cn_type = undefined;
    patch.cn_selection = undefined;
    Object.assign(patch, qwenEdit2511LightningPatch());
    patch.edit_strength = 0.35;
    patch.model = selectQwenEditModel(gallery) || DEFAULT_QWEN_EDIT_MODEL;
    patch.qwen_edit_mode = "plus";
    patch.reference_role = "source_edit";
    patch.inpaint_mask_path = undefined;
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
