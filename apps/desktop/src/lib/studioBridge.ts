import { invoke } from "@tauri-apps/api/core";
import type { GenerationSettings, ModelGalleryItem } from "./tauri-api";

export type StudioSettings = {
  path_checkpoints?: string;
  path_loras?: string;
  path_outputs?: string;
  path_inbox?: string;
  archive_folders?: string;
  images_per_page?: number;
  image_number_max?: number;
  auto_negative_prompt?: boolean;
  clip_skip?: number;
  seed_random?: boolean;
  lora_min?: number;
  lora_max?: number;
};

export type LoraInfo = {
  name: string;
  keywords: string;
  default_weight: number;
};

export type ImageLibraryPage = {
  items: string[];
  page: number;
  pages: number;
  total: number;
  range_text?: string;
};

export type AgentProviderPreset = {
  id: string;
  label: string;
  mode: "local";
  base_url: string;
  default_model: string;
  requires_api_key: boolean;
  test_kind: string;
};

export type DreamForgeAppConfig = {
  agent: {
    provider: string;
    base_url: string;
    model: string;
    api_key?: string;
    api_key_configured?: boolean;
    api_key_tail?: string;
    custom_instructions: string;
    approval_required: boolean;
    auto_configure_workflows: boolean;
    clear_api_key?: boolean;
  };
  privacy: {
    cloud_confirmation_required?: boolean;
    allow_cloud_image_context?: boolean;
  };
  ui: {
    studio_mode: "generate" | "edit" | "inpaint" | "upscale" | "extract" | "agent";
    experience: "simple" | "pro";
    advanced_mode: boolean;
    auto_enhance_on_generate?: boolean;
    enhance_strength?: "minimal" | "balanced" | "rich";
    use_flufferizer?: boolean;
    civitai_api_key?: string;
    civitai_api_key_configured?: boolean;
    civitai_api_key_tail?: string;
  };
};

export type DreamForgeAppConfigPatch = {
  agent?: Partial<DreamForgeAppConfig["agent"]>;
  privacy?: Partial<DreamForgeAppConfig["privacy"]>;
  ui?: Partial<DreamForgeAppConfig["ui"]>;
};

export type AgentProviderTestResult = {
  ok: boolean;
  provider: string;
  model: string;
  latency_ms: number;
  detail: string;
};

export type WorkflowReadiness = {
  ready?: boolean;
  missing_inputs?: string[];
  missing_models?: string[];
  missing_node_packs?: string[];
  optional_nodes?: string[];
  recommended_actions?: Array<Record<string, unknown>>;
  warnings?: string[];
};

export type DynamicPresetMeta = {
  schema_version?: string;
  source?: string[];
  applied?: Record<string, unknown>;
};

export type ModeContract = {
  schema_version?: string;
  mode?: string;
  model_policy?: string;
  model_source?: string;
  selected_model?: string;
  changed_fields?: string[];
  preserved_fields?: string[];
  preservation_hints?: string[];
  summary?: string;
};

export type AgentPlanSnapshot = {
  source?: string;
  provider?: string;
  message?: string;
  mode?: AgentPlanResult["mode"];
  /** Fingerprint of settings used when the plan was built (edit-family freshness). */
  settings_snapshot?: string;
  applied?: Partial<GenerationSettings>;
  proposed?: Partial<GenerationSettings>;
  actions?: string[];
  downloads?: string[];
  operations?: string[];
  dynamic_preset?: DynamicPresetMeta;
  mode_contract?: ModeContract;
  workflow_plan?: Array<{
    id?: string;
    operation?: string;
    mode?: string;
    params?: Record<string, unknown>;
  }>;
  workflow_blueprint?: Record<string, unknown>;
  readiness?: WorkflowReadiness;
  escalation_reason?: string;
};

export type AgentTranscriptMessage = {
  id: string;
  role: "user" | "assistant" | "system";
  text: string;
  created_at: string;
  source?: string;
  mode?: AgentPlanResult["mode"];
  actions?: string[];
  status?: "planned" | "applied" | "error";
};

