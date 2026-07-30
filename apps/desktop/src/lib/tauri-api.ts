import { invoke, isTauri } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import type { StyleGroup } from "./inventory";

type Unlisten = () => void;

function safeListen<T>(
  event: string,
  handler: (event: { payload: T }) => void,
): Promise<Unlisten> {
  if (!isTauri()) {
    return Promise.resolve(() => {});
  }
  return listen<T>(event, handler);
}

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
  vram_profile?:
    | "auto"
    | "16gb"
    | "8gb"
    | "5gb"
    | "no_gpu"
    | "mps_24gb"
    | "mps_16gb"
    | "mps_8gb"
    | "mps_4gb"
    | "mps";
  style?: string;
  performance?: string;
  image_number?: number;
  cn_selection?: string;
  cn_type?: string;
  upscale_image?: string;
  upscale_method?: string;
  /** Named enhance preset. */
  upscale_preset?: "1.5x" | "2x" | "faithful_2x" | "fast_2x" | "fast_4x" | "detail_2x";
  upscale_by?: number;
  upscale_denoise?: number;
  upscale_tile_width?: number;
  upscale_tile_height?: number;
  upscale_mask_blur?: number;
  upscale_tile_padding?: number;
  upscale_seam_fix_mode?: string;
  upscale_seam_fix_denoise?: number;
  upscale_seam_fix_width?: number;
  upscale_seam_fix_mask_blur?: number;
  upscale_seam_fix_padding?: number;
  upscale_force_uniform_tiles?: boolean;
  upscale_tiled_decode?: boolean;
  upscale_mode_type?: string;
  cn_upscale?: string;
  batch_size?: number;
  edit_type?: "auto" | "kontext" | "inpaint" | "img2img" | "qwen_edit" | "outpaint";
  edit_strength?: number;
  /** Fooocus-style img2img variation strength preset. */
  vary_amount?: "subtle" | "strong";
  /** Qwen edit graph: auto picks plus when reference_images are set. */
  qwen_edit_mode?:
    | "auto"
    | "single"
    | "plus"
    | "raw"
    | "raw_plus"
    | "preserve"
    | "preserve_resolution"
    | "exact"
    | "lightning_4step";
  /** ModelSamplingAuraFlow shift (Qwen Image / Edit). */
  qwen_image_shift?: number;
  /** Scale edit canvas to this megapixel budget before encode (VRAM). */
  qwen_scale_megapixels?: number;
  /** Qwen Edit Plus: VAE-encode refs at source resolution + ReferenceLatent (no 1MP rescale). */
  qwen_preserve_resolution?: boolean;
  /** Optional megapixel cap when preserve_resolution is on (VRAM safety). */
  qwen_preserve_megapixels?: number;
  use_qwen_lightning_lora?: boolean;
  qwen_lightning_strength?: number;
  /** Ideogram 4 scheduler preset (Default / Quality / Turbo). */
  ideogram4_mode?: "default" | "quality" | "turbo";
  /** Ideogram 4 prompt handling on Generate. */
  ideogram4_prompt_mode?: "natural" | "structured" | "auto";
  /** Run magic prompt on Generate when mode is natural (Enhance still always expands). */
  ideogram4_enhance_on_generate?: boolean;
  /** Sync width/height with Ideogram aspect presets (custom uses width/height fields). */
  ideogram4_aspect_preset?: "1:1" | "4:5" | "9:16" | "16:9" | "2:3" | "custom";
  /** Opt in to Quality (48 steps) on 16 GB VRAM dual-UNet runs. */
  ideogram4_allow_quality_on_16gb?: boolean;
  /** Advanced Ideogram4Scheduler overrides (optional). */
  ideogram4_mu_override?: number;
  ideogram4_std_override?: number;
  ideogram4_steps_override?: number;
  ideogram4_dual_cfg_override?: number;
  ideogram4_cfg_override?: number;
  ideogram4_cfg_override_start?: number;
  ideogram4_cfg_override_end?: number;
  input_image?: string;
  /** Primary style/face reference for IP-Adapter generate workflows. */
  reference_image?: string;
  /** Additional Kontext/control reference images (Krita-style multi-reference). */
  reference_images?: string[];
  /** Multi-slot references (Pro Create): path + role + weight + stop-at per slot. */
  references?: Array<{
    path: string;
    role:
      | "image_prompt"
      | "restyle"
      | "source_edit"
      | "inpaint"
      | "upscale"
      | "structure";
    weight?: number;
    stop_at?: number;
    structure_type?: string;
  }>;
  reference_weight?: number;
  cn_strength?: number;
  cn_stop?: number;
  structure_type?: string;
  /** Identity preservation intent: preserve_face (Kontext/Qwen) or ipadapter_faceid when assets exist. */
  identity_mode?: "preserve_face" | "kontext" | "qwen_edit" | "ipadapter_faceid" | "auto" | string;
  face_preservation?: boolean;
  /** Inpaint mask preprocessing (Krita grow/feather). */
  inpaint_grow?: number;
  inpaint_feather?: number;
  inpaint_mask_grow_by?: number;
  /** Named inpaint mode: default / improve_detail / modify_content. */
  inpaint_intent?: "default" | "improve_detail" | "modify_content";
  /** Backend-owned edit/inpaint task preset resolved during dry-run. */
  edit_task?:
    | "remove"
    | "replace"
    | "add"
    | "repair"
    | "refine"
    | "recolor"
    | "relight"
    | "restyle"
    | "extend"
    | "global_edit"
    | "photo_restore"
    | "outfit_transfer"
    | "cutout_compose"
    | "portrait_master";
  /** Active imported ComfyUI custom tool (execution pending backend wiring). */
  custom_tool_id?: string;
  cutout_placement?: "center" | "left" | "right" | "foreground" | "background";
  outfit_transfer_regions?: Array<
    "upper_body" | "lower_body" | "full_outfit" | "shoes_accessories"
  >;
  portrait_shot?: "closeup" | "portrait" | "medium" | "full";
  portrait_age?: number;
  portrait_expression?: "neutral" | "happy" | "serious" | "confident";
  portrait_lighting?: "soft" | "studio" | "natural" | "dramatic";
  portrait_skin_detail?: number;
  portrait_eye_detail?: number;
  portrait_pose_strength?: number;
  portrait_depth_strength?: number;
  /** Photo restore: depth ControlNet strength (0.1–0.2 typical). */
  depth_strength?: number;
  /** Photo restore: lineart ControlNet strength (0.2–0.5 typical). */
  lineart_strength?: number;
  /** Extra prompt for improve_detail / modify_content passes. */
  inpaint_additional_prompt?: string;
  /** Planner hints for edit-family preservation (UI toggles). */
  preserve_character?: boolean;
  preserve_style?: boolean;
  preserve_text?: boolean;
  inpaint_mask_path?: string;
  /** Skip feathering on inpaint mask edges (advanced). */
  inpaint_hard_mask?: boolean;
  /** Outpaint / canvas extend direction and padding. */
  outpaint_direction?: "left" | "right" | "top" | "bottom" | "";
  outpaint_amount?: number;
  outpaint_feathering?: number;
  /** What the attached image means for routing (explicit user intent). */
  reference_role?:
    | "image_prompt"
    | "restyle"
    | "source_edit"
    | "inpaint"
    | "upscale"
    | "structure";
  /** Creative template bundle id. */
  template_id?: string;
  /** Run Ultimate SD Upscale after edit/inpaint completes. */
  post_upscale?: string;
  /** UI toggle: sharpen output after edit/inpaint. */
  post_upscale_enabled?: boolean;
  /** Optional Comfy Save (API Format) workflow template path. */
  comfy_workflow_api?: string;
  /** Route through the Krita-style managed ComfyUI server. */
  use_comfy_server?: boolean;
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
  studio_mode?: "generate" | "edit" | "inpaint" | "upscale" | "toolbox" | "agent";
  workflow_mode?: string;
  arabic_text?: string;
  execute_workflow_plan?: boolean;
  workflow_plan?: Array<Record<string, unknown>>;
  detail_target?: string;
  detail_prompt?: string;
  /** Auto-enhance: detect face/hands/eyes and run targeted fix. */
  enhance_auto_fix?: boolean;
  enhance_target?: "face" | "hands" | "eyes" | "auto";
  enhance_detection_prompt?: string;
  enhance_post_upscale?: boolean;
  /** HiDream-O1 Dev: flash noise scale (locked 7.6 on Dev mxfp8). */
  hidream_noise_scale?: number;
  hidream_s_noise?: number;
  hidream_s_noise_end?: number;
  hidream_noise_clip_std?: number;
  hidream_patch_seam_smoothing?: boolean;
  hidream_reference_megapixels?: number;
  hidream_prompt_refinement?: boolean;
  prompt_enhancer?: "none" | "hyperprompt" | "flufferizer" | "erniehancer" | string;
  denoise?: number;
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
  | "missing_custom_node_pack"
  | "model_not_found"
  | "model_file_unreadable"
  | "unsupported_model_format"
  | "unsupported_model_for_workflow"
  | "unsupported_workflow_class"
  | "disk_full"
  | "virtual_memory_low"
  | "low_system_ram"
  | "low_disk_space"
  | "vram_headroom_low"
  | "worker_crashed"
  | "worker_boot_failed"
  | "worker_pipe_closed"
  | "comfy_server_crashed"
  | "generation_cancelled"
  | "generation_in_progress"
  | "invalid_request"
  | "comfy_workflow_validation"
  | "generation_failed";

