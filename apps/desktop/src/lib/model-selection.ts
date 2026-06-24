import {
  selectCuratedEditModel,
} from "./editModel";
import { selectCuratedInpaintModel } from "./inpaintModel";
import { selectCuratedUpscaleModel } from "./upscaleModel";
import type { ModelGalleryItem } from "./tauri-api";

export type StyleRecipe = {
  id: string;
  models?: string[];
  thumbnail?: string;
  original_name?: string;
  styles?: string[];
  performance?: string;
  aspect_ratio?: string;
  prompt_prefix?: string;
  notes?: string;
};

export type StudioMode = "generate" | "edit" | "inpaint" | "upscale" | "agent" | "extract";

export function isEditFamilyMode(mode?: StudioMode): boolean {
  return mode === "edit" || mode === "inpaint" || mode === "upscale" || mode === "extract";
}

export function modelBasename(path: string | null | undefined): string {
  const safePath = path ?? "";
  const normalized = safePath.replace(/\\/g, "/");
  const parts = normalized.split("/");
  return parts[parts.length - 1] || safePath;
}

export function modelMatches(
  item: ModelGalleryItem,
  selected?: string | null,
): boolean {
  if (!selected) return false;
  const sel = selected.toLowerCase();
  const engine = (item.engine_name ?? "").toLowerCase();
  const caption = (item.caption ?? "").toLowerCase();
  const base = modelBasename(selected).toLowerCase();
  return (
    sel === engine ||
    sel === caption ||
    modelBasename(engine) === base ||
    modelBasename(caption) === base
  );
}

export function findGalleryModel(
  gallery: ModelGalleryItem[],
  candidate: string,
): ModelGalleryItem | undefined {
  const norm = candidate.toLowerCase();
  const base = modelBasename(candidate).toLowerCase();
  return gallery.find(
    (m) =>
      (m.engine_name ?? "").toLowerCase() === norm ||
      (m.caption ?? "").toLowerCase() === norm ||
      modelBasename(m.engine_name ?? "").toLowerCase() === base ||
      modelBasename(m.caption ?? "").toLowerCase() === base,
  );
}

export function pickStyleModel(
  gallery: ModelGalleryItem[],
  styleId: string | undefined,
  recipes: StyleRecipe[],
): string | undefined {
  if (!styleId || styleId === "none") return undefined;
  const recipe = recipes.find((r) => r.id === styleId);
  if (!recipe?.models?.length) return undefined;
  for (const candidate of recipe.models) {
    const hit = findGalleryModel(gallery, candidate);
    if (hit) return hit.engine_name;
  }
  return undefined;
}

/** @deprecated Use pickStyleModel */
export const pickUseCaseModel = pickStyleModel;

function galleryHaystack(item: ModelGalleryItem): string {
  return `${item.family} ${item.caption} ${item.engine_name} ${item.relative_path}`.toLowerCase();
}

function pickBestScoredGalleryItem(
  gallery: ModelGalleryItem[],
  scoreFn: (item: ModelGalleryItem) => number,
): ModelGalleryItem | undefined {
  let best: ModelGalleryItem | undefined;
  let bestScore = -1;
  for (const item of gallery) {
    const score = scoreFn(item);
    if (score > bestScore) {
      bestScore = score;
      best = item;
    }
  }
  return bestScore >= 0 ? best : undefined;
}

function scoreIdeogram4GalleryItem(item: ModelGalleryItem): number {
  const hay = galleryHaystack(item);
  const family = (item.family ?? "").toLowerCase();
  if (family !== "ideogram4" && !hay.includes("ideogram")) return -1;
  let score = 0;
  if (family === "ideogram4") score += 100;
  if (hay.includes("fp8")) score += 40;
  if (hay.includes("scaled")) score += 20;
  if (hay.includes("v4") || hay.includes("ideogram4")) score += 15;
  if (hay.includes("4")) score += 5;
  return score;
}

/** Prefer installed Ideogram 4 checkpoint (fp8 scaled when available). */
export function selectIdeogram4GalleryModel(
  gallery: ModelGalleryItem[],
): ModelGalleryItem | undefined {
  return pickBestScoredGalleryItem(gallery, scoreIdeogram4GalleryItem);
}

function ideogram4EngineName(gallery: ModelGalleryItem[]): string | undefined {
  return selectIdeogram4GalleryModel(gallery)?.engine_name;
}

export function resolveActiveModel(
  gallery: ModelGalleryItem[],
  current: string | undefined,
  styleId: string | undefined,
  recipes: StyleRecipe[],
  userPicked: boolean,
): string {
  if (userPicked && current && findGalleryModel(gallery, current)) {
    return findGalleryModel(gallery, current)!.engine_name;
  }
  const fromRecipe = pickStyleModel(gallery, styleId, recipes);
  if (fromRecipe) return fromRecipe;
  const ideogram = ideogram4EngineName(gallery);
  if (ideogram) return ideogram;
  if (current && findGalleryModel(gallery, current)) {
    return findGalleryModel(gallery, current)!.engine_name;
  }
  return gallery[0]?.engine_name ?? current ?? "";
}


export function selectCuratedModelForMode(
  mode: StudioMode,
  gallery: ModelGalleryItem[],
  current?: string,
): string {
  if (mode === "upscale") {
    return selectCuratedUpscaleModel(gallery) || current || gallery[0]?.engine_name || "";
  }
  const ideogram = ideogram4EngineName(gallery);
  if (mode === "generate" || mode === "agent") {
    return ideogram ?? current ?? gallery[0]?.engine_name ?? "";
  }
  if (mode === "inpaint") {
    return selectCuratedInpaintModel(gallery, current);
  }
  if (mode === "edit") {
    return selectCuratedEditModel(gallery);
  }
  return current ?? gallery[0]?.engine_name ?? "";
}

export type IdentityGenerateRoute = "kontext" | "qwen_edit" | "ipadapter" | "ipadapter_faceid";

export type IdentityGenerateModelPick = {
  engine_name: string;
  family: string;
  route: IdentityGenerateRoute;
};

/** Best local stack for generate-mode identity reference (photo → new scene, same face). */
export function selectIdentityGenerateModel(
  gallery: ModelGalleryItem[],
): IdentityGenerateModelPick | undefined {
  const kontextNeedles = [
    "flux1-dev-kontext_fp8_scaled",
    "flux1-dev-kontext",
    "kontext",
    "flux kontext",
  ];
  for (const needle of kontextNeedles) {
    const query = needle.toLowerCase();
    const hit = gallery.find((item) => galleryHaystack(item).includes(query));
    if (hit) {
      return {
        engine_name: hit.engine_name,
        family: hit.family ?? "flux_kontext",
        route: "kontext",
      };
    }
  }

  const qwenHit = gallery.find((item) => item.engine_name === selectCuratedEditModel(gallery));
  if (qwenHit) {
    return {
      engine_name: qwenHit.engine_name,
      family: qwenHit.family ?? "qwen_image_edit",
      route: "qwen_edit",
    };
  }

  return undefined;
}