export type AgentPlanResult = {
  ok?: boolean;
  source: "provider" | "local";
  provider?: string;
  provider_model?: string;
  message: string;
  mode: "generate" | "edit" | "inpaint" | "upscale" | "extract" | "agent";
  patch: Partial<GenerationSettings>;
  actions: string[];
  downloads: string[];
  workflow_plan?: AgentPlanSnapshot["workflow_plan"];
  workflow_blueprint?: Record<string, unknown>;
  readiness?: WorkflowReadiness;
  operations?: string[];
  dynamic_preset?: DynamicPresetMeta;
  mode_contract?: ModeContract;
};

type BridgeOk<T> = { ok?: boolean; error?: string } & T;

export async function bridgeInvoke<T>(
  cmd: string,
  params: Record<string, unknown> = {},
): Promise<T> {
  const res = await invoke<BridgeOk<T>>("bridge_invoke", { cmd, params });
  if (res.ok === false && res.error) {
    throw new Error(res.error);
  }
  return res as T;
}

export async function getStudioSettings() {
  const res = await bridgeInvoke<{ settings: StudioSettings }>(
    "get_studio_settings",
  );
  return res.settings;
}

export async function saveStudioSettings(settings: StudioSettings) {
  return bridgeInvoke<{ ok: boolean }>("save_studio_settings", { settings });
}

export async function getAppConfig() {
  const res = await bridgeInvoke<{ config: DreamForgeAppConfig }>(
    "get_app_config",
  );
  return res.config;
}

export async function saveAppConfig(config: DreamForgeAppConfigPatch) {
  const res = await bridgeInvoke<{ config: DreamForgeAppConfig }>(
    "save_app_config",
    { config },
  );
  return res.config;
}

export async function listAgentProviders() {
  const res = await bridgeInvoke<{ providers: AgentProviderPreset[] }>(
    "list_agent_providers",
  );
  return res.providers ?? [];
}

export async function testAgentProvider(config?: DreamForgeAppConfigPatch | DreamForgeAppConfig) {
  return bridgeInvoke<AgentProviderTestResult>("test_agent_provider", {
    config,
  });
}

export async function planAgentInstruction(params: {
  instruction: string;
  settings: GenerationSettings;
  selected_image?: string;
  model_gallery?: ModelGalleryItem[];
}) {
  return bridgeInvoke<AgentPlanResult>("agent_plan", params);
}

export async function getLoraInfo(name: string) {
  return bridgeInvoke<LoraInfo>("get_lora_info", { name });
}

export async function aggregateLoraKeywords(lora: string[]) {
  const res = await bridgeInvoke<{ keywords: string }>(
    "aggregate_lora_keywords",
    { lora },
  );
  return res.keywords ?? "";
}

export async function applyStylesToPrompt(params: {
  styles: string[];
  prompt: string;
  negative_prompt?: string;
  lora_keywords?: string;
}) {
  return bridgeInvoke<{ prompt: string; negative_prompt: string }>(
    "apply_styles_to_prompt",
    params,
  );
}

export async function listWildcards() {
  const res = await bridgeInvoke<{ wildcards: string[] }>("list_wildcards");
  return res.wildcards ?? [];
}

export async function matchWildcards(text: string) {
  const res = await bridgeInvoke<{ matches: string[] }>("match_wildcards", {
    text,
  });
  return res.matches ?? [];
}

export async function browseImages(page: number, search = "") {
  return bridgeInvoke<ImageLibraryPage>("browse_images", { page, search });
}

export async function imageBrowserMetadata(path: string) {
  return bridgeInvoke<{ metadata: Record<string, unknown>; text: string }>(
    "image_browser_metadata",
    { path },
  );
}

export async function reindexImageLibrary() {
  return bridgeInvoke<ImageLibraryPage>("image_browser_reindex");
}

export async function randomOnebuttonPrompt() {
  const res = await bridgeInvoke<{ prompt: string }>("random_onebutton_prompt");
  return res.prompt ?? "";
}