export type RepairAction = {
  action?: string;
  requires_approval?: boolean;
  hint?: string;
  missing?: Array<Record<string, unknown>>;
  catalog_ids?: string[];
  nodes?: string[];
  pack_id?: string;
  vram_profile?: string;
  scale?: number;
  image_number?: number;
  max_retries?: number;
  [key: string]: unknown;
};

export type FailureReport = {
  kind?: string;
  summary?: string;
  recoverable?: boolean;
  auto_retry?: boolean;
  max_auto_retries?: number;
  requires_user_approval?: boolean;
  repair_actions?: RepairAction[];
};

export type StructuredError = {
  code?: DreamForgeErrorCode | string;
  /** Legacy field; identical to `code` for new payloads. */
  error?: DreamForgeErrorCode | string;
  message?: string;
  suggestions?: string[];
  details?: Record<string, unknown>;
  failure_report?: FailureReport;
  recoverable?: boolean;
};

export type GenerationFinishedPayload = StructuredError & {
  job_id?: string;
  success?: boolean;
  /** Worker exit code OR a numeric status (0 = success, 1 = error). */
  code?: number | DreamForgeErrorCode | string;
  log_path?: string;
  log_tail?: string;
  /** Final frame inlined by the shell when generation succeeds. */
  data_url?: string;
  preview_path?: string;
  asset_url?: string;
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
  asset_url?: string;
  has_preview?: boolean;
  /** Step preview during sampling (smaller, frequent updates). */
  live?: boolean;
  /** Final high-res frame (emitted before generation-finished). */
  final?: boolean;
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
  size_bytes?: number;
  modified_at?: number;
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
  settings_patch?: Partial<GenerationSettings> | null;
  hints: string[];
};

