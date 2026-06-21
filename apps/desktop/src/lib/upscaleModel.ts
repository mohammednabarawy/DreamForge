import type { ModelGalleryItem } from "./tauri-api";
import { modelBasename, type StudioMode } from "./model-selection";

/** SDXL checkpoints work best with Ultimate SD Upscale (tile diffusion + img2img). */
export const SDXL_UPSCALE_NEEDLES = [
  "epicrealism",
  "juggernaut",
  "realvis",
  "dreamshaper",
  "sd_xl",
  "sdxl",
] as const;

export function modelHaystack(item: ModelGalleryItem): string {
  return `${item.family} ${item.caption} ${item.engine_name} ${item.relative_path}`.toLowerCase();
}

export function isSdxlCheckpoint(item: ModelGalleryItem): boolean {
  const family = (item.family ?? "").toLowerCase();
  const category = (item.category ?? "").toLowerCase();
  const hay = modelHaystack(item);
  if (family === "sdxl" || hay.includes("sdxl")) return category === "checkpoints" || category === "";
  return SDXL_UPSCALE_NEEDLES.some((needle) => hay.includes(needle));
}

export function isUpscaleCompatibleModel(item: ModelGalleryItem): boolean {
  const family = (item.family ?? "").toLowerCase();
  const hay = modelHaystack(item);
  if (family.startsWith("z-image") || family.startsWith("z_image")) return false;
  if (family === "ideogram4" || hay.includes("ideogram")) return false;
  if (family.startsWith("flux") && (item.category ?? "").toLowerCase() !== "checkpoints") {
    return false;
  }
  return isSdxlCheckpoint(item) || (item.category ?? "").toLowerCase() === "checkpoints";
}

function scoreUpscaleGalleryItem(item: ModelGalleryItem): number {
  if (!isUpscaleCompatibleModel(item)) return -1;
  const hay = modelHaystack(item);
  const family = (item.family ?? "").toLowerCase();
  let score = 0;
  if (family === "sdxl") score += 100;
  if ((item.category ?? "").toLowerCase() === "checkpoints") score += 80;
  for (const needle of SDXL_UPSCALE_NEEDLES) {
    if (hay.includes(needle)) score += 25;
  }
  if (hay.includes("turbo") || hay.includes("lightning")) score -= 10;
  return score;
}

/** Default Enhance checkpoint: SDXL realism checkpoint when installed. */
export function selectCuratedUpscaleModel(gallery: ModelGalleryItem[]): string {
  let best: ModelGalleryItem | undefined;
  let bestScore = -1;
  for (const item of gallery) {
    const score = scoreUpscaleGalleryItem(item);
    if (score > bestScore) {
      bestScore = score;
      best = item;
    }
  }
  return best?.engine_name ?? "";
}

export function upscaleModelWarning(
  item: ModelGalleryItem,
  mode: StudioMode,
): string | null {
  if (mode !== "upscale") return null;
  if (isUpscaleCompatibleModel(item)) return null;
  return `"${modelBasename(item.caption)}" is not a recommended SDXL checkpoint — Ultimate SD Upscale works best with SDXL models. You can still try it, but Z-Image / Ideogram / Flux routes may fail.`;
}

export function sortGalleryForUpscaleMode(
  gallery: ModelGalleryItem[],
  mode: StudioMode,
): ModelGalleryItem[] {
  if (mode !== "upscale") return gallery;
  return [...gallery].sort((a, b) => {
    const sa = scoreUpscaleGalleryItem(a);
    const sb = scoreUpscaleGalleryItem(b);
    if (sa !== sb) return sb - sa;
    return (a.caption ?? a.engine_name).localeCompare(b.caption ?? b.engine_name);
  });
}
