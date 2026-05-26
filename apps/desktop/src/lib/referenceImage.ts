import type { GenerationSettings } from "./tauri-api";
import { readImagePreview } from "./tauri-api";

export const DREAMFORGE_IMAGE_PATH_MIME = "application/x-dreamforge-image-path";

export type ReferenceImageMode = "reference" | "inpaint" | "upscale";

export const REFERENCE_IMAGE_MODES: Array<{
  id: ReferenceImageMode;
  label: string;
  short: string;
  description: string;
}> = [
  {
    id: "reference",
    label: "Reference / edit",
    short: "Ref",
    description: "Identity or Kontext-style image editing",
  },
  {
    id: "inpaint",
    label: "Inpaint",
    short: "Inpaint",
    description: "Localized edits and inpaint guidance",
  },
  {
    id: "upscale",
    label: "Upscale 2×",
    short: "2×",
    description: "Upscale the attached image",
  },
];

export function basename(path: string): string {
  const normalized = path.replace(/\\/g, "/");
  const parts = normalized.split("/");
  return parts[parts.length - 1] || path;
}

export function activeReferencePath(
  settings: GenerationSettings,
): string | undefined {
  return (settings.input_image ?? settings.upscale_image ?? "").trim() || undefined;
}

export function activeReferenceMode(
  settings: GenerationSettings,
): ReferenceImageMode {
  if (settings.upscale_image?.trim()) return "upscale";
  if (settings.edit_type === "inpaint") return "inpaint";
  return "reference";
}

export function buildReferenceImagePatch(
  path: string,
  mode: ReferenceImageMode,
  outputFor: (suffix: string) => string,
): Partial<GenerationSettings> {
  if (mode === "upscale") {
    return {
      upscale_image: path,
      input_image: undefined,
      edit_type: "auto",
      cn_selection: "Custom...",
      cn_type: "upscale",
      upscale_method: "2x",
      use_case: "image_edit",
      output: outputFor("upscale"),
    };
  }

  if (mode === "inpaint") {
    return {
      input_image: path,
      upscale_image: undefined,
      edit_type: "inpaint",
      cn_selection: "Custom...",
      cn_type: "inpaint",
      use_case: "image_edit",
      output: outputFor("inpaint"),
    };
  }

  return {
    input_image: path,
    upscale_image: undefined,
    edit_type: "kontext",
    cn_selection: "None",
    cn_type: "None",
    use_case: "image_edit",
    output: outputFor("edit"),
  };
}

export function buildClearReferenceImagePatch(): Partial<GenerationSettings> {
  return {
    input_image: undefined,
    upscale_image: undefined,
    inpaint_mask_path: undefined,
    cn_selection: "None",
    cn_type: "None",
    edit_type: "auto",
    upscale_method: undefined,
    // Return to text-to-image defaults so a cleared reference does not keep edit routing.
    use_case: "none",
  };
}

export function setImagePathDragData(dataTransfer: DataTransfer, path: string) {
  dataTransfer.setData(DREAMFORGE_IMAGE_PATH_MIME, path);
  dataTransfer.setData("text/plain", path);
  dataTransfer.effectAllowed = "copy";
}

export function readImagePathFromDrop(
  dataTransfer: DataTransfer,
): string | null {
  const path =
    dataTransfer.getData(DREAMFORGE_IMAGE_PATH_MIME) ||
    dataTransfer.getData("text/plain");
  const trimmed = path.trim();
  if (!trimmed) return null;
  if (/\.(png|jpe?g|webp|bmp|gif|tif{1,2})$/i.test(trimmed)) {
    return trimmed;
  }
  return null;
}

export function referenceStatusLabel(
  mode: ReferenceImageMode,
  path: string,
): string {
  const modeLabel =
    REFERENCE_IMAGE_MODES.find((item) => item.id === mode)?.short ?? "Ref";
  return `${modeLabel}: ${basename(path)}`;
}

/** Resolve to the canonical on-disk path (matches Tauri preview + Python loader). */
export async function resolveReferenceImagePath(path: string): Promise<string> {
  const trimmed = path.trim();
  if (!trimmed) return trimmed;
  try {
    const preview = await readImagePreview(trimmed);
    return preview.path?.trim() || trimmed;
  } catch {
    return trimmed;
  }
}

export async function resolveGenerationImagePaths(
  settings: GenerationSettings,
): Promise<GenerationSettings> {
  const next = { ...settings };
  if (next.input_image?.trim()) {
    next.input_image = await resolveReferenceImagePath(next.input_image);
  }
  if (next.upscale_image?.trim()) {
    next.upscale_image = await resolveReferenceImagePath(next.upscale_image);
  }
  if (next.inpaint_mask_path?.trim()) {
    next.inpaint_mask_path = await resolveReferenceImagePath(
      next.inpaint_mask_path,
    );
  }
  return next;
}
