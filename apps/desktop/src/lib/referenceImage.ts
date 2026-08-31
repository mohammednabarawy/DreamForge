import type { GenerationSettings } from "./tauri-api";
import { readImagePreview } from "./tauri-api";
import type { StudioMode } from "./model-selection";
import { sanitizeSettingsForStudioMode } from "./routeResolution";
import { referenceRoleFromAttach, type ReferenceRole } from "./referenceRole";
import { qwenEdit2511LightningPatch } from "./qwenEditDefaults";

export const DREAMFORGE_IMAGE_PATH_MIME = "application/x-dreamforge-image-path";

export type ReferenceImageMode = "reference" | "inpaint" | "upscale";

export const UPSCALE_METHOD_LABELS: Record<string, string> = {
  ultimate_sd_upscale: "Ultimate SD Upscale",
  default: "Ultimate SD Upscale",
  pid_flux1_4k: "PiD 4K (mxfp8)",
  pid_flux1_4k_bf16: "PiD 4K (bf16)",
  pid_flux1_4k_mxfp8: "PiD 4K (mxfp8)",
  fast_2x: "Fast 2× (OmniSR)",
  fast_3x: "Fast 3× (OmniSR)",
  fast_4x: "Fast 4× (OmniSR)",
  quality: "High quality 4× (HAT)",
  sharp: "Sharper 4×",
};

/** How an attached image is routed — derived from the active studio tab, not a manual picker. */
export function referenceModeForStudio(studioMode: StudioMode): ReferenceImageMode {
  if (studioMode === "inpaint") return "inpaint";
  if (studioMode === "upscale") return "upscale";
  return "reference";
}

export function referencePanelTitle(studioMode: StudioMode, compact = false): string {
  if (compact) return "References";
  if (studioMode === "inpaint") return "Inpaint source";
  if (studioMode === "upscale") return "Enhance source";
  if (studioMode === "edit") return "Edit source";
  return "References";
}

export function referencePanelSubtitle(studioMode: StudioMode): string {
  if (studioMode === "inpaint") {
    return "Source image for masked edits — paint the region on the canvas";
  }
  if (studioMode === "upscale") return "Image to upscale or restore";
  if (studioMode === "edit") {
    return "Source and extra references use the selected edit model (Krea 2, Kontext, Qwen, img2img)";
  }
  return "Attach references — routing follows model and role (image prompt, restyle, structure)";
}

export function referenceAttachedLabel(
  studioMode: StudioMode,
  settings: GenerationSettings,
): string {
  if (studioMode === "inpaint") return "Inpaint source";
  if (studioMode === "upscale") {
    return `Upscale — ${upscaleMethodLabel(settings.upscale_method)}`;
  }
  if (studioMode === "edit") return "Edit source";
  return "Reference";
}

export function basename(path: string | undefined | null): string {
  const value = typeof path === "string" ? path : "";
  const normalized = value.replace(/\\/g, "/");
  const parts = normalized.split("/");
  return parts[parts.length - 1] || value;
}

export function activeReferencePath(
  settings: GenerationSettings,
  studioMode: StudioMode = "generate",
): string | undefined {
  if (studioMode === "upscale") {
    return (
      settings.upscale_image?.trim() ||
      settings.input_image?.trim() ||
      undefined
    );
  }
  if (studioMode === "inpaint" || studioMode === "edit") {
    return settings.input_image?.trim() || undefined;
  }
  return (
    settings.input_image?.trim() ||
    settings.reference_image?.trim() ||
    settings.reference_images?.find((item) => item.trim())?.trim() ||
    undefined
  );
}

