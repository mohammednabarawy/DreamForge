import type { GenerationSettings, ModelGalleryItem } from "./tauri-api";
import { modelBasename, type StudioMode } from "./model-selection";

/** Canonical Flux Kontext FP8 filename when the checkpoint is not yet in the gallery. */
export const DEFAULT_FLUX_KONTEXT_EDIT_MODEL =
  "flux1-dev-kontext_fp8_scaled.safetensors";

export const FLUX_KONTEXT_NEEDLES = [
  "flux1-dev-kontext_fp8_scaled",
  "flux1-dev-kontext",
  "flux.1-kontext",
  "flux kontext",
] as const;

const IMG2IMG_EDIT_FAMILIES = new Set([
  "sdxl",
  "sd15",
  "flux",
  "flux2",
  "hidream",
  "hidream_o1",
  "ideogram4",
  "krea2",
  "z_image",
]);

export function modelHaystack(item: ModelGalleryItem): string {
  return `${item.family} ${item.caption} ${item.engine_name} ${item.relative_path}`.toLowerCase();
}

export function isFluxKontextEditModel(item: ModelGalleryItem): boolean {
  const family = (item.family ?? "").toLowerCase();
  if (family === "flux_kontext") return true;
  const hay = modelHaystack(item);
  if (hay.includes("fill")) return false;
  return FLUX_KONTEXT_NEEDLES.some((needle) => hay.includes(needle));
}

export function isQwenEditModel(item: ModelGalleryItem): boolean {
  const family = (item.family ?? "").toLowerCase();
  if (family === "qwen_image_edit") return true;
  const hay = modelHaystack(item);
  return hay.includes("qwen") && hay.includes("edit");
}

export function isImg2ImgEditModel(item: ModelGalleryItem): boolean {
  const family = (item.family ?? "").toLowerCase();
  if (IMG2IMG_EDIT_FAMILIES.has(family)) return true;
  const hay = modelHaystack(item);
  if (hay.includes("flux") && !hay.includes("fill") && !hay.includes("kontext")) {
    return true;
  }
  return false;
}

export function isEditCapableModel(item: ModelGalleryItem): boolean {
  return (
    isFluxKontextEditModel(item) ||
    isQwenEditModel(item) ||
    isImg2ImgEditModel(item)
  );
}

export function selectFluxKontextEditModel(gallery: ModelGalleryItem[]): string {
  for (const needle of FLUX_KONTEXT_NEEDLES) {
    const hit = gallery.find(
      (item) => modelHaystack(item).includes(needle) && !modelHaystack(item).includes("fill"),
    );
    if (hit) return hit.engine_name;
  }
  const familyHit = gallery.find(
    (item) => (item.family ?? "").toLowerCase() === "flux_kontext",
  );
  return familyHit?.engine_name ?? "";
}

/** Canonical Qwen Edit GGUF filename when the checkpoint is not yet in the gallery. */
export const DEFAULT_QWEN_EDIT_MODEL = "qwen-image-edit-2511-Q4_K_M.gguf";

export function scoreQwenEditGalleryItem(item: ModelGalleryItem): number {
  const hay = modelHaystack(item);
  if (!hay.includes("qwen") || !hay.includes("edit")) return -1;
  let score = 0;
  if (hay.includes("q4_k_m") && hay.includes(".gguf")) score += 100;
  else if (hay.includes(".gguf") && (hay.includes("q4") || hay.includes("q5"))) score += 85;
  else if (hay.includes(".gguf")) score += 75;
  else if (hay.includes("2511") && hay.includes("fp8") && !hay.includes("lightning")) score += 35;
  else if (hay.includes("2511")) score += 30;
  else if (hay.includes("fp8") && !hay.includes("lightning")) score += 20;
  if (hay.includes("lightning") && (hay.includes("4step") || hay.includes("4steps"))) score -= 25;
  if (hay.includes("lightning") && hay.includes("fp8")) score -= 15;
  if (hay.includes("2511")) score += 10;
  return score;
}

export function selectQwenEditModel(gallery: ModelGalleryItem[]): string {
  let bestScore = -1;
  let bestEngine = "";
  for (const item of gallery) {
    const s = scoreQwenEditGalleryItem(item);
    if (s > bestScore) {
      bestScore = s;
      bestEngine = item.engine_name;
    }
  }
  return bestEngine;
}

export function selectCuratedEditModel(gallery: ModelGalleryItem[]): string {
  const kontext = selectFluxKontextEditModel(gallery);
  if (kontext) return kontext;
  return selectQwenEditModel(gallery);
}

export function editModelWarning(
  item: ModelGalleryItem,
  mode: StudioMode,
): string | null {
  if (mode !== "edit") return null;
  if (isEditCapableModel(item)) return null;
  return `"${modelBasename(item.caption)}" may not support instruction edits — Flux Kontext, Qwen Edit, or img2img checkpoints work best.`;
}

export function sortGalleryForEditMode(
  gallery: ModelGalleryItem[],
  mode: StudioMode,
): ModelGalleryItem[] {
  if (mode !== "edit") return gallery;
  const kontext: ModelGalleryItem[] = [];
  const qwen: ModelGalleryItem[] = [];
  const img2img: ModelGalleryItem[] = [];
  const other: ModelGalleryItem[] = [];
  for (const item of gallery) {
    if (isFluxKontextEditModel(item)) kontext.push(item);
    else if (isQwenEditModel(item)) qwen.push(item);
    else if (isImg2ImgEditModel(item)) img2img.push(item);
    else other.push(item);
  }
  return [...kontext, ...qwen, ...img2img, ...other];
}

/** Map a user-selected edit model to the correct edit_type / control-net routing. */
export function buildEditRoutingPatch(
  item: ModelGalleryItem | undefined,
): Partial<GenerationSettings> {
  if (!item) {
    return {
      edit_type: "kontext",
      edit_strength: 1.0,
      cn_selection: "None",
      cn_type: "None",
      steps: 20,
    };
  }
  if (isQwenEditModel(item)) {
    return {
      edit_type: "qwen_edit",
      edit_strength: 1.0,
      cn_selection: "None",
      cn_type: "None",
    };
  }
  if (isFluxKontextEditModel(item) || (item.family ?? "").toLowerCase() === "flux_kontext") {
    return {
      edit_type: "kontext",
      edit_strength: 1.0,
      cn_selection: "None",
      cn_type: "None",
      steps: 20,
    };
  }
  if ((item.family ?? "").toLowerCase() === "ideogram4") {
    return {
      edit_type: "kontext",
      edit_strength: 1.0,
      cn_selection: "None",
      cn_type: "None",
    };
  }
  if (isImg2ImgEditModel(item)) {
    return {
      edit_type: "img2img",
      edit_strength: 0.75,
      cn_selection: "Custom...",
      cn_type: "img2img",
    };
  }
  return {
    edit_type: "kontext",
    edit_strength: 1.0,
    cn_selection: "None",
    cn_type: "None",
    steps: 20,
  };
}