export async function getUiDefaults() {
  return invoke<UiDefaults & { ok?: boolean }>("get_ui_defaults");
}

export async function listStyles() {
  const res = await invoke<{ ok?: boolean; styles?: Array<{ id: string; models?: string[] }> }>(
    "list_styles",
  );
  return { styles: res.styles ?? [] };
}

export async function getInventory(opts?: { forceRefresh?: boolean }) {
  return invoke<InventoryPayload & { ok?: boolean; from_cache?: boolean }>(
    "get_inventory",
    {
      include_fonts: false,
      force_refresh: Boolean(opts?.forceRefresh),
    },
  );
}

export async function getModelGallery(
  filter = "",
  opts?: { forceRefresh?: boolean },
) {
  const res = await invoke<{ ok?: boolean; items?: ModelGalleryItem[]; from_cache?: boolean }>(
    "get_model_gallery",
    { filter, force_refresh: Boolean(opts?.forceRefresh) },
  );
  return res.items ?? [];
}

export async function getLoraGallery(
  filter = "",
  opts?: { forceRefresh?: boolean },
) {
  const res = await invoke<{ ok?: boolean; items?: LoraGalleryItem[]; from_cache?: boolean }>(
    "get_lora_gallery",
    { filter, force_refresh: Boolean(opts?.forceRefresh) },
  );
  return res.items ?? [];
}