export function activeReferenceMode(
  _settings: GenerationSettings,
  studioMode: StudioMode = "generate",
): ReferenceImageMode {
  return referenceModeForStudio(studioMode);
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
  studioMode: StudioMode = "edit",
): Partial<GenerationSettings> {
  const imagePath = typeof path === "string" ? path : "";
  const referenceRole = referenceRoleFromAttach(mode, studioMode);
  if (mode === "upscale") {
    return {
      reference_role: referenceRole,
      upscale_image: imagePath,
      input_image: undefined,
      reference_image: undefined,
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
      reference_role: referenceRole,
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
      reference_role: referenceRole,
      input_image: imagePath,
      upscale_image: undefined,
      inpaint_mask_path: undefined,
      ...qwenEdit2511LightningPatch(),
      output: outputFor("edit"),
    };
  }

  if (modelFamily === "flux_kontext") {
    return {
      reference_role: referenceRole,
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
    reference_role: referenceRole,
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

/** Generate tab: reference photo → img2img on the selected (or auto-routed edit) model. */
export type GenerateReferencePatchOptions = {
  currentModel?: string;
  userPickedModel?: boolean;
  modelFamily?: string;
};

/** Generate-tab restyle / img2img reference (keeps workflow on Create). */
export function buildRestyleReferencePatch(
  imagePath: string,
  shared: Partial<GenerationSettings> = {},
  modelFamily?: string,
): Partial<GenerationSettings> {
  return {
    ...shared,
    reference_role: "restyle",
    workflow_mode: shared.workflow_mode ?? "generate",
    input_image: imagePath,
    reference_image: imagePath,
    edit_type: "auto",
    cn_selection: "Custom...",
    cn_type: "img2img",
    face_preservation: undefined,
    identity_mode: undefined,
    edit_strength: defaultReferenceEditStrength(
      { edit_type: "auto" } as GenerationSettings,
      modelFamily,
    ),
  };
}

/** Image-prompt guidance via IP-Adapter (text-to-image + reference). */
export function buildImagePromptReferencePatch(
  path: string,
  outputFor: (suffix: string) => string,
): Partial<GenerationSettings> {
  const imagePath = typeof path === "string" ? path : "";
  return {
    reference_role: "image_prompt",
    workflow_mode: "ipadapter",
    reference_image: imagePath,
    input_image: undefined,
    upscale_image: undefined,
    inpaint_mask_path: undefined,
    style: "none",
    output: outputFor("gen"),
    cn_selection: "None",
    cn_type: "None",
    edit_type: "auto",
    face_preservation: undefined,
    identity_mode: undefined,
  };
}

/** Structure / ControlNet guidance from a reference map or photo. */
export function buildStructureReferencePatch(
  path: string,
  outputFor: (suffix: string) => string,
  structureType = "canny",
): Partial<GenerationSettings> {
  const imagePath = typeof path === "string" ? path : "";
  return {
    reference_role: "structure",
    workflow_mode: "controlnet",
    reference_image: imagePath,
    input_image: undefined,
    upscale_image: undefined,
    inpaint_mask_path: undefined,
    style: "none",
    output: outputFor("gen"),
    cn_selection: "Custom...",
    cn_type: structureType,
    edit_type: "auto",
    face_preservation: undefined,
    identity_mode: undefined,
  };
}

export function buildReferenceRolePatch(
  role: ReferenceRole,
  path: string,
  outputFor: (suffix: string) => string,
  options: {
    studioMode?: StudioMode;
    modelFamily?: string;
    currentModel?: string;
  } = {},
): Partial<GenerationSettings> {
  const studioMode = options.studioMode ?? "generate";
  if (role === "image_prompt") {
    return buildImagePromptReferencePatch(path, outputFor);
  }
  if (role === "restyle") {
    return buildRestyleReferencePatch(
      path,
      { output: outputFor(studioMode === "generate" ? "gen" : "edit") },
      options.modelFamily,
    );
  }
  if (role === "upscale") {
    return buildReferenceImagePatch(path, "upscale", outputFor, options.modelFamily, studioMode);
  }
  if (role === "inpaint") {
    return buildReferenceImagePatch(path, "inpaint", outputFor, options.modelFamily, studioMode);
  }
  if (role === "source_edit") {
    return {
      ...buildReferenceImagePatch(path, "reference", outputFor, options.modelFamily, studioMode),
      reference_role: "source_edit",
    };
  }
  if (role === "structure") {
    return buildStructureReferencePatch(path, outputFor);
  }
  return buildReferenceImagePatch(path, "reference", outputFor, options.modelFamily, studioMode);
}

/** Attach a Generate reference without changing the selected model or sampling. */
export function buildGenerateReferencePatch(
  path: string,
  outputFor: (suffix: string) => string,
  options: GenerateReferencePatchOptions = {},
): Partial<GenerationSettings> {
  return buildRestyleReferencePatch(path, {
    upscale_image: undefined,
    inpaint_mask_path: undefined,
    workflow_mode: "generate",
    style: "none",
    output: outputFor("gen"),
  }, options.modelFamily);
}

export function buildClearReferenceImagePatch(): Partial<GenerationSettings> {
  return {
    input_image: undefined,
    upscale_image: undefined,
    reference_image: undefined,
    reference_images: undefined,
    references: undefined,
    inpaint_mask_path: undefined,
    cn_selection: "None",
    cn_type: "None",
    edit_type: "auto",
    edit_task: undefined,
    inpaint_intent: undefined,
    inpaint_additional_prompt: undefined,
    inpaint_hard_mask: undefined,
    outpaint_direction: undefined,
    outpaint_amount: undefined,
    outpaint_feathering: undefined,
    upscale_method: undefined,
    face_preservation: undefined,
    identity_mode: undefined,
    preserve_character: undefined,
    workflow_mode: undefined,
    reference_role: undefined,
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

function dragTransferTypes(dataTransfer: DataTransfer): string[] {
  return Array.from(dataTransfer.types ?? []).map((type) => type.toLowerCase());
}

export function canAcceptImagePathDrag(dataTransfer: DataTransfer): boolean {
  if (getDraggingImagePath()) return true;
  const types = dragTransferTypes(dataTransfer);
  return (
    types.includes(DREAMFORGE_IMAGE_PATH_MIME.toLowerCase()) ||
    types.includes("text/plain") ||
    types.includes("text/uri-list") ||
    types.includes("files")
  );
}

/** Call on dragenter/dragover (incl. capture) so nested buttons don't show a blocked cursor. */
export function handleImagePathDragOver(
  event: Pick<DragEvent, "preventDefault" | "stopPropagation" | "dataTransfer">,
  disabled = false,
): boolean {
  event.preventDefault();
  event.stopPropagation();
  if (disabled) return false;
  const transfer = event.dataTransfer;
  if (!transfer) return false;
  const accepted = canAcceptImagePathDrag(transfer);
  if (accepted) {
    transfer.dropEffect = "copy";
  }
  return accepted;
}

let dragDropBridgeInstalled = false;

/** WebView2/Tauri: keep internal image drags droppable (requires dragDropEnabled: false). */
export function installImagePathDragDropBridge() {
  if (typeof window === "undefined" || dragDropBridgeInstalled) return;
  dragDropBridgeInstalled = true;

  window.addEventListener(
    "dragover",
    (event) => {
      const transfer = event.dataTransfer;
      if (transfer && canAcceptImagePathDrag(transfer)) {
        event.preventDefault();
        transfer.dropEffect = "copy";
      }
    },
    { capture: true },
  );

  window.addEventListener(
    "dragenter",
    (event) => {
      const transfer = event.dataTransfer;
      if (transfer && canAcceptImagePathDrag(transfer)) {
        event.preventDefault();
        transfer.dropEffect = "copy";
      }
    },
    { capture: true },
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
  studioMode: StudioMode,
  path: string,
): string {
  const modeLabel =
    studioMode === "inpaint"
      ? "Inpaint"
      : studioMode === "upscale"
        ? "Upscale"
        : studioMode === "edit"
          ? "Edit"
          : "Reference";
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

/** Drop cross-mode image fields so the active studio tab stays authoritative. */
export function sanitizeEditFamilySettings(
  settings: GenerationSettings,
  studioMode: StudioMode,
): GenerationSettings {
  return sanitizeSettingsForStudioMode(studioMode, settings);
}

/** Optimal default edit strength for reference / inpaint workflows (Krita-aligned). */
export function defaultReferenceEditStrength(
  settings: GenerationSettings,
  modelFamily?: string,
): number {
  const family = (modelFamily ?? "").toLowerCase();
  if (family.includes("z_image") || family.includes("z-image")) return 0.35;
  if (family === "qwen_image_edit") return 1.0;
  if (settings.edit_type === "inpaint") return 0.9;
  return 0.75;
}

export function effectiveReferenceEditStrength(
  settings: GenerationSettings,
  modelFamily?: string,
): number {
  const value = settings.edit_strength;
  if (value != null && value > 0) return value;
  return defaultReferenceEditStrength(settings, modelFamily);
}
