import type { GenerationSettings } from "./tauri-api";
import { generationNeedsReferenceImage } from "./parseAgentPrompt";
import type { ModelGalleryItem } from "./tauri-api";
import type { EditFamilyPlanState } from "./workflowPlanActions";
import { isEditFamilyMode, type StudioMode } from "./model-selection";
import { isFluxFillModel, selectFluxFillModel } from "./inpaintModel";
import { vramProfileFromHardware } from "./vramProfiles";

export { isEditFamilyMode, vramProfileFromHardware };
export type { EditFamilyPlanState };

export type GenerateReadiness = {
  ok: boolean;
  reason: string;
  /** True when Generate is blocked only because companion/studio assets are missing. */
  missingCompanions: boolean;
  companionBlockedOnly: boolean;
};

export function computeGenerateReadiness(args: {
  workerReady: boolean;
  generating: boolean;
  engineState: string;
  engineLabel: string;
  prompt: string;
  model: string;
  modelDependenciesReady: boolean;
  missingCompanionCount: number;
  /** Upscalers, inpaint bundles, FLUX Kontext checkpoints (studio bridge). */
  studioMissingAssetCount?: number;
  settings: GenerationSettings;
  modelGallery: ModelGalleryItem[];
  studioMode?: StudioMode;
  editPlanState?: EditFamilyPlanState;
}): GenerateReadiness {
  if (args.generating) {
    return { ok: false, reason: "Generation in progress", missingCompanions: false, companionBlockedOnly: false };
  }
  if (!args.workerReady) {
    return {
      ok: false,
      reason: args.engineLabel?.includes("ComfyUI")
        ? args.engineLabel
        : args.engineState === "booting" || args.engineState === "restarting"
          ? "ComfyUI server is still starting — wait for the engine to finish loading"
          : args.engineLabel || "GPU engine is still loading",
      missingCompanions: false,
      companionBlockedOnly: false,
    };
  }
  const studio = args.studioMode ?? "generate";
  if (!(args.prompt ?? "").trim() && studio !== "upscale") {
    return { ok: false, reason: "Enter a prompt first", missingCompanions: false, companionBlockedOnly: false };
  }
  if (!(args.model ?? "").trim()) {
    return { ok: false, reason: "Select a base model", missingCompanions: false, companionBlockedOnly: false };
  }
  const studioMissing = args.studioMissingAssetCount ?? 0;
  if (studioMissing > 0) {
    return {
      ok: false,
      missingCompanions: true,
      companionBlockedOnly: true,
      reason: `Missing ${studioMissing} studio asset(s) (models folder) — Download first`,
    };
  }
  const hasEditImage = Boolean((args.settings.input_image ?? "").trim());
  const hasUpscaleImage = Boolean((args.settings.upscale_image ?? "").trim());
  const hasInpaintMask = Boolean((args.settings.inpaint_mask_path ?? "").trim());
  if (studio === "edit" && !hasEditImage) {
    return {
      ok: false,
      reason: "Attach an image to edit (canvas output or reference)",
      missingCompanions: false,
      companionBlockedOnly: false,
    };
  }
  if (studio === "inpaint" && !hasEditImage) {
    return {
      ok: false,
      reason: "Attach an image before creating an inpaint mask",
      missingCompanions: false,
      companionBlockedOnly: false,
    };
  }
  if (studio === "inpaint" && !hasInpaintMask) {
    return {
      ok: false,
      reason: "Create or attach an inpaint mask first",
      missingCompanions: false,
      companionBlockedOnly: false,
    };
  }
  if (studio === "inpaint") {
    const modelItem = args.modelGallery.find((item) => item.engine_name === args.model);
    if (!modelItem || !isFluxFillModel(modelItem)) {
      const flux = selectFluxFillModel(args.modelGallery);
      return {
        ok: false,
        missingCompanions: !flux,
        companionBlockedOnly: !flux,
        reason: flux
          ? "Inpaint requires Flux Fill — reselect Inpaint mode or pick a Fill checkpoint"
          : "Flux Fill is missing — approve the asset download prompt before inpainting",
      };
    }
  }
  if (
    studio === "upscale" &&
    !hasUpscaleImage &&
    !hasEditImage
  ) {
    return {
      ok: false,
      reason: "Attach an image to upscale (canvas output or reference)",
      missingCompanions: false,
      companionBlockedOnly: false,
    };
  }
  if (args.settings.edit_type === "inpaint" && hasEditImage && !hasInpaintMask) {
    if (studio === "inpaint" || studio === "edit") {
      return {
        ok: false,
        reason: "Create or attach an inpaint mask first",
        missingCompanions: false,
        companionBlockedOnly: false,
      };
    }
  }
  if (studio !== "upscale" && !args.modelDependenciesReady) {
    const n = args.missingCompanionCount;
    return {
      ok: false,
      missingCompanions: n > 0,
      companionBlockedOnly: n > 0,
      reason:
        n > 0
          ? `Missing ${n} companion file(s)`
          : "Model dependencies not ready",
    };
  }
  if (generationNeedsReferenceImage(args.settings, args.modelGallery)) {
    return {
      ok: false,
      reason: "Attach a reference image or pick a text-to-image model",
      missingCompanions: false,
      companionBlockedOnly: false,
    };
  }
  if (args.editPlanState === "not_ready") {
    return {
      ok: false,
      reason: "Resolve missing inputs in Settings, then Generate again",
      missingCompanions: false,
      companionBlockedOnly: false,
    };
  }
  return { ok: true, reason: "", missingCompanions: false, companionBlockedOnly: false };
}
