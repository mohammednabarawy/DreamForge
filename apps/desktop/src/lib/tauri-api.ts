import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import type { StyleGroup } from "./inventory";

export type OutputItem = {
  manifest_path: string;
  timestamp: string;
  created_at?: string;
  session: string;
  title: string;
  prompt: string;
  model_family: string;
  model_name: string;
  model_stem: string;
  images: string[];
  styles: string[];
  seed?: number;
};

export type GenerationSettings = {
  model?: string;
  prompt?: string;
  negative_prompt?: string;
  aspect_ratio?: string;
  width?: number;
  height?: number;
  seed?: number;
  steps?: number;
  cfg_scale?: number;
  sampler?: string;
  scheduler?: string;
  styles?: string[];
  lora?: string[];
  vram_profile?: "auto" | "16gb" | "8gb" | "5gb";
  use_case?: string;
  performance?: string;
  image_number?: number;
  cn_selection?: string;
  cn_type?: string;
  upscale_image?: string;
  upscale_method?: string;
  edit_type?: "auto" | "kontext" | "inpaint" | "img2img" | "qwen_edit";
  input_image?: string;
  inpaint_mask_path?: string;
  lora_keywords?: string;
  clip_skip?: number;
  auto_negative_prompt?: boolean;
  subject?: string;
  composition?: string;
  lighting?: string;
  camera?: string;
  brand_colors?: string;
  output?: string;
  validate_output?: boolean;
  civitai_api_key?: string;
};

export type InventoryPayload = {
  categories: Record<string, Array<{ name: string; family?: string }>>;
  styles: string[];
  style_groups: StyleGroup[];
  presets: unknown[];
};

/**
 * Stable error codes emitted by the Python worker.
 * Keep in sync with backend/dreamforge_errors.py.
 */
export type DreamForgeErrorCode =
  | "out_of_memory"
  | "missing_input_image"
  | "invalid_input_image"
  | "missing_model_dependencies"
  | "model_not_found"
  | "model_file_unreadable"
  | "unsupported_model_format"
  | "disk_full"
  | "worker_crashed"
  | "generation_cancelled"
  | "generation_in_progress"
  | "invalid_request"
  | "generation_failed";

export type StructuredError = {
  code?: DreamForgeErrorCode | string;
  /** Legacy field; identical to `code` for new payloads. */
  error?: DreamForgeErrorCode | string;
  message?: string;
  suggestions?: string[];
  details?: Record<string, unknown>;
  recoverable?: boolean;
};

export type GenerationFinishedPayload = StructuredError & {
  job_id?: string;
  success?: boolean;
  /** Worker exit code OR a numeric status (0 = success, 1 = error). */
  code?: number | DreamForgeErrorCode | string;
  log_path?: string;
  log_tail?: string;
  result?: {
    images?: Array<{ path: string }>;
  };
};

export type WorkerFailedPayload = StructuredError & {
  log_tail?: string;
};

export type GenerationPreviewPayload = {
  job_id?: string;
  data_url?: string;
  preview_path?: string;
  has_preview?: boolean;
  percentage?: number;
  title?: string;
};

export async function getPaths() {
  return invoke<Record<string, unknown>>("get_paths");
}

export type UiDefaults = {
  performances?: string[];
  controlnet_presets?: string[];
  aspect_ratios?: string[];
  samplers?: string[];
  schedulers?: string[];
};

export type ModelGalleryItem = {
  category: string;
  relative_path: string;
  caption: string;
  engine_name: string;
  family: string;
  thumbnail_path: string;
};

export type LoraGalleryItem = {
  name: string;
  stem: string;
  relative_path?: string;
  thumbnail_path: string;
};

export type ModelUiProfile = {
  family: string;
  category: string;
  engine_name: string;
  performance_selection: string;
  apply_performance: boolean;
  clear_styles: boolean;
  clear_negative: boolean;
  custom_sampling?: {
    custom_steps: number;
    cfg: number;
    sampler_name: string;
    scheduler: string;
    clip_skip: number;
  };
  hints: string[];
};