export async function evolvePrompts(params: {
  prompt: string;
  mode?: string;
  strength?: number;
}) {
  const res = await bridgeInvoke<{ variants: string[] }>("evolve_prompts", params);
  return res.variants ?? [];
}

export type EnhanceStudioPromptResult = {
  ok?: boolean;
  error?: string;
  prompt?: string;
  negative_prompt?: string;
  hint?: string;
  prompt_enhancer?: string;
  model_family?: string;
  studio_mode?: string;
  prompt_format?: string;
  magic_prompt_source?: string;
  enhance_strength?: string;
  enhance_purpose?: string;
};

export async function enhanceStudioPrompt(
  params: Record<string, unknown> & { studio_mode: string },
) {
  return bridgeInvoke<EnhanceStudioPromptResult>("enhance_studio_prompt", params);
}

export type ValidateIdeogram4CaptionResult = {
  ok: boolean;
  errors: string[];
  normalized?: string | null;
};

export type RenderIdeogram4CaptionTemplateResult = ValidateIdeogram4CaptionResult & {
  caption?: string | null;
  template?: { id?: string; label?: string; aspect_ratio?: string };
};

export async function validateIdeogram4Caption(prompt: string) {
  return bridgeInvoke<ValidateIdeogram4CaptionResult>("validate_ideogram4_caption", {
    prompt,
  });
}

export async function buildIdeogram4CaptionFromLayout(params: {
  aspect_ratio: string;
  high_level_description: string;
  background?: string;
  elements: Array<Record<string, unknown>>;
  style_description?: Record<string, unknown>;
}) {
  return bridgeInvoke<ValidateIdeogram4CaptionResult>(
    "build_ideogram4_caption_from_layout",
    params,
  );
}

export type Ideogram4CaptionTemplate = {
  id: string;
  label: string;
  description?: string;
  aspect_ratio?: string;
};

export async function listIdeogram4CaptionTemplates() {
  const res = await bridgeInvoke<{ templates: Ideogram4CaptionTemplate[] }>(
    "list_ideogram4_caption_templates",
    {},
  );
  return res.templates ?? [];
}

export async function renderIdeogram4CaptionTemplate(params: {
  template_id: string;
  aspect_ratio?: string;
}) {
  return bridgeInvoke<RenderIdeogram4CaptionTemplateResult>(
    "render_ideogram4_caption_template",
    params,
  );
}

export async function interrogateImage(path: string, prompt?: string) {
  return bridgeInvoke<{ prompt?: string; gallery?: unknown }>(
    "interrogate_image",
    { path, prompt },
  );
}

export type StudioResourceItem = {
  id?: string;
  relative?: string;
  url?: string;
  filename?: string;
  category?: string;
  expected_path?: string;
  note?: string;
};

export async function checkStudioResources(
  studioMode: string,
  upscaleMethod?: string,
) {
  return bridgeInvoke<{
    missing: StudioResourceItem[];
    ready: boolean;
    studio_mode: string;
  }>("check_studio_resources", {
    studio_mode: studioMode,
    upscale_method: upscaleMethod ?? null,
  });
}

export async function checkImagePromptResources() {
  return bridgeInvoke<{
    missing: StudioResourceItem[];
    ready: boolean;
  }>("check_image_prompt_resources", {});
}

/**
 * Re-classify a just-downloaded model and move it to its canonical ComfyUI
 * folder (e.g. diffusion-only Krea 2 / Flux UNet files land in checkpoints/ but
 * must live under diffusion_models/). Safe no-op when already correct.
 */
export async function relocateDownloadedModel(args: {
  path?: string;
  category?: string;
  filename?: string;
}) {
  return bridgeInvoke<{
    ok: boolean;
    moved?: boolean;
    family?: string;
    role?: string;
    category?: string;
    destination?: string;
    reason?: string;
    error?: string;
  }>("relocate_downloaded_model", {
    path: args.path ?? null,
    category: args.category ?? null,
    filename: args.filename ?? null,
  });
}

