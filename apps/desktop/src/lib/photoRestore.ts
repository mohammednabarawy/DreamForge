import type { GenerationSettings, ModelGalleryItem } from "./tauri-api";
import { PHOTO_RESTORE_DEFAULT_PROMPT } from "./editTaskPrompts";

/** Matches backend photo_restore workflow defaults (restore photo.json). */
export const PHOTO_RESTORE_SAMPLING = {
  steps: 6,
  cfg_scale: 1.5,
  sampler: "dpmpp_2s_ancestral_cfg_pp",
  scheduler: "karras",
  edit_strength: 0.4,
  depth_strength: 0.15,
  lineart_strength: 0.35,
} as const;

export { PHOTO_RESTORE_DEFAULT_PROMPT };

const SDXL_RESTORE_NEEDLES = [
  "epicrealism",
  "juggernaut",
  "realvis",
  "dreamshaper",
  "sd_xl",
  "sdxl",
] as const;

function galleryHaystack(item: ModelGalleryItem): string {
  return `${item.family ?? ""} ${item.caption ?? ""} ${item.engine_name} ${item.relative_path ?? ""}`.toLowerCase();
}

export function isPhotoRestoreSdxlModel(item: ModelGalleryItem): boolean {
  const family = (item.family ?? "").toLowerCase();
  const category = (item.category ?? "").toLowerCase();
  const hay = galleryHaystack(item);
  if (family === "sdxl" || hay.includes("sdxl")) {
    return category === "" || category === "checkpoints";
  }
  return SDXL_RESTORE_NEEDLES.some((needle) => hay.includes(needle));
}

export function selectPhotoRestoreModel(gallery: ModelGalleryItem[]): string {
  let bestName = "";
  let bestScore = -1;
  for (const item of gallery) {
    if (!isPhotoRestoreSdxlModel(item)) continue;
    const hay = galleryHaystack(item);
    let score = 0;
    if ((item.family ?? "").toLowerCase() === "sdxl") score += 100;
    if ((item.category ?? "").toLowerCase() === "checkpoints") score += 80;
    for (const needle of SDXL_RESTORE_NEEDLES) {
      if (hay.includes(needle)) score += 25;
    }
    if (hay.includes("turbo") || hay.includes("lightning")) score -= 10;
    if (score > bestScore) {
      bestScore = score;
      bestName = item.engine_name;
    }
  }
  return bestName;
}

export function patchForPhotoRestoreTask(
  settings: GenerationSettings,
  gallery: ModelGalleryItem[],
): Partial<GenerationSettings> {
  const restoreModel = selectPhotoRestoreModel(gallery);
  const prompt = (settings.prompt ?? "").trim();
  return {
    edit_task: "photo_restore",
    edit_type: undefined,
    cn_type: undefined,
    cn_selection: undefined,
    inpaint_mask_path: undefined,
    inpaint_intent: undefined,
    model: restoreModel || settings.model,
    style: "image_edit",
    ...PHOTO_RESTORE_SAMPLING,
    face_preservation: true,
    prompt: prompt || PHOTO_RESTORE_DEFAULT_PROMPT,
  };
}

export function isPhotoRestoreTask(settings: GenerationSettings): boolean {
  return (settings.edit_task ?? "").toLowerCase() === "photo_restore";
}