export async function refreshModelLibraryCache() {
  return invoke<{ ok?: boolean; rebuilt?: boolean; model_gallery?: number; lora_gallery?: number }>(
    "refresh_model_library_cache",
  );
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

export type GenerationBundleResult = {
  ok?: boolean;
  manifest_path?: string;
  bundle?: Record<string, unknown>;
  status?: string;
  message?: string;
};

export async function getGenerationBundle(manifestPath: string) {
  const res = await invoke<GenerationBundleResult & { error?: string }>(
    "bridge_invoke",
    {
      cmd: "get_generation_bundle",
      params: { manifest_path: manifestPath },
    },
  );
  if (res.error) {
    return { ok: false, status: "error", message: res.error };
  }
  return res;
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

export async function invokeAutomation(spec: Record<string, unknown>) {
  return invoke<{ job_id: string; status: string; log_path?: string }>(
    "invoke_automation",
    {
      spec,
    },
  );
}

export async function cancelGeneration() {
  return invoke<{ cancelled: boolean; job_id?: string }>("cancel_generation");
}

export async function cancelAutomation() {
  return invoke<{ cancelled: boolean; job_id?: string }>("cancel_automation");
}

export async function readJobLog(jobId: string) {
  return invoke<{ tail: string; log_path: string }>("read_job_log", {
    jobId,
  });
}

export async function generationStatus() {
  return invoke<{ running: boolean; job_id?: string }>("generation_status");
}

export type ImagePreviewResponse = {
  data_url?: string;
  asset_url?: string;
  mime: string;
  path: string;
  quality?: string;
};

export async function readImagePreview(
  path: string,
  opts?: { quality?: "live" | "final" },
) {
  return invoke<ImagePreviewResponse>("read_image_preview", {
    path,
    quality: opts?.quality ?? "final",
  });
}

export async function pickImageFile() {
  return invoke<string | null>("pick_image_file");
}

export async function readTextFile(path: string): Promise<string | null> {
  if (!isTauri()) return null;
  return await invoke("read_text_file", { path });
}

export async function pickTextFile(): Promise<string | null> {
  if (!isTauri()) return null;
  return await invoke("pick_text_file");
}

export async function pickJsonFile(): Promise<string | null> {
  if (!isTauri()) return null;
  return await invoke("pick_json_file");
}

export async function pickFolder(): Promise<string | null> {
  return invoke<string | null>("pick_folder");
}

export async function readLivePreview() {
  return invoke<ImagePreviewResponse>("read_live_preview");
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
  return safeListen("outputs-changed", () => cb());
}

export function onGenerationStarted(
  cb: (payload: { job_id?: string; log_path?: string }) => void,
) {
  return safeListen<{ job_id?: string; log_path?: string }>(
    "generation-started",
    (e) => cb(e.payload),
  );
}

export function onGenerationFinished(cb: (payload: GenerationFinishedPayload) => void) {
  return safeListen<GenerationFinishedPayload>("generation-finished", (e) =>
    cb(e.payload),
  );
}

export function onGenerationPreview(
  cb: (payload: GenerationPreviewPayload) => void,
) {
  return safeListen<GenerationPreviewPayload>("generation-preview", (e) =>
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
  return safeListen<GenerationWarningPayload>("generation-warning", (e) =>
    cb(e.payload),
  );
}

export type ComfyBackendStatus = {
  ok: boolean;
  error?: string;
  installed: boolean;
  needs_update: boolean;
  current: string;
  target: string;
};

export async function checkComfyBackend(): Promise<ComfyBackendStatus> {
  return invoke<ComfyBackendStatus>("bridge_invoke", {
    cmd: "check_comfy_backend",
    params: {},
  });
}

export async function installComfyBackend(optionalNodes = false): Promise<{ ok: boolean; error?: string }> {
  return invoke<{ ok: boolean; error?: string }>("bridge_invoke", {
    cmd: "install_comfy_backend",
    params: { optional_nodes: optionalNodes },
  });
}

export function onWorkerReady(
  cb: (payload: {
    ready?: boolean;
    preview_path?: string;
    gpu_name?: string;
    vram_gb?: number;
  }) => void,
) {
  return safeListen<{
    ready?: boolean;
    preview_path?: string;
    gpu_name?: string;
    vram_gb?: number;
  }>("worker-ready", (e) => cb(e.payload));
}

export function onWorkerStatus(cb: (payload: { status?: string; message?: string }) => void) {
  return safeListen<{ status?: string; message?: string }>("worker-status", (e) => cb(e.payload));
}

export function onWorkerBootProgress(
  cb: (payload: { message?: string; phase?: string }) => void,
) {
  return safeListen<{ message?: string; phase?: string }>("worker-boot-progress", (e) =>
    cb(e.payload),
  );
}

export function onEngineHealthStatus(
  cb: (payload: { health?: EngineHealth; previous?: string }) => void,
) {
  return safeListen<{ health?: EngineHealth; previous?: string }>(
    "engine-health-status",
    (e) => cb(e.payload),
  );
}

export function onWorkerDead(
  cb: (payload: { error?: string; log_tail?: string }) => void,
) {
  return safeListen<{ error?: string; log_tail?: string }>("worker-dead", (e) =>
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
  return safeListen<{
    phase?: string;
    progress?: number;
    message?: string;
    job_id?: string;
  }>("generation-progress", (e) => cb(e.payload));
}

export function onGenerationBusy(
  cb: (payload: { code?: number; error?: string; message?: string }) => void,
) {
  return safeListen<{ code?: number; error?: string; message?: string }>(
    "generation-busy",
    (e) => cb(e.payload),
  );
}

export function onWorkerFailed(cb: (payload: WorkerFailedPayload) => void) {
  return safeListen<WorkerFailedPayload>("worker-failed", (e) => cb(e.payload));
}

export type EngineHealth = "alive" | "booting" | "dead" | "restarting" | "unknown";

export type EngineStatus = {
  ready: boolean;
  events_ready?: boolean;
  comfy_ready?: boolean;
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
  desktop_vram_profile?: string;
  resolved_vram_profile?: string | null;
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
  if (!isTauri()) {
    return {
      ready: false,
      worker_running: false,
      health: "unknown" as const,
      bridge_alive: false,
      boot_message: "Desktop bridge unavailable in browser preview",
    };
  }
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

export async function restartGpuWorker(vramProfile?: string) {
  return invoke<{ ready?: boolean }>("restart_gpu_worker", {
    vramProfile: vramProfile ?? null,
  });
}

/** Ask the GPU worker to unload Comfy models via /free (idle memory after a job). */
export async function freeWorkerVram() {
  return invoke<void>("free_worker_vram");
}

export async function syncDesktopVramProfile(profile: string) {
  return invoke<{
    desktop_vram_profile?: string;
    resolved_vram_profile?: string;
  }>("sync_desktop_vram_profile", { profile });
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
  download_tier?: "A" | "B";
  min_bytes?: number;
  requires_hf_token?: boolean;
  kind?: "model" | "custom_node_pack" | "workflow_model" | "custom_tool";
  pack_id?: string;
  catalog_id?: string;
  missing_nodes?: string[];
  /** pinned = DreamForge recipe SHA; manager = ComfyUI-Manager cm-cli; direct = HF workflow model */
  install_via?: "pinned" | "manager" | "direct";
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

export async function checkModelDependencies(
  model: string,
  performance?: string | null,
) {
  return invoke<ModelDependenciesResult>("check_model_dependencies", {
    model,
    performance: performance ?? null,
  });
}

export async function downloadModelCompanions(
  model: string,
  ids?: string[],
  performance?: string | null,
) {
  return invoke<DownloadCompanionsResult>("download_model_companions", {
    model,
    ids: ids ?? null,
    performance: performance ?? null,
  });
}

export async function downloadModel(params: {
  url: string;
  category: string;
  filename: string;
  apiKey?: string | null;
  minBytes?: number | null;
}) {
  return invoke<void>("download_model", params);
}

export type ReleaseStatus = {
  current: string;
  latest: string;
  update_available: boolean;
  release_url: string;
  published_at?: string;
};

export async function getReleaseStatus() {
  return invoke<ReleaseStatus>("get_release_status");
}

export function onDownloadProgress(cb: (payload: DownloadProgressPayload) => void) {
  return listen<DownloadProgressPayload>("download-progress", (e) => cb(e.payload));
}

export function onDownloadComplete(cb: (payload: DownloadProgressPayload) => void) {
  return listen<DownloadProgressPayload>("download-complete", (e) => cb(e.payload));
}
