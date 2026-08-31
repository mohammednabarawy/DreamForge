import { invoke } from "@tauri-apps/api/core";
import type { GenerationSettings, ModelDependencyItem, ModelGalleryItem } from "./tauri-api";

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
    studio_mode: "generate" | "edit" | "inpaint" | "upscale" | "toolbox" | "agent";
    experience: "simple" | "pro";
    advanced_mode: boolean;
    auto_enhance_on_generate?: boolean;
    enhance_strength?: "minimal" | "balanced" | "rich";
    use_flufferizer?: boolean;
    civitai_api_key?: string;
    civitai_api_key_configured?: boolean;
    civitai_api_key_tail?: string;
    /** Last selected Creative Toolbox custom tool (survives app restart). */
    selected_custom_tool_id?: string;
  };
  custom_tools?: Array<{
    id: string;
    name: string;
    description: string;
    workflow_path: string;
    source_workflow_path?: string;
    workflow_sha256?: string;
    workflow_format?: "ui" | "api";
    managed_workflow_version?: number;
    bindings: Record<string, any>;
    model_overrides?: Record<string, string>;
  }>;
};

export type DreamForgeAppConfigPatch = {
  agent?: Partial<DreamForgeAppConfig["agent"]>;
  privacy?: Partial<DreamForgeAppConfig["privacy"]>;
  ui?: Partial<DreamForgeAppConfig["ui"]>;
  custom_tools?: DreamForgeAppConfig["custom_tools"];
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

export type InpaintContextPlan = {
  schema_version?: string;
  status?: string;
  message?: string;
  image_size?: number[];
  mask_empty?: boolean;
  mask_bbox?: number[];
  mask_coverage?: number;
  mask_selected_pixels?: number;
  crop?: {
    enabled?: boolean;
    box?: number[];
    size?: number[];
  };
  requires_mask?: boolean;
  outpaint?: {
    direction?: string;
    amount?: number;
    feathering?: number;
  };
};

export type FinalEditRequestPlan = {
  schema_version?: string;
  mode?: string;
  task?: string;
  task_hint?: string;
  scope?: string;
  user_instruction?: string;
  model_instruction?: string;
  negative_prompt?: string;
};

export type EditTaskDefaultsPlan = {
  edit_task?: string;
  label?: string;
  hint?: string;
  scope?: string;
  requires_mask?: boolean;
  inpaint_intent?: string;
  edit_strength?: number;
};

export type ModelCapabilitiesPlan = {
  schema_version?: string;
  family?: string;
  required?: string[];
  supported?: string[];
  missing?: string[];
  compatible?: boolean;
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
  inpaint_context?: InpaintContextPlan;
  final_edit_request?: FinalEditRequestPlan;
  edit_task_defaults?: EditTaskDefaultsPlan;
  model_capabilities?: ModelCapabilitiesPlan;
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
  mode: "generate" | "edit" | "inpaint" | "upscale" | "agent";
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

export type IdentityFaceAnalysis = {
  ok: boolean;
  count: number;
  detector?: string;
  error?: string;
  faces: Array<{
    index: number;
    x: number;
    y: number;
    width: number;
    height: number;
    recommended?: boolean;
  }>;
};

export async function importFooocusStyles(styles: unknown) {
  return bridgeInvoke<{ ok: boolean; count?: number; error?: string }>(
    "import_fooocus_styles",
    { styles },
  );
}

export async function deleteCustomStyle(styleId: string) {
  return bridgeInvoke<{ ok: boolean; removed?: number; error?: string }>(
    "delete_custom_style",
    { style_id: styleId },
  );
}

export type DiscoverWorkflowTemplate = {
  id: string;
  label: string;
  operation: string;
  mode: string;
  summary: string;
  builder: string;
  node_pattern?: string[];
  required_inputs?: string[];
  required_models?: string[];
  required_node_packs?: string[];
  security_note?: string;
  url?: string;
  thumbnail_url?: string;
  source?: string;
};

export async function listWorkflowTemplates() {
  return bridgeInvoke<{
    ok: boolean;
    templates?: DiscoverWorkflowTemplate[];
    error?: string;
  }>("list_workflow_templates", {});
}

export type WorkflowCompatibilityReport = {
  ok: boolean;
  state?: "NATIVE" | "ADAPTABLE" | "COMFY_ONLY" | "INVALID";
  format?: string;
  reason?: string;
  dependencies?: string[];
  security?: { safe?: boolean; blocked?: boolean; reasons?: string[] };
  error?: string;
};

export async function analyzeWorkflowCompatibility(path: string) {
  return bridgeInvoke<WorkflowCompatibilityReport>("analyze_workflow_compatibility", { path });
}

export type WorkflowRecipeCompileResult = {
  ok: boolean;
  can_recreate?: boolean;
  missing?: string[];
  recipe?: Record<string, unknown>;
  report?: WorkflowCompatibilityReport;
};

export async function compileWorkflowRecipe(path: string) {
  return bridgeInvoke<WorkflowRecipeCompileResult>("compile_workflow_recipe", { path });
}

export type WorkflowIRCompileResult = {
  ok: boolean;
  version?: string;
  can_execute?: boolean;
  kind?: string;
  source?: string;
  nodes?: string[];
  dependencies?: string[];
  recipe?: Record<string, unknown>;
  report?: WorkflowCompatibilityReport;
  missing?: string[];
};

export async function compileWorkflowIR(path: string) {
  return bridgeInvoke<WorkflowIRCompileResult>("compile_workflow_ir", { path });
}

export type WorkflowIndexItem = DiscoverWorkflowTemplate & {
  url?: string;
  thumbnail_url?: string;
  source?: string;
  category?: string;
  tags?: string[];
  open_source?: boolean;
};

export async function searchWorkflowIndex(url = "") {
  return bridgeInvoke<{ ok: boolean; items?: WorkflowIndexItem[]; count?: number; error?: string }>("workflow_index_search", { url });
}

export async function downloadWorkflow(url: string, filename?: string) {
  return bridgeInvoke<{ ok: boolean; path?: string; filename?: string; execution?: "disabled"; error?: string }>("workflow_download", { url, filename });
}

export type WorkflowSaveResult = {
  ok: boolean;
  path?: string;
  filename?: string;
  execution?: "disabled";
  report?: WorkflowCompatibilityReport;
  error?: string;
};

export async function saveWorkflowFile(path: string) {
  return bridgeInvoke<WorkflowSaveResult>("save_workflow_file", { path });
}

export type RecipeDiscoveryItem = {
  id: string;
  provider: string;
  title: string;
  image_url: string;
  source_url: string;
  recipe: Record<string, unknown>;
  completeness?: { score?: number; present?: string[]; missing?: string[] };
};

export type RecipeDiscoverySearchResult = {
  ok: boolean;
  query: string;
  page: number;
  limit: number;
  items: RecipeDiscoveryItem[];
  providers: Array<{
    provider: string;
    ok: boolean;
    items?: RecipeDiscoveryItem[];
    error?: string;
    error_code?: string;
    total?: number;
    next_cursor?: string;
  }>;
  provider_ok: number;
  provider_errors: number;
  next_cursor?: string;
};

export async function searchRecipeDiscovery(params: {
  query: string;
  provider?: "all" | "civitai_images" | "lexica";
  page?: number;
  limit?: number;
  nsfw?: boolean;
  cursor?: string;
}) {
  return bridgeInvoke<RecipeDiscoverySearchResult>("recipe_discovery_search", {
    query: params.query,
    provider: params.provider ?? "all",
    page: params.page ?? 1,
    limit: params.limit ?? 24,
    nsfw: params.nsfw ?? false,
    cursor: params.cursor ?? "",
  });
}

export async function saveRecipeToLibrary(recipeId: string, recipe: Record<string, unknown>) {
  return bridgeInvoke<{ ok: boolean; path?: string; filename?: string; error?: string }>(
    "recipe_save_library",
    { recipe_id: recipeId, recipe },
  );
}

export type RecipeLibraryItem = {
  filename: string;
  path: string;
  modified_at: number;
  recipe: Record<string, unknown>;
};

export async function listRecipeLibrary() {
  return bridgeInvoke<{ ok: boolean; root?: string; items: RecipeLibraryItem[]; error?: string }>("recipe_list_library");
}

export async function deleteRecipeFromLibrary(filename: string) {
  return bridgeInvoke<{ ok: boolean; filename?: string; error?: string }>("recipe_delete_library", { filename });
}

export type CivitaiRecipeResource = {
  id: string;
  kind: "model" | "lora" | "other";
  name: string;
  version_name: string;
  model_id: string;
  model_version_id: string;
  source_url: string;
  filename: string;
  download_url: string;
  sha256: string;
  local_engine_name: string;
  category: string;
  weight: number;
  downloadable: boolean;
  error: string;
};

export type RecipeResourceResolution = {
  ok: boolean;
  resources: CivitaiRecipeResource[];
  errors: Array<{ model_version_id: string; error: string }>;
};

export function resolveRecipeCivitaiResources(recipe: Record<string, unknown>) {
  return bridgeInvoke<RecipeResourceResolution>("recipe_resolve_civitai_resources", { recipe });
}

export function analyzeIdentityFaces(path: string): Promise<IdentityFaceAnalysis> {
  return bridgeInvoke<IdentityFaceAnalysis>("analyze_identity_faces", { path });
}

export type ModelOrganizationPlan = {
  ok: boolean;
  applied: boolean;
  models_root: string;
  summary: {
    total: number;
    to_move: number;
    ambiguous: number;
    skipped: number;
    needs_review: number;
  };
  actions: Array<{
    source: string;
    destination: string;
    will_move: boolean;
    skip_reason?: string | null;
  }>;
  errors: string[];
  result?: {
    moved: Array<{ source: string; destination: string }>;
    failed: Array<{ source: string; destination: string; error?: string }>;
    skipped: Array<{ source: string; reason?: string }>;
  };
};

export async function organizeModels(apply = false) {
  return bridgeInvoke<ModelOrganizationPlan>("organize_models", {
    apply,
    include_low_confidence: false,
  });
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

export async function interrogateImage(path: string, interrogator?: string) {
  return bridgeInvoke<{ ok?: boolean; prompt?: string; gallery?: unknown; error?: string }>(
    "interrogate_image",
    {
      path,
      ...(interrogator ? { interrogator } : {}),
    },
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
  model?: string,
) {
  return bridgeInvoke<{
    missing: StudioResourceItem[];
    ready: boolean;
    studio_mode: string;
  }>("check_studio_resources", {
    studio_mode: studioMode,
    upscale_method: upscaleMethod ?? null,
    model: model ?? null,
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
  model?: string,
) {
  return bridgeInvoke<{
    status?: string;
    downloaded?: number;
    errors?: Array<{ id?: string; error?: string }>;
  }>("download_studio_resources", {
    studio_mode: studioMode,
    upscale_method: upscaleMethod ?? null,
    model: model ?? null,
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

export async function installCustomNodePacks(
  packIds: string[],
  options?: {
    strategy?: "auto" | "pinned" | "manager";
    restart_comfy?: boolean;
    progress_file?: string;
  },
) {
  return bridgeInvoke<{
    ok?: boolean;
    ready?: boolean;
    installed?: string[];
    packs?: Array<{
      pack_id?: string;
      ready?: boolean;
      missing_nodes?: string[];
      directory_present?: boolean;
      install_via?: string;
    }>;
    errors?: Array<{ pack_id?: string; error?: string; code?: string; hint?: string }>;
    messages?: string[];
    needs_comfy_restart?: boolean;
  }>("install_custom_node_packs", {
    pack_ids: packIds,
    strategy: options?.strategy ?? "auto",
    restart_comfy: options?.restart_comfy ?? true,
    progress_file: options?.progress_file ?? null,
  });
}

export async function getManagerQueueStatus() {
  return bridgeInvoke<{
    ok?: boolean;
    error?: string;
    base_url?: string;
    status?: {
      total_count?: number;
      done_count?: number;
      in_progress_count?: number;
      is_processing?: boolean;
    };
  }>("get_manager_queue_status", {});
}

export async function checkWorkflowTaskDependencies(editTask?: string | null) {
  return bridgeInvoke<{
    ok?: boolean;
    ready?: boolean;
    missing?: ModelDependencyItem[];
  }>("check_workflow_task_dependencies", {
    edit_task: editTask ?? null,
  });
}

export async function installWorkflowModels(
  catalogIds: string[],
  options?: { prefer_manager?: boolean; progress_file?: string },
) {
  return bridgeInvoke<{
    ok?: boolean;
    ready?: boolean;
    installed?: string[];
    errors?: Array<{ pack_id?: string; error?: string; code?: string; hint?: string }>;
    messages?: string[];
  }>("install_workflow_models", {
    catalog_ids: catalogIds,
    prefer_manager: options?.prefer_manager ?? true,
    progress_file: options?.progress_file ?? null,
  });
}

export async function fetchCustomToolDependencies(toolId: string, useObjectInfo = true) {
  return bridgeInvoke<{
    ok?: boolean;
    ready?: boolean;
    missing?: ModelDependencyItem[];
    tool_id?: string;
    tool_name?: string;
    error?: string;
  }>("custom_tool_dependencies", {
    tool_id: toolId,
    use_object_info: useObjectInfo,
  });
}

export async function fetchCustomToolWorkflowModels(toolId: string) {
  return bridgeInvoke<{
    ok?: boolean;
    tool_id?: string;
    tool_name?: string;
    models?: Array<Record<string, unknown>>;
    error?: string;
  }>("custom_tool_workflow_models", {
    tool_id: toolId,
  });
}

export async function parseComfyWorkflowFile(path: string) {
  return bridgeInvoke<{
    ok?: boolean;
    api_format?: boolean;
    ui_format?: boolean;
    nodes?: Record<string, unknown>;
    class_types?: string[];
    repaired_nodes?: string[];
    ui_sibling?: string | null;
    warning?: string;
    error?: string;
  }>("parse_comfy_workflow", { path });
}

export async function importCustomToolWorkflow(path: string, toolId: string) {
  return bridgeInvoke<{
    ok?: boolean;
    workflow_path: string;
    source_workflow_path: string;
    workflow_sha256: string;
    workflow_format: "ui" | "api";
    managed_workflow_version: number;
    warning?: string;
    error?: string;
  }>("import_custom_tool_workflow", { path, tool_id: toolId });
}

export async function ensureCreativeTaskReady(args: {
  model?: string;
  studio_mode?: string;
  upscale_method?: string | null;
  performance?: string | null;
  edit_task?: string | null;
  custom_tool_id?: string | null;
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
    edit_task: args.edit_task ?? null,
    custom_tool_id: args.custom_tool_id ?? null,
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
  error?: string;
  message?: string;
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
  try {
    const res = await bridgeInvoke<{ path?: string; error?: string }>(
      "write_studio_mask_png",
      { data_base64: dataUrl },
    );
    if (res.path) return res.path;
    throw new Error(res.error || "write_studio_mask_png_missing_path");
  } catch (bridgeError) {
    try {
      return await invoke<string>("write_temp_png", { dataBase64: dataUrl });
    } catch {
      try {
        return await invoke<string>("write_temp_png", { data_base64: dataUrl });
      } catch {
        throw bridgeError;
      }
    }
  }
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
