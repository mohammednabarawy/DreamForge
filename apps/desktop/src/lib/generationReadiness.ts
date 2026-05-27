import type { GenerationSettings } from "./tauri-api";
import { generationNeedsReferenceImage } from "./parseAgentPrompt";
import type { ModelGalleryItem } from "./tauri-api";
import type { StudioMode } from "./model-selection";

export function vramProfileFromHardware(
  vramGb: number | null,
  mpsAvailable: boolean | null,
): "16gb" | "8gb" | "5gb" {
  if (mpsAvailable) return "8gb";
  if (vramGb == null) return "16gb";
  if (vramGb >= 14) return "16gb";
  if (vramGb >= 9) return "8gb";
  return "5gb";
}

export type GenerateReadiness = {
  ok: boolean;
  reason: string;
  /** True when Generate is blocked only because companion files are missing. */
  missingCompanions: boolean;
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
}): GenerateReadiness {
  if (args.generating) {
    return { ok: false, reason: "Generation in progress", missingCompanions: false };
  }
  if (!args.workerReady) {
    return {
      ok: false,
      reason: args.engineLabel || "GPU engine is still loading",
      missingCompanions: false,
    };
  }
  if (!(args.prompt ?? "").trim()) {
    return { ok: false, reason: "Enter a prompt first", missingCompanions: false };
  }
  if (!(args.model ?? "").trim()) {
    return { ok: false, reason: "Select a base model", missingCompanions: false };
  }
  const studioMissing = args.studioMissingAssetCount ?? 0;
  if (studioMissing > 0) {
    return {
      ok: false,
      missingCompanions: true,
      reason: `Missing ${studioMissing} studio asset(s) (models folder) — Download first`,
    };
  }
  const studio = args.studioMode ?? "generate";
  if (
    studio === "upscale" &&
    !Boolean((args.settings.upscale_image ?? "").trim()) &&
    !Boolean((args.settings.input_image ?? "").trim())
  ) {
    return {
      ok: false,
      reason: "Attach an image to upscale (canvas output or reference)",
      missingCompanions: false,
    };
  }
  if (
    args.settings.edit_type === "inpaint" &&
    Boolean((args.settings.input_image ?? "").trim()) &&
    !Boolean((args.settings.inpaint_mask_path ?? "").trim())
  ) {
    return {
      ok: false,
      reason: "Create or attach an inpaint mask first",
      missingCompanions: false,
    };
  }
  if (!args.modelDependenciesReady) {
    const n = args.missingCompanionCount;
    return {
      ok: false,
      missingCompanions: n > 0,
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
    };
  }
  return { ok: true, reason: "", missingCompanions: false };
}