export async function getUiDefaults() {
  return invoke<UiDefaults & { ok?: boolean }>("get_ui_defaults");
}

export async function listUseCases() {
  const res = await invoke<{ ok?: boolean; use_cases?: Array<{ id: string; models?: string[] }> }>(
    "list_use_cases",
  );
  return { use_cases: res.use_cases ?? [] };
}

export async function getInventory() {
  return invoke<InventoryPayload & { ok?: boolean }>("get_inventory", {
    include_fonts: false,
  });
}

export async function getModelGallery(filter = "") {
  const res = await invoke<{ ok?: boolean; items?: ModelGalleryItem[] }>(
    "get_model_gallery",
    { filter },
  );
  return res.items ?? [];
}

export async function getLoraGallery(filter = "") {
  const res = await invoke<{ ok?: boolean; items?: LoraGalleryItem[] }>(
    "get_lora_gallery",
    { filter },
  );
  return res.items ?? [];
}

export async function resolveModelProfile(params: {
  caption?: string;
  category?: string;
  relative_path?: string;
  performance?: string;
  lock_family_defaults?: boolean;
  preset_active?: boolean;
}) {
  return invoke<{
    ok?: boolean;
    profile: ModelUiProfile;
    caption?: string;
    civit_base?: string;
  }>("resolve_model_profile", { params });
}

export type OutputsPage = {
  items: OutputItem[];
  total: number;
  offset: number;
  limit: number;
  hasMore: boolean;
};

export async function listOutputsPage(opts?: {
  limit?: number;
  offset?: number;
  session?: string;
}): Promise<OutputsPage> {
  const limit = opts?.limit ?? 50;
  const offset = opts?.offset ?? 0;
  const res = await invoke<{
    ok?: boolean;
    items?: OutputItem[];
    total?: number;
    offset?: number;
    limit?: number;
    has_more?: boolean;
  }>("list_outputs", {
    since: null,
    limit,
    offset,
    session: opts?.session ?? null,
  });
  const items = res.items ?? [];
  const total = res.total ?? items.length;
  return {
    items,
    total,
    offset: res.offset ?? offset,
    limit: res.limit ?? limit,
    hasMore: res.has_more ?? offset + items.length < total,
  };
}

/** @deprecated Use listOutputsPage */
export async function listOutputs(limit = 60) {
  const page = await listOutputsPage({ limit, offset: 0 });
  return page.items;
}

export async function searchOutputsPage(
  query: string,
  opts?: { limit?: number; offset?: number },
): Promise<OutputsPage> {
  const q = query.trim();
  if (!q) {
    return { items: [], total: 0, offset: 0, limit: 0, hasMore: false };
  }
  const limit = opts?.limit ?? 50;
  const offset = opts?.offset ?? 0;
  const res = await invoke<{
    ok?: boolean;
    items?: OutputItem[];
    total?: number;
    offset?: number;
    limit?: number;
    has_more?: boolean;
  }>("search_outputs", { query: q, limit, offset });
  const items = res.items ?? [];
  const total = res.total ?? items.length;
  return {
    items,
    total,
    offset: res.offset ?? offset,
    limit: res.limit ?? limit,
    hasMore: res.has_more ?? offset + items.length < total,
  };
}

export async function revealPathInExplorer(path: string) {
  return invoke<void>("reveal_path_in_explorer", { path });
}

type DeleteResponse = {
  ok?: boolean;
  error?: string;
  manifest_removed?: boolean;
  deleted_image?: string;
};

function assertDeleteOk(res: DeleteResponse) {
  if (res.ok || res.manifest_removed || res.deleted_image) return;
  throw new Error(res.error ?? "delete_failed");
}

export async function deleteOutput(manifestPath: string) {
  const res = await invoke<DeleteResponse>("delete_output", {
    manifestPath,
  });
  assertDeleteOk(res);
  return res;
}

export async function deleteOutputImage(
  manifestPath: string,
  imagePath: string,
) {
  const res = await invoke<DeleteResponse>("delete_output_image", {
    manifestPath,
    imagePath,
  });
  assertDeleteOk(res);
  return res;
}