export async function downloadStudioResources(
  studioMode: string,
  upscaleMethod?: string,
) {
  return bridgeInvoke<{
    status?: string;
    downloaded?: number;
    errors?: Array<{ id?: string; error?: string }>;
  }>("download_studio_resources", {
    studio_mode: studioMode,
    upscale_method: upscaleMethod ?? null,
  });
}

export async function downloadCompanionEntries(
  items: StudioResourceItem[],
) {
  return bridgeInvoke<{
    ok?: boolean;
    status?: string;
    error?: string;
    downloaded?: number;
    skipped?: number;
    results?: Array<{ status?: string; id?: string; path?: string }>;
    errors?: Array<{ id?: string; relative?: string; error?: string }>;
  }>("download_companion_entries", { items });
}

export async function verifyCompanionEntries(items: StudioResourceItem[]) {
  return bridgeInvoke<{
    ok?: boolean;
    ready: boolean;
    present?: StudioResourceItem[];
    missing?: StudioResourceItem[];
  }>("verify_companion_entries", { items });
}

export type EnsureCreativeTaskReadyResult = {
  ok?: boolean;
  ready?: boolean;
  missing?: StudioResourceItem[];
  missing_tier_a?: StudioResourceItem[];
  missing_tier_b?: StudioResourceItem[];
  missing_node_packs?: StudioResourceItem[];
  downloaded_tier_a?: number;
  downloaded_tier_b?: number;
  downloaded?: number;
  node_setup?: string[];
  errors?: Array<{ id?: string; relative?: string; error?: string }>;
  model?: string;
  studio_mode?: string;
};

export async function installCustomNodePacks(packIds: string[]) {
  return bridgeInvoke<{
    ok?: boolean;
    ready?: boolean;
    installed?: string[];
    packs?: Array<{
      pack_id?: string;
      ready?: boolean;
      missing_nodes?: string[];
      directory_present?: boolean;
    }>;
    errors?: Array<{ pack_id?: string; error?: string }>;
    messages?: string[];
  }>("install_custom_node_packs", { pack_ids: packIds });
}

export async function ensureCreativeTaskReady(args: {
  model?: string;
  studio_mode?: string;
  upscale_method?: string | null;
  performance?: string | null;
  auto_download_tier_a?: boolean;
  auto_download_tier_b?: boolean;
  auto_install_nodes?: boolean;
  template_id?: string | null;
}) {
  return bridgeInvoke<EnsureCreativeTaskReadyResult>("ensure_creative_task_ready", {
    model: args.model ?? null,
    studio_mode: args.studio_mode ?? null,
    upscale_method: args.upscale_method ?? null,
    performance: args.performance ?? null,
    auto_download_tier_a: args.auto_download_tier_a ?? true,
    auto_download_tier_b: args.auto_download_tier_b ?? false,
    auto_install_nodes: args.auto_install_nodes ?? false,
    template_id: args.template_id ?? null,
  });
}

export type ResolveCreativeTaskResult = {
  ok?: boolean;
  studio_mode?: string;
  template_id?: string;
  post_upscale?: string;
  patch?: GenerationSettings;
  changed?: Partial<GenerationSettings>;
  model?: string;
  vram_tier?: string;
};

export type CreativeTemplateSummary = {
  id: string;
  label: string;
  studio_mode?: string | null;
  post_upscale?: string;
  companions?: string[];
};

export async function listCreativeTemplates(studioMode?: string) {
  const res = await bridgeInvoke<{ templates: CreativeTemplateSummary[] }>(
    "list_creative_templates",
    { studio_mode: studioMode ?? null },
  );
  return res.templates ?? [];
}

