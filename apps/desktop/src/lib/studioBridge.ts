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
    studio_mode: "generate" | "edit" | "inpaint" | "upscale" | "agent";
    advanced_mode: boolean;
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

export type AttachedReferencePack = {
  id?: string;
  name?: string;
  type?: string;
  tags?: string[];
  preferred_use_cases?: string[];
};

export type AttachedIdentityReference = {
  id?: string;
  name?: string;
  type?: string;
  tags?: string[];
  embedding_status?: string;
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
  reference_pack?: AttachedReferencePack;
  identity_reference?: AttachedIdentityReference;
  workflow_plan?: Array<{
    id?: string;
    operation?: string;
    mode?: string;
    params?: Record<string, unknown>;
  }>;
  workflow_blueprint?: Record<string, unknown>;
  readiness?: WorkflowReadiness;
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
  reference_pack?: AttachedReferencePack;
  identity_reference?: AttachedIdentityReference;
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

export type ReferencePack = {
  id: string;
  name: string;
  type: "person" | "character" | "product" | "brand" | "style";
  image_paths: string[];
  tags: string[];
  notes?: string;
  preferred_use_cases: string[];
  created_at?: string;
  updated_at?: string;
};

export type IdentityRecord = {
  id: string;
  name: string;
  type: "person" | "character" | "product" | "brand" | "style" | "location";
  image_paths: string[];
  reference_pack_ids: string[];
  tags: string[];
  notes?: string;
  metadata?: Record<string, unknown>;
  embeddings?: Record<string, unknown>;
  embedding_status?: string;
  created_at?: string;
  updated_at?: string;
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

export async function listReferencePacks() {
  const res = await bridgeInvoke<{ packs: ReferencePack[] }>(
    "list_reference_packs",
  );
  return res.packs ?? [];
}

export async function saveReferencePack(pack: Partial<ReferencePack> & { name: string }) {
  const res = await bridgeInvoke<{ pack: ReferencePack }>(
    "save_reference_pack",
    pack,
  );
  return res.pack;
}

export async function deleteReferencePack(id: string) {
  const res = await bridgeInvoke<{ deleted: boolean }>(
    "delete_reference_pack",
    { id },
  );
  return res.deleted;
}

export async function listIdentities(query = "", type = "") {
  const res = await bridgeInvoke<{ identities: IdentityRecord[] }>(
    "list_identities",
    { query, type },
  );
  return res.identities ?? [];
}

export async function saveIdentity(identity: Partial<IdentityRecord> & { name: string }) {
  const res = await bridgeInvoke<{ identity: IdentityRecord }>(
    "save_identity",
    identity,
  );
  return res.identity;
}

export async function deleteIdentity(id: string) {
  const res = await bridgeInvoke<{ deleted: boolean }>(
    "delete_identity",
    { id },
  );
  return res.deleted;
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