export async function deleteSession(session: string) {
  const res = await invoke<{ ok?: boolean; error?: string }>("delete_session", {
    session,
  });
  if (!res.ok) {
    throw new Error(res.error ?? "delete_failed");
  }
  return res;
}

export async function dryRun(params: GenerationSettings) {
  const res = await invoke<{ ok?: boolean; plan?: Record<string, unknown> }>(
    "dry_run",
    { params },
  );
  return { plan: res.plan ?? res };
}

export async function invokeGeneration(params: GenerationSettings) {
  return invoke<{ job_id: string; status: string; log_path?: string }>(
    "invoke_generation",
    {
      params: { ...params, json: true },
    },
  );
}

export async function cancelGeneration() {
  return invoke<{ cancelled: boolean; job_id?: string }>("cancel_generation");
}

export async function readJobLog(jobId: string) {
  return invoke<{ tail: string; log_path: string }>("read_job_log", {
    jobId,
  });
}

export async function generationStatus() {
  return invoke<{ running: boolean; job_id?: string }>("generation_status");
}

export async function readImagePreview(path: string) {
  return invoke<{ data_url: string; mime: string; path: string }>(
    "read_image_preview",
    {
      path,
    },
  );
}

export async function pickImageFile() {
  return invoke<string | null>("pick_image_file");
}

export async function readLivePreview() {
  return invoke<{ data_url: string; mime: string; path?: string }>(
    "read_live_preview",
  );
}

export async function windowDrag() {
  return invoke("window_drag");
}

export async function notifyDone(title: string, body: string) {
  try {
    await invoke("show_generation_notification", { title, body });
  } catch {
    /* optional in dev */
  }
}

export function onOutputsChanged(cb: () => void) {
  return listen("outputs-changed", () => cb());
}

export function onGenerationStarted(
  cb: (payload: { job_id?: string; log_path?: string }) => void,
) {
  return listen<{ job_id?: string; log_path?: string }>(
    "generation-started",
    (e) => cb(e.payload),
  );
}

export function onGenerationFinished(cb: (payload: GenerationFinishedPayload) => void) {
  return listen<GenerationFinishedPayload>("generation-finished", (e) =>
    cb(e.payload),
  );
}

export function onGenerationPreview(
  cb: (payload: GenerationPreviewPayload) => void,
) {
  return listen<GenerationPreviewPayload>("generation-preview", (e) =>
    cb(e.payload),
  );
}

/**
 * Advisory events emitted by the worker (e.g. preflight warnings such as
 * ``low_disk_space`` / ``vram_headroom_low``).  Same shape as a
 * StructuredError but with ``type === "warning"``.
 */
export type GenerationWarningPayload = StructuredError & {
  type?: "warning";
  job_id?: string;
};

export function onGenerationWarning(
  cb: (payload: GenerationWarningPayload) => void,
) {
  return listen<GenerationWarningPayload>("generation-warning", (e) =>
    cb(e.payload),
  );
}

export function onWorkerReady(
  cb: (payload: {
    ready?: boolean;
    preview_path?: string;
    gpu_name?: string;
    vram_gb?: number;
  }) => void,
) {
  return listen<{
    ready?: boolean;
    preview_path?: string;
    gpu_name?: string;
    vram_gb?: number;
  }>("worker-ready", (e) => cb(e.payload));
}

export function onWorkerStatus(cb: (payload: { status?: string }) => void) {
  return listen<{ status?: string }>("worker-status", (e) => cb(e.payload));
}

export function onWorkerBootProgress(
  cb: (payload: { message?: string; phase?: string }) => void,
) {
  return listen<{ message?: string; phase?: string }>("worker-boot-progress", (e) =>
    cb(e.payload),
  );
}

export function onEngineHealthStatus(
  cb: (payload: { health?: EngineHealth; previous?: string }) => void,
) {
  return listen<{ health?: EngineHealth; previous?: string }>(
    "engine-health-status",
    (e) => cb(e.payload),
  );
}

