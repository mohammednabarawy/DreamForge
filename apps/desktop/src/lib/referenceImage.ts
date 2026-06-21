import type { GenerationSettings, ModelGalleryItem } from "./tauri-api";
import { readImagePreview } from "./tauri-api";
import {
  isEditFamilyMode,
  selectIdentityGenerateModel,
  type StudioMode,
} from "./model-selection";
import { qwenEdit2511LightningPatch } from "./qwenEditDefaults";

export const DREAMFORGE_IMAGE_PATH_MIME = "application/x-dreamforge-image-path";

export type ReferenceImageMode = "reference" | "inpaint" | "upscale";

export const UPSCALE_METHOD_LABELS: Record<string, string> = {
  ultimate_sd_upscale: "Ultimate SD Upscale",
  default: "Ultimate SD Upscale",
  pid_flux1_4k: "Ultimate SD Upscale",
  pid_flux1_4k_bf16: "Ultimate SD Upscale",
  pid_flux1_4k_mxfp8: "Ultimate SD Upscale",
  fast_2x: "Ultimate SD Upscale",
  fast_3x: "Ultimate SD Upscale",
  fast_4x: "Ultimate SD Upscale",
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
    label: "Upscale 4K",
    short: "4K",
    description: "Upscale the attached image",
  },
];

export function basename(path: string | undefined | null): string {
  const value = typeof path === "string" ? path : "";
  const normalized = value.replace(/\\/g, "/");
  const parts = normalized.split("/");
  return parts[parts.length - 1] || value;
}

export function activeReferencePath(
  settings: GenerationSettings,
): string | undefined {
  return (
    settings.input_image?.trim() ||
    settings.upscale_image?.trim() ||
    settings.reference_image?.trim() ||
    settings.reference_images?.find((item) => item.trim())?.trim() ||
    undefined
  );
}

export function activeReferenceMode(
  settings: GenerationSettings,
): ReferenceImageMode {
  if (settings.upscale_image?.trim()) return "upscale";
  if (settings.edit_type === "inpaint") return "inpaint";
  return "reference";
}

export function upscaleMethodLabel(method: string | undefined): string {
  const key = (method ?? "ultimate_sd_upscale").trim();
  return UPSCALE_METHOD_LABELS[key] ?? key;
}

export function buildReferenceImagePatch(
  path: string,
  mode: ReferenceImageMode,
  outputFor: (suffix: string) => string,
  modelFamily?: string,
): Partial<GenerationSettings> {
  const imagePath = typeof path === "string" ? path : "";
  if (mode === "upscale") {
    return {
      upscale_image: imagePath,
      input_image: undefined,
      inpaint_mask_path: undefined,
      edit_type: "auto",
      cn_selection: "Custom...",
      cn_type: "upscale",
      upscale_method: "ultimate_sd_upscale",
      style: "image_edit",
      output: outputFor("upscale"),
    };
  }

  if (mode === "inpaint") {
    return {
      input_image: imagePath,
      upscale_image: undefined,
      inpaint_mask_path: undefined,
      edit_type: "inpaint",
      cn_selection: "Custom...",
      cn_type: "inpaint",
      style: "image_edit",
      output: outputFor("inpaint"),
    };
  }

  if (modelFamily === "qwen_image_edit") {
    return {
      input_image: imagePath,
      upscale_image: undefined,
      inpaint_mask_path: undefined,
      ...qwenEdit2511LightningPatch(),
      output: outputFor("edit"),
    };
  }

  if (modelFamily === "flux_kontext") {
    return {
      input_image: imagePath,
      upscale_image: undefined,
      inpaint_mask_path: undefined,
      edit_type: "kontext",
      edit_strength: 1.0,
      cn_selection: "None",
      cn_type: "None",
      steps: 20,
      style: "image_edit",
      output: outputFor("edit"),
    };
  }

  return {
    input_image: imagePath,
    upscale_image: undefined,
    inpaint_mask_path: undefined,
    edit_type: "auto",
    edit_strength: 0.75,
    cn_selection: "Custom...",
    cn_type: "img2img",
    style: "image_edit",
    output: outputFor("edit"),
  };
}

