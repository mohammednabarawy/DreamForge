import type { ModelGalleryItem } from "./tauri-api";
import type { GenerationSettings } from "./tauri-api";
import { modelBasename, type StudioMode } from "./model-selection";
import {
  applyInpaintIntentAtSubmit,
} from "./inpaintIntent";
import { isQwenEditModel, selectQwenEditModel } from "./editModel";

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
  return isQwenEditModel(item);
}

export function findInpaintCapableModels(gallery: ModelGalleryItem[]): ModelGalleryItem[] {
  return gallery.filter(isInpaintCapableModel);
}

/** Default inpaint checkpoint: best scored Fill or native inpaint model in gallery. */
export function selectFluxFillModel(gallery: ModelGalleryItem[]): string {
  return selectQwenEditModel(gallery);
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
  return `"${modelBasename(item.caption)}" cannot be used for masked editing. DreamForge edits only with Qwen Image 2.1.`;
}

export function sortGalleryForInpaintMode(
  gallery: ModelGalleryItem[],
  mode: StudioMode,
): ModelGalleryItem[] {
  if (mode !== "inpaint") return gallery;
  return gallery.filter(isQwenEditModel);
}

/** Flux Fill needs denoise 1.0; native inpaint keeps user/task strength. */
export function effectiveInpaintEditStrength(
  _settings: GenerationSettings,
  _modelItem: ModelGalleryItem | undefined,
): number {
  return 1.0;
}

/** Force inpaint routing before submit (blocks stale Qwen/edit control-net state). */
export function enforceInpaintJobSettings(
  settings: GenerationSettings,
  studioMode: StudioMode,
  gallery: ModelGalleryItem[],
  _advancedMode?: boolean,
): GenerationSettings {
  if (studioMode !== "inpaint") return settings;
  const merged = applyInpaintIntentAtSubmit(settings, gallery);
  const defaultModel = selectCuratedInpaintModel(gallery);
  const model = defaultModel || merged.model;
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