export function onWorkerDead(
  cb: (payload: { error?: string; log_tail?: string }) => void,
) {
  return listen<{ error?: string; log_tail?: string }>("worker-dead", (e) =>
    cb(e.payload),
  );
}

export function onGenerationProgress(
  cb: (payload: {
    phase?: string;
    progress?: number;
    message?: string;
    job_id?: string;
  }) => void,
) {
  return listen<{
    phase?: string;
    progress?: number;
    message?: string;
    job_id?: string;
  }>("generation-progress", (e) => cb(e.payload));
}

export function onGenerationBusy(
  cb: (payload: { code?: number; error?: string; message?: string }) => void,
) {
  return listen<{ code?: number; error?: string; message?: string }>(
    "generation-busy",
    (e) => cb(e.payload),
  );
}

export function onWorkerFailed(cb: (payload: WorkerFailedPayload) => void) {
  return listen<WorkerFailedPayload>("worker-failed", (e) => cb(e.payload));
}

export type EngineHealth = "alive" | "booting" | "dead" | "restarting" | "unknown";

export type EngineStatus = {
  ready: boolean;
  events_ready?: boolean;
  worker_alive?: boolean;
  worker_running: boolean;
  health?: EngineHealth;
  boot_phase?: string;
  boot_message?: string;
  boot_elapsed_secs?: number;
  bridge_alive?: boolean;
  generation_running?: boolean;
  gpu_name?: string | null;
  vram_gb?: number | null;
  cuda_available?: boolean | null;
  mps_available?: boolean | null;
  bridge_health?: Record<string, unknown>;
  worker_log?: string;
  events_log?: string;
};

export type GenerationProgress = {
  running: boolean;
  phase?: string;
  progress?: number;
  message?: string;
  job_id?: string;
};

export async function getEngineStatus() {
  return invoke<EngineStatus>("get_engine_status");
}

export async function getGenerationProgress() {
  return invoke<GenerationProgress>("get_generation_progress");
}

export async function readWorkerLog() {
  return invoke<{ path: string; tail: string }>("read_worker_log");
}

export async function readFullWorkerLog() {
  return invoke<{ path: string; tail: string }>("read_full_worker_log");
}

export async function restartGpuWorker() {
  return invoke<{ ready?: boolean }>("restart_gpu_worker");
}

export type DownloadProgressPayload = {
  filename: string;
  percentage?: number;
  downloaded?: number;
  total?: number;
  status?: "downloading" | "complete" | "exists" | "error";
  path?: string;
  category?: string;
};

export type ModelDependencyItem = {
  id?: string;
  relative?: string;
  note?: string;
  expected_path?: string;
  url?: string;
  category?: string;
  filename?: string;
  optional?: boolean;
};

export type ModelDependenciesResult = {
  ok?: boolean;
  model?: Record<string, unknown>;
  missing: ModelDependencyItem[];
  ready: boolean;
};

export type DownloadCompanionsResult = {
  ok?: boolean;
  status?: string;
  model?: Record<string, unknown>;
  downloaded?: number;
  skipped?: number;
  results?: Array<{ status?: string; path?: string; id?: string }>;
  errors?: Array<{ id?: string; relative?: string; error?: string }>;
};

export async function checkModelDependencies(model: string) {
  return invoke<ModelDependenciesResult>("check_model_dependencies", { model });
}

export async function downloadModelCompanions(model: string, ids?: string[]) {
  return invoke<DownloadCompanionsResult>("download_model_companions", {
    model,
    ids: ids ?? null,
  });
}

export async function downloadModel(params: {
  url: string;
  category: string;
  filename: string;
  apiKey?: string | null;
}) {
  return invoke<void>("download_model", params);
}

export function onDownloadProgress(cb: (payload: DownloadProgressPayload) => void) {
  return listen<DownloadProgressPayload>("download-progress", (e) => cb(e.payload));
}

export function onDownloadComplete(cb: (payload: DownloadProgressPayload) => void) {
  return listen<DownloadProgressPayload>("download-complete", (e) => cb(e.payload));
}
