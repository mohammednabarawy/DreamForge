import type { StudioMode } from "./model-selection";
import { selectIdentityGenerateModel } from "./model-selection";
import { isIdentityPreservationActive } from "./identityPreserve";
import type { GenerationSettings, ModelGalleryItem } from "./tauri-api";

/**
 * Resolve the family the reference images will actually run through.
 *
 * Legacy Agent identity requests may still select Qwen. Generate keeps the
 * user's selected model, including when multiple references are attached.
 */
export function resolveReferenceModelFamily(
  settings: GenerationSettings,
  studioMode: StudioMode,
  gallery: ModelGalleryItem[],
  selectedFamily: string,
): string {
  if (selectedFamily === "krea2" && studioMode === "edit") return selectedFamily;
  if (["hidream_o1", "flux_kontext", "qwen_image_2.1", "minimax_h3_image"].includes(selectedFamily)) return selectedFamily;
  const routed = selectIdentityGenerateModel(gallery);
  if (routed?.family === "qwen_image_2.1") {
    const isKeepFace = studioMode === "agent" && isIdentityPreservationActive(settings);
    if (isKeepFace) {
      return "qwen_image_2.1";
    }
  }
  return selectedFamily;
}

/** Max reference images a resolved family supports (Qwen 2.1 supports up to 10; Krea 2 supports 2 in edit and 4 in generate). */
export function maxReferenceImagesForFamily(family: string, studioMode: StudioMode = "edit"): number {
  if (family === "minimax_h3_image") return 16;
  if (family === "krea2") return studioMode === "edit" ? 2 : 4;
  if (family === "qwen_image_2.1") return 10;
  if (family === "flux_kontext") return 4;
  return 4;
}
