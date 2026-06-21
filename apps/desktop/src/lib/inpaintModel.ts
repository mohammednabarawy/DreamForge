import type { ModelGalleryItem } from "./tauri-api";
import type { GenerationSettings } from "./tauri-api";
import { modelBasename, type StudioMode } from "./model-selection";

/** Canonical Flux Fill FP8 filename when the checkpoint is not yet in the gallery. */
export const DEFAULT_FLUX_FILL_MODEL = "flux1-fill-dev-fp8.safetensors";

/** Flux Fill checkpoints - the only inpaint default (no fallback). */
export const FLUX_FILL_NEEDLES = [
  "flux1-fill",
  "flux.1-fill",
  "flux-fill",
  "flux fill",
] as const;

/** Broader hints for manual inpaint-capable picks (override / warnings only). */
export const INPAINT_MODEL_HINTS = [
  ...FLUX_FILL_NEEDLES,
  "fill",
  "inpaint",
] as const;

export function modelHaystack(item: ModelGalleryItem): string {
  return `${item.family} ${item.caption} ${item.engine_name} ${item.relative_path}`.toLowerCase();
}

export function isFluxFillModel(item: ModelGalleryItem): boolean {
  const hay = modelHaystack(item);
  return FLUX_FILL_NEEDLES.some((needle) => hay.includes(needle));
}

export function isInpaintCapableModel(item: ModelGalleryItem): boolean {
  if (isFluxFillModel(item)) return true;
  if ((item.family ?? "").toLowerCase() === "ideogram4") return true;
  const hay = modelHaystack(item);
  return INPAINT_MODEL_HINTS.some((needle) => hay.includes(needle));
}

export function findInpaintCapableModels(gallery: ModelGalleryItem[]): ModelGalleryItem[] {
  return gallery.filter(isInpaintCapableModel);
}

function isFluxFillFp8Model(item: ModelGalleryItem): boolean {
  const hay = modelHaystack(item);
  return isFluxFillModel(item) && (hay.includes("fp8") || hay.includes("_fp8"));
}

/** Default inpaint checkpoint: Flux Fill FP8 preferred, then any Fill (empty when not installed). */
export function selectFluxFillModel(gallery: ModelGalleryItem[]): string {
  const fillModels = gallery.filter(isFluxFillModel);
  const fp8 = fillModels.find(isFluxFillFp8Model);
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
  if (isFluxFillModel(item)) return null;
  return `"${modelBasename(item.caption)}" is not Flux Fill — inpaint may fail. Default route is Flux Fill; override only if you know this checkpoint supports inpaint.`;
}

export function sortGalleryForInpaintMode(
  gallery: ModelGalleryItem[],
  mode: StudioMode,
): ModelGalleryItem[] {
  if (mode !== "inpaint") return gallery;
  const recommendedFp8: ModelGalleryItem[] = [];
  const recommendedOtherFill: ModelGalleryItem[] = [];
  const other: ModelGalleryItem[] = [];
  for (const item of gallery) {
    if (isFluxFillFp8Model(item)) recommendedFp8.push(item);
    else if (isFluxFillModel(item)) recommendedOtherFill.push(item);
    else other.push(item);
  }
  return [...recommendedFp8, ...recommendedOtherFill, ...other];
}

/** Force Flux Fill + inpaint routing before submit (blocks stale Qwen/edit control-net state). */
export function enforceInpaintJobSettings(
  settings: GenerationSettings,
  studioMode: StudioMode,
  gallery: ModelGalleryItem[],
  _advancedMode?: boolean,
): GenerationSettings {
  if (studioMode !== "inpaint") return settings;
  const fluxDefault = selectFluxFillModel(gallery) || DEFAULT_FLUX_FILL_MODEL;
  return {
    ...settings,
    model: settings.model?.trim() || fluxDefault,
    edit_type: "inpaint",
    cn_selection: "Custom...",
    cn_type: "inpaint",
    upscale_image: undefined,
    upscale_method: undefined,
  };
}