export async function resolveCreativeTemplate(args: {
  template_id: string;
  settings?: GenerationSettings;
  vram_profile?: string | null;
  post_upscale_enabled?: boolean;
}) {
  return bridgeInvoke<{
    ok?: boolean;
    template_id?: string;
    patch?: GenerationSettings;
    post_upscale?: string;
    companions?: string[];
  }>("resolve_creative_template", {
    template_id: args.template_id,
    settings: args.settings ?? {},
    vram_profile: args.vram_profile ?? null,
    post_upscale_enabled: args.post_upscale_enabled ?? false,
  });
}

export type AutomationPreview = {
  ok?: boolean;
  type?: string;
  job_count?: number;
  jobs?: Array<{ index?: number; label?: string }>;
};

export async function previewAutomation(spec: Record<string, unknown>) {
  return bridgeInvoke<AutomationPreview>("preview_automation", { spec });
}

export async function runAutomation(spec: Record<string, unknown>) {
  return bridgeInvoke<{
    ok?: boolean;
    status?: string;
    automation_id?: string;
    completed?: number;
    total?: number;
    output_dir?: string | null;
    results?: Array<Record<string, unknown>>;
    error?: Record<string, unknown>;
    failed_at?: number;
  }>("run_automation", { spec });
}

export async function resolveCreativeTask(args: {
  studio_mode: string;
  settings?: GenerationSettings;
  model_gallery?: ModelGalleryItem[];
  vram_profile?: string | null;
  advanced_mode?: boolean;
  user_picked_model?: boolean;
  selected_image?: string;
  enforce?: boolean;
  template_id?: string;
}) {
  return bridgeInvoke<ResolveCreativeTaskResult>("resolve_creative_task", {
    studio_mode: args.studio_mode,
    settings: args.settings ?? {},
    model_gallery: args.model_gallery ?? [],
    vram_profile: args.vram_profile ?? null,
    advanced_mode: args.advanced_mode ?? false,
    user_picked_model: args.user_picked_model ?? false,
    selected_image: args.selected_image ?? "",
    enforce: args.enforce ?? false,
    template_id: args.template_id ?? null,
  });
}

export type UserStyleProfile = {
  enabled: boolean;
  favorite_models: string[];
  favorite_styles: string[];
  aspect_ratios: string[];
  workflow_modes: string[];
  generation_count: number;
};

export type UserStyleProfileExport = {
  status: string;
  profile: UserStyleProfile;
  path: string;
};

export async function getUserStyleProfile() {
  const res = await bridgeInvoke<UserStyleProfileExport>(
    "get_user_style_profile",
  );
  return res;
}

export async function saveUserStyleProfile(
  patch: Partial<UserStyleProfile> & { enabled?: boolean },
) {
  const current = await getUserStyleProfile();
  const profile = { ...current.profile, ...patch };
  return bridgeInvoke<{ status: string; profile: UserStyleProfile }>(
    "save_user_style_profile",
    { profile },
  );
}

export async function clearUserStyleProfile() {
  return bridgeInvoke<{ status: string; profile: UserStyleProfile }>(
    "clear_user_style_profile",
  );
}

export async function exportUserStyleProfile() {
  return bridgeInvoke<UserStyleProfileExport>("export_user_style_profile");
}

export async function writeTempPng(dataUrl: string) {
  return invoke<string>("write_temp_png", { dataBase64: dataUrl });
}

export type InpaintSelectionKind =
  | "subject"
  | "background"
  | "person"
  | "clothes"
  | "face"
  | "eyes"
  | "hands"
  | "legs"
  | "feet"
  | "tap_object"
  | "tap_background";

export type InpaintSelectionResult = {
  ok: boolean;
  mask_path?: string;
  selection?: string;
  method?: string;
  coverage?: number;
  error?: string;
};

export async function generateInpaintSelectionMask(args: {
  imagePath: string;
  selection: InpaintSelectionKind;
  tapX?: number;
  tapY?: number;
}) {
  return bridgeInvoke<InpaintSelectionResult>(
    "generate_inpaint_selection_mask",
    {
      image_path: args.imagePath,
      selection: args.selection,
      tap_x: args.tapX,
      tap_y: args.tapY,
    },
  );
}
