import type { StudioMode } from "./model-selection";
import { selectIdentityGenerateModel } from "./model-selection";
import { coerceReferenceSlots, MAX_REFERENCE_SLOTS } from "./referenceSlots";
import { isIdentityPreservationActive } from "./identityPreserve";
import type { GenerationSettings, ModelGalleryItem } from "./tauri-api";

/** Qwen Edit Plus (TextEncodeQwenImageEditPlus) accepts at most 3 images. */
export const QWEN_EDIT_MAX_REFERENCES = 3;

/**
 * Roles that count as "an image the prompt can talk about" (image 1/2/3).
 * Structure (ControlNet) / upscale / inpaint slots are deliberate, separate
 * controls and never participate in multi-image compose.
 */
const COMPOSE_ROLES = new Set(["image_prompt", "restyle", "source_edit"]);

/** Number of attached images that act as compose references (image 1/2/3…). */
export function composeReferenceCount(
  settings: GenerationSettings,
  studioMode: StudioMode,
): number {
  return coerceReferenceSlots(settings, studioMode).filter((slot) =>
    COMPOSE_ROLES.has(slot.role),
  ).length;
}

/**
 * True when the job should be driven by Qwen/Kontext multi-image compose
 * (Qwen 2509-style: attach images, refer to "image 1/2/3" in the prompt).
 *
 * Mirrors how leading apps work — no per-image role picking required; the
 * prompt guides the model. Only triggers in Generate when 2+ plain images are
 * attached, there's no explicit structure (ControlNet) slot, and a
 * multi-image-capable edit model (Qwen / Kontext) is installed.
 */
export function multiImageComposeActive(
  settings: GenerationSettings,
  studioMode: StudioMode,
  gallery: ModelGalleryItem[],
): boolean {
  if (studioMode !== "generate" && studioMode !== "agent") return false;
  if (
    settings.vary_amount ||
    settings.enhance_target ||
    settings.enhance_auto_fix
  ) {
    return false;
  }
  const slots = coerceReferenceSlots(settings, studioMode);
  if (slots.some((slot) => slot.role === "structure")) return false;
  if (composeReferenceCount(settings, studioMode) < 2) return false;
  return Boolean(selectIdentityGenerateModel(gallery));
}

/**
 * Route 2+ attached images through Qwen/Kontext multi-image edit at submit.
 *
 * Reuses the identity pipeline (`applyIdentityAtSubmit`) by flagging identity
 * preservation, which switches to the installed Qwen/Kontext model, sets the
 * first image as the base, and forwards the remaining images as references the
 * prompt can address as "image 2", "image 3".
 */
export function applyMultiImageComposeAtSubmit(
  settings: GenerationSettings,
  studioMode: StudioMode,
  gallery: ModelGalleryItem[],
): GenerationSettings {
  if (isIdentityPreservationActive(settings)) return settings;
  if (!multiImageComposeActive(settings, studioMode, gallery)) return settings;
  return {
    ...settings,
    preserve_character: true,
    face_preservation: true,
    identity_mode:
      settings.identity_mode === "ipadapter_faceid"
        ? "ipadapter_faceid"
        : "preserve_face",
  };
}

/**
 * Resolve the family the reference images will actually run through.
 *
 * A Generate job can be authored against a Flux/SDXL model yet auto-route to a
 * Qwen edit model at submit (identity preserve or 2+ compose images). Callers
 * that gate reference counts or labels need that resolved family, not just the
 * model the user happened to pick.
 */
export function resolveReferenceModelFamily(
  settings: GenerationSettings,
  studioMode: StudioMode,
  gallery: ModelGalleryItem[],
  selectedFamily: string,
): string {
  if (selectedFamily === "krea2" && studioMode === "edit") return "krea2";
  if (selectedFamily === "qwen_image_edit") return "qwen_image_edit";
  const routed = selectIdentityGenerateModel(gallery);
  if (routed?.family === "qwen_image_edit") {
    const isKeepFace = isIdentityPreservationActive(settings);
    const composeCount = composeReferenceCount(settings, studioMode);
    if (isKeepFace || composeCount >= 2) {
      return "qwen_image_edit";
    }
  }
  return selectedFamily;
}

/** Max reference images a resolved family supports (Qwen Edit Plus caps at 3). */
export function maxReferenceImagesForFamily(family: string, studioMode: StudioMode = "edit"): number {
  if (family === "krea2" && studioMode === "edit") return 2;
  return family === "qwen_image_edit"
    ? QWEN_EDIT_MAX_REFERENCES
    : MAX_REFERENCE_SLOTS;
}
