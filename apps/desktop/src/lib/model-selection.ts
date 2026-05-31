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

export type StudioMode = "generate" | "edit" | "inpaint" | "upscale" | "agent";

export function isEditFamilyMode(mode?: StudioMode): boolean {
  return mode === "edit" || mode === "inpaint" || mode === "upscale";
}

export function modelBasename(path: string): string {
  const normalized = path.replace(/\\/g, "/");
  const parts = normalized.split("/");
  return parts[parts.length - 1] || path;
}

export function modelMatches(
  item: ModelGalleryItem,
  selected?: string | null,
): boolean {
  if (!selected) return false;
  const sel = selected.toLowerCase();
  const engine = item.engine_name.toLowerCase();
  const caption = item.caption.toLowerCase();
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
      m.engine_name.toLowerCase() === norm ||
      m.caption.toLowerCase() === norm ||
      modelBasename(m.engine_name).toLowerCase() === base ||
      modelBasename(m.caption).toLowerCase() === base,
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
  if (mode === "generate" || mode === "agent") return current ?? "";
  const candidates =
    mode === "inpaint"
      ? ["flux1-fill", "flux fill", "flux.1-fill", "flux1-dev", "fill", "inpaint"]
      : mode === "edit"
        ? [
            "flux1-dev-kontext_fp8_scaled",
            "flux1-dev-kontext",
            "kontext",
            "flux kontext",
            "qwen image edit",
            "qwen_edit",
            "qwen edit",
          ]
        : ["upscale", "omnisr", "nmkd", "supir", "esrgan", "real-esrgan", "real esrgan"];
  for (const needle of candidates) {
    const hit = gallery.find((item) => {
      const hay =
        `${item.family} ${item.caption} ${item.engine_name} ${item.relative_path}`.toLowerCase();
      return hay.includes(needle);
    });
    if (hit) return hit.engine_name;
  }
  return current ?? gallery[0]?.engine_name ?? "";
}
