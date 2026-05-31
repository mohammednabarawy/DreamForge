import type { GenerationSettings } from "./tauri-api";
import { readImagePreview } from "./tauri-api";

export const DREAMFORGE_IMAGE_PATH_MIME = "application/x-dreamforge-image-path";

export type ReferenceImageMode = "reference" | "inpaint" | "upscale";

export const UPSCALE_METHOD_LABELS: Record<string, string> = {
  fast_2x: "Fast 2x (OmniSR)",
  fast_3x: "Fast 3x (OmniSR)",
  fast_4x: "Fast 4x (OmniSR)",
  quality: "High quality 4x (HAT)",
  sharp: "Sharper 4x",
  default: "Quality 4x (NMKD)",
  "2x": "Fast 2x (OmniSR)",
  "4x": "Quality 4x (NMKD)",
};

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

export function upscaleMethodLabel(method: string | undefined): string {
  const key = (method ?? "fast_2x").trim();
  return UPSCALE_METHOD_LABELS[key] ?? key;
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
      inpaint_mask_path: undefined,
      edit_type: "auto",
      cn_selection: "Custom...",
      cn_type: "upscale",
      upscale_method: "fast_2x",
      style: "image_edit",
      output: outputFor("upscale"),
    };
  }

  if (mode === "inpaint") {
    return {
      input_image: path,
      upscale_image: undefined,
      inpaint_mask_path: undefined,
      edit_type: "inpaint",
      cn_selection: "Custom...",
      cn_type: "inpaint",
      style: "image_edit",
      output: outputFor("inpaint"),
    };
  }

  return {
    input_image: path,
    upscale_image: undefined,
    inpaint_mask_path: undefined,
    edit_type: "kontext",
    cn_selection: "None",
    cn_type: "None",
    style: "image_edit",
    output: outputFor("edit"),
  };
}

export function buildClearReferenceImagePatch(): Partial<GenerationSettings> {
  return {
    input_image: undefined,
    upscale_image: undefined,
    reference_images: undefined,
    inpaint_mask_path: undefined,
    cn_selection: "None",
    cn_type: "None",
    edit_type: "auto",
    upscale_method: undefined,
    // Return to text-to-image defaults so a cleared reference does not keep edit routing.
    style: "none",
  };
}

/** Append a Kontext/control reference (Krita multi-reference; not the main edit image). */
export function appendExtraReferencePath(
  settings: GenerationSettings,
  path: string,
): Partial<GenerationSettings> {
  const normalized = path.trim();
  if (!normalized) return {};
  const main = (settings.input_image ?? "").trim();
  if (main && main === normalized) return {};
  const current = [...(settings.reference_images ?? [])];
  if (current.some((item) => item.trim() === normalized)) return {};
  return { reference_images: [...current, normalized] };
}

export function removeExtraReferenceAt(
  settings: GenerationSettings,
  index: number,
): Partial<GenerationSettings> {
  const current = [...(settings.reference_images ?? [])];
  if (index < 0 || index >= current.length) return {};
  current.splice(index, 1);
  return { reference_images: current.length ? current : undefined };
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
  if (next.reference_images?.length) {
    next.reference_images = await Promise.all(
      next.reference_images.map((path) => resolveReferenceImagePath(path)),
    );
  }
  return next;
}

/** Optimal default edit strength for reference / inpaint workflows (Krita-aligned). */
export function defaultReferenceEditStrength(
  settings: GenerationSettings,
  modelFamily?: string,
): number {
  const family = (modelFamily ?? "").toLowerCase();
  if (family === "qwen_image_edit") return 1.0;
  if (settings.edit_type === "inpaint") return 0.9;
  return 0.98;
}

export function effectiveReferenceEditStrength(
  settings: GenerationSettings,
  modelFamily?: string,
): number {
  const value = settings.edit_strength;
  if (value != null && value > 0) return value;
  return defaultReferenceEditStrength(settings, modelFamily);
}
