import type { ModelGalleryItem, ModelDependencyItem } from "./tauri-api";
import type { StudioMode } from "./model-selection";
import type { GenerateReferencePatchOptions } from "./referenceImage";
import {
  buildGenerateIdentityReferencePatch,
  buildImagePromptReferencePatch,
  buildRestyleReferencePatch,
} from "./referenceImage";
import { routeBadgeLabel } from "./referenceRole";
import type { GenerationSettings } from "./tauri-api";

function dependencyHaystack(items: ModelDependencyItem[]): string {
  return items
    .map((item) =>
      [
        item.id,
        item.filename,
        item.relative,
        item.url,
        item.expected_path,
      ]
        .filter(Boolean)
        .join(" "),
    )
    .join(" ")
    .toLowerCase();
}

/** True when IP-Adapter companion assets are not reported missing. */
export function ipAdapterAssetsReady(
  modelMissing: ModelDependencyItem[] = [],
  studioMissing: ModelDependencyItem[] = [],
  imagePromptMissing: ModelDependencyItem[] = [],
): boolean {
  const missingText = dependencyHaystack([
    ...modelMissing,
    ...studioMissing,
    ...imagePromptMissing,
  ]);
  const blockers = ["ipadapter", "ip-adapter", "clip_vision", "clip-vision"];
  return !blockers.some((token) => missingText.includes(token));
}

export function galleryHasIpAdapterStack(gallery: ModelGalleryItem[]): boolean {
  const haystack = gallery
    .map((item) =>
      [item.engine_name, item.relative_path, item.category, item.family]
        .filter(Boolean)
        .join(" "),
    )
    .join(" ")
    .toLowerCase();
  return haystack.includes("ipadapter") || haystack.includes("ip-adapter");
}

export function easyCreateReferenceRole(
  gallery: ModelGalleryItem[],
  modelMissing: ModelDependencyItem[] = [],
  studioMissing: ModelDependencyItem[] = [],
  imagePromptMissing: ModelDependencyItem[] = [],
): "image_prompt" | "restyle" {
  if (
    galleryHasIpAdapterStack(gallery) &&
    ipAdapterAssetsReady(modelMissing, studioMissing, imagePromptMissing)
  ) {
    return "image_prompt";
  }
  return "restyle";
}

/** Easy Create: opinionated reference attach without switching studio mode. */
export function buildEasyCreateReferencePatch(
  path: string,
  gallery: ModelGalleryItem[],
  outputFor: (suffix: string) => string,
  options: GenerateReferencePatchOptions & {
    ipAdapterReady?: boolean;
    modelMissing?: ModelDependencyItem[];
    studioMissing?: ModelDependencyItem[];
    imagePromptMissing?: ModelDependencyItem[];
  } = {},
): Partial<GenerationSettings> {
  const role =
    options.ipAdapterReady === true
      ? "image_prompt"
      : options.ipAdapterReady === false
        ? "restyle"
        : easyCreateReferenceRole(
            gallery,
            options.modelMissing,
            options.studioMissing,
            options.imagePromptMissing,
          );

  const shared = {
    upscale_image: undefined,
    inpaint_mask_path: undefined,
    preserve_character: true,
    style: "none" as const,
    output: outputFor("gen"),
  };

  if (role === "image_prompt") {
    return {
      ...buildImagePromptReferencePatch(path, outputFor),
      ...shared,
      model: options.userPickedModel ? options.currentModel?.trim() : undefined,
    };
  }

  if (options.userPickedModel && options.currentModel?.trim()) {
    return {
      ...buildRestyleReferencePatch(path, shared, options.modelFamily),
      model: options.currentModel.trim(),
      workflow_mode: "generate",
    };
  }

  return {
    ...buildGenerateIdentityReferencePatch(path, gallery, outputFor, options),
    reference_role: "restyle",
    workflow_mode: "generate",
  };
}

export function easyRouteSummary(
  settings: GenerationSettings,
  studioMode: StudioMode,
  modelFamily?: string,
  activeModelLabel?: string,
): string {
  const badge = routeBadgeLabel(settings, studioMode, modelFamily);
  if (badge) return badge;

  switch (studioMode) {
    case "generate":
      return activeModelLabel?.trim()
        ? `Creating with ${activeModelLabel}`
        : "Create from your prompt";
    case "edit":
      return "Describe what should change";
    case "inpaint":
      return settings.inpaint_mask_path?.trim()
        ? "Fix the painted region"
        : "Paint a region to fix";
    case "upscale":
      return "Enhance image resolution";
    case "extract":
      return "Extract structure from image";
    default:
      return "";
  }
}