/** Generate tab: reference photo → new scene with preserved face/identity. */
export function buildGenerateIdentityReferencePatch(
  path: string,
  gallery: ModelGalleryItem[],
  outputFor: (suffix: string) => string,
): Partial<GenerationSettings> {
  const imagePath = typeof path === "string" ? path : "";
  const routed = selectIdentityGenerateModel(gallery);
  const shared: Partial<GenerationSettings> = {
    upscale_image: undefined,
    inpaint_mask_path: undefined,
    face_preservation: true,
    identity_mode: "faceid",
    preserve_character: true,
    workflow_mode: "generate",
    style: "none",
    output: outputFor("gen"),
  };

  if (!routed) {
    return {
      ...shared,
      input_image: imagePath,
      reference_image: imagePath,
      reference_images: [imagePath],
      cn_selection: "Custom...",
      cn_type: "reference",
    };
  }

  if (routed.route === "kontext") {
    return {
      ...shared,
      model: routed.engine_name,
      input_image: imagePath,
      reference_image: imagePath,
      edit_type: "kontext",
      edit_strength: 0.92,
      cn_selection: "None",
      cn_type: "None",
      steps: 20,
    };
  }

  if (routed.route === "qwen_edit") {
    return {
      ...shared,
      model: routed.engine_name,
      input_image: imagePath,
      reference_image: imagePath,
      ...qwenEdit2511LightningPatch(),
      edit_type: "qwen_edit",
      edit_strength: 1.0,
      cn_selection: "None",
      cn_type: "None",
    };
  }

  if (routed.route === "ipadapter") {
    return {
      ...shared,
      model: routed.engine_name,
      reference_image: imagePath,
      reference_images: [imagePath],
      input_image: undefined,
      cn_selection: "Custom...",
      cn_type: "reference",
    };
  }

  return shared;
}

export function buildClearReferenceImagePatch(): Partial<GenerationSettings> {
  return {
    input_image: undefined,
    upscale_image: undefined,
    reference_image: undefined,
    reference_images: undefined,
    inpaint_mask_path: undefined,
    cn_selection: "None",
    cn_type: "None",
    edit_type: "auto",
    upscale_method: undefined,
    face_preservation: undefined,
    identity_mode: undefined,
    preserve_character: undefined,
    workflow_mode: undefined,
    // Return to text-to-image defaults so a cleared reference does not keep edit routing.
    style: "none",
  };
}

