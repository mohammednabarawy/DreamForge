import type { ModelGalleryItem } from "./tauri-api";
import type { GenerationSettings } from "./tauri-api";
import { modelBasename, type StudioMode } from "./model-selection";
import {
  applyInpaintIntentAtSubmit,
} from "./inpaintIntent";

/** Canonical Flux Fill FP8 filename when the checkpoint is not yet in the gallery. */
export const DEFAULT_FLUX_FILL_MODEL = "flux1-fill-dev-fp8.safetensors";

/** Flux Fill checkpoints — preferred inpaint default. */
export const FLUX_FILL_NEEDLES = [
  "flux1-fill",
  "flux.1-fill",
  "flux-fill",
  "flux fill",
] as const;

/** Native / checkpoint inpaint hints (SDXL, SD1.5, dedicated inpaint merges). */
export const NATIVE_INPAINT_HINTS = [
  "inpaint",
  "512-inpainting",
  "in-painting",
] as const;

export function modelHaystack(item: ModelGalleryItem): string {
  return `${item.family} ${item.caption} ${item.engine_name} ${item.relative_path}`.toLowerCase();
}

export function isFluxFillModel(item: ModelGalleryItem): boolean {
  const hay = modelHaystack(item);
  return FLUX_FILL_NEEDLES.some((needle) => hay.includes(needle));
}

export function isNativeInpaintModel(item: ModelGalleryItem): boolean {
  const family = (item.family ?? "").toLowerCase();
  if (family === "flux_fill") return false;
  if (family === "sdxl" || family === "sd15" || family === "sdxl_inpaint") {
    return true;
  }
  const hay = modelHaystack(item);
  if (hay.includes("controlnet") && hay.includes("inpaint")) return false;
  return NATIVE_INPAINT_HINTS.some((needle) => hay.includes(needle));
}

export function isInpaintCapableModel(item: ModelGalleryItem): boolean {
  return isFluxFillModel(item) || isNativeInpaintModel(item);
}

export function findInpaintCapableModels(gallery: ModelGalleryItem[]): ModelGalleryItem[] {
  return gallery.filter(isInpaintCapableModel);
}

function scoreInpaintGalleryItem(item: ModelGalleryItem): number {
  if (!isInpaintCapableModel(item)) return -1;
  const hay = modelHaystack(item);
  let score = 0;
  if (isFluxFillModel(item)) {
    score += 80;
    if (hay.includes("fp8") || hay.includes("_fp8")) score += 15;
  }
  if (hay.includes("inpaint")) score += 40;
  const family = (item.family ?? "").toLowerCase();
  if (family === "sdxl" || family === "sdxl_inpaint" || family === "sd15") score += 25;
  if (hay.includes("lightning") && hay.includes("inpaint")) score += 10;
  return score;
}

function isFluxFillFp8Model(item: ModelGalleryItem): boolean {
  const hay = modelHaystack(item);
  return isFluxFillModel(item) && (hay.includes("fp8") || hay.includes("_fp8"));
}

/** Default inpaint checkpoint: best scored Fill or native inpaint model in gallery. */
export function selectFluxFillModel(gallery: ModelGalleryItem[]): string {
  let bestScore = -1;
  let bestEngine = "";
  for (const item of gallery) {
    const score = scoreInpaintGalleryItem(item);
    if (score > bestScore) {
      bestScore = score;
      bestEngine = item.engine_name;
    }
  }
  if (bestEngine) return bestEngine;
  const fp8 = gallery.find(isFluxFillFp8Model);
  if (fp8) return fp8.engine_name;
  for (const needle of FLUX_FILL_NEEDLES) {
    const hit = gallery.find((item) => modelHaystack(item).includes(needle));
    if (hit) return hit.engine_name;
  }
  return "";
}

export function selectCuratedInpaintModel(
  gallery: ModelGalleryItem[],
  _current?: string,
): string {
  return selectFluxFillModel(gallery);
}

export function inpaintModelWarning(
  item: ModelGalleryItem,
  mode: StudioMode,
): string | null {
  if (mode !== "inpaint") return null;
  if (isInpaintCapableModel(item)) return null;
  return `"${modelBasename(item.caption)}" is not recognized as inpaint-capable. Use Flux Fill or an SDXL/SD1.5 inpaint checkpoint.`;
}

export function sortGalleryForInpaintMode(
  gallery: ModelGalleryItem[],
  mode: StudioMode,
): ModelGalleryItem[] {
  if (mode !== "inpaint") return gallery;
  const scored = gallery
    .map((item) => ({ item, score: scoreInpaintGalleryItem(item) }))
    .sort((a, b) => b.score - a.score);
  const capable = scored.filter((row) => row.score >= 0).map((row) => row.item);
  const rest = scored.filter((row) => row.score < 0).map((row) => row.item);
  return [...capable, ...rest];
}

/** Flux Fill needs denoise 1.0; native inpaint keeps user/task strength. */
export function effectiveInpaintEditStrength(
  settings: GenerationSettings,
  modelItem: ModelGalleryItem | undefined,
): number {
  const raw = Number(settings.edit_strength ?? 0.9);
  if (modelItem && isFluxFillModel(modelItem)) {
    return 1.0;
  }
  return raw;
}

/** Force inpaint routing before submit (blocks stale Qwen/edit control-net state). */
export function enforceInpaintJobSettings(
  settings: GenerationSettings,
  studioMode: StudioMode,
  gallery: ModelGalleryItem[],
  advancedMode?: boolean,
): GenerationSettings {
  if (studioMode !== "inpaint") return settings;
  const merged = applyInpaintIntentAtSubmit(settings, gallery);
  const currentItem = gallery.find((item) => item.engine_name === merged.model);
  const userModel = merged.model?.trim();
  const userPickedCapable =
    Boolean(userModel) &&
    Boolean(currentItem) &&
    isInpaintCapableModel(currentItem!);
  const defaultModel = selectCuratedInpaintModel(gallery);
  const model =
    userPickedCapable || (advancedMode && userModel)
      ? userModel
      : defaultModel || userModel;
  const modelItem = gallery.find((item) => item.engine_name === model);
  return {
    ...merged,
    model,
    edit_strength: effectiveInpaintEditStrength(merged, modelItem),
    edit_type: "inpaint",
    cn_selection: "Custom...",
    cn_type: "inpaint",
    upscale_image: undefined,
    upscale_method: undefined,
  };
}