/** Append a Kontext/control reference (Krita multi-reference; not the main edit image). */
export function appendExtraReferencePath(
  settings: GenerationSettings,
  path: string,
): Partial<GenerationSettings> {
  const normalized = typeof path === "string" ? path.trim() : "";
  if (!normalized) return {};
  const main = activeReferencePath(settings) ?? "";
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

/** Same-window drag fallback — Tauri/WebView often omits custom MIME until drop. */
const DRAG_SESSION_KEY = "dreamforge:image-drag-path";
let draggingImagePath: string | null = null;
let clearDragTimer: ReturnType<typeof setTimeout> | null = null;

function persistDraggingImagePath(path: string | null) {
  draggingImagePath = path;
  try {
    if (path) {
      window.sessionStorage.setItem(DRAG_SESSION_KEY, path);
    } else {
      window.sessionStorage.removeItem(DRAG_SESSION_KEY);
    }
  } catch {
    // Session storage is only a convenience fallback for embedded WebViews.
  }
}

export function cancelScheduledClearImagePathDragSession() {
  if (clearDragTimer) {
    clearTimeout(clearDragTimer);
    clearDragTimer = null;
  }
}

/** Defer clearing so drop handlers run before dragend in Tauri/WebView2. */
export function scheduleClearImagePathDragSession(delayMs = 200) {
  cancelScheduledClearImagePathDragSession();
  clearDragTimer = setTimeout(() => {
    clearDragTimer = null;
    clearImagePathDragSession();
  }, delayMs);
}

export function getDraggingImagePath(): string | null {
  if (draggingImagePath) return draggingImagePath;
  try {
    return normalizeImagePath(
      window.sessionStorage.getItem(DRAG_SESSION_KEY) ?? "",
    );
  } catch {
    return null;
  }
}

export function primeImagePathDragSession(path: string) {
  cancelScheduledClearImagePathDragSession();
  const normalized = normalizeImagePath(path) ?? path.trim();
  persistDraggingImagePath(normalized || null);
}

export function clearImagePathDragSession() {
  cancelScheduledClearImagePathDragSession();
  persistDraggingImagePath(null);
}

function normalizeImagePath(path: string): string | null {
  let trimmed = path.trim();
  if (!trimmed) return null;
  const uriLine = trimmed
    .split(/\r?\n/)
    .map((line) => line.trim())
    .find((line) => line && !line.startsWith("#"));
  if (uriLine) trimmed = uriLine;
  trimmed = trimmed.replace(/^["']|["']$/g, "");
  if (/^file:\/\//i.test(trimmed)) {
    try {
      trimmed = decodeURIComponent(new URL(trimmed).pathname);
      if (/^\/[A-Za-z]:\//.test(trimmed)) trimmed = trimmed.slice(1);
      trimmed = trimmed.replace(/\//g, "\\");
    } catch {
      trimmed = trimmed.replace(/^file:\/\/\/?/i, "");
    }
  }
  if (/\.(png|jpe?g|webp|bmp|gif|tif{1,2})$/i.test(trimmed)) {
    return trimmed;
  }
  return null;
}

export function setImagePathDragData(dataTransfer: DataTransfer, path: string) {
  const value = typeof path === "string" ? path : "";
  primeImagePathDragSession(value);
  dataTransfer.effectAllowed = "copy";
  try {
    dataTransfer.setData(DREAMFORGE_IMAGE_PATH_MIME, value);
  } catch {
    // WebView hosts may reject custom MIME during native drags.
  }
  try {
    dataTransfer.setData("text/plain", value);
  } catch {
    // Keep the module-level fallback alive even if the platform rejects text.
  }
  try {
    const uri =
      value && /^[A-Za-z]:[\\/]/.test(value)
        ? `file:///${value.replace(/\\/g, "/").replace(/ /g, "%20")}`
        : value;
    dataTransfer.setData("text/uri-list", uri);
  } catch {
    // Some hosts reject uri-list for local paths.
  }
}

export function canAcceptImagePathDrag(dataTransfer: DataTransfer): boolean {
  if (getDraggingImagePath()) return true;
  const types = Array.from(dataTransfer.types ?? []);
  return (
    types.includes(DREAMFORGE_IMAGE_PATH_MIME) ||
    types.includes("text/plain") ||
    types.includes("text/uri-list") ||
    types.includes("Files")
  );
}

export function readImagePathFromDrop(
  dataTransfer: DataTransfer,
): string | null {
  cancelScheduledClearImagePathDragSession();
  const formats = [DREAMFORGE_IMAGE_PATH_MIME, "text/plain", "text/uri-list"];
  for (const format of formats) {
    const normalized = normalizeImagePath(dataTransfer.getData(format));
    if (normalized) {
      clearImagePathDragSession();
      return normalized;
    }
  }
  for (const file of Array.from(dataTransfer.files ?? [])) {
    const path = (file as File & { path?: string }).path ?? file.name;
    const normalized = normalizeImagePath(path);
    if (normalized) {
      clearImagePathDragSession();
      return normalized;
    }
  }
  const fromSession = getDraggingImagePath();
  clearImagePathDragSession();
  return fromSession;
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
  const trimmed = typeof path === "string" ? path.trim() : "";
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

/** Drop cross-mode image fields so Kontext edit never reads a stale upscale path. */
export function sanitizeEditFamilySettings(
  settings: GenerationSettings,
  studioMode: StudioMode,
): GenerationSettings {
  if (!isEditFamilyMode(studioMode)) return settings;
  const next = { ...settings };
  if (studioMode === "upscale") {
    next.input_image = undefined;
    next.inpaint_mask_path = undefined;
    return next;
  }
  next.upscale_image = undefined;
  if (studioMode === "edit") {
    next.inpaint_mask_path = undefined;
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
