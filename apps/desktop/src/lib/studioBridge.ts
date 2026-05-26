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
  mode: "local" | "cloud" | "custom";
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
    cloud_confirmation_required: boolean;
    allow_cloud_image_context: boolean;
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

export async function writeTempPng(dataUrl: string) {
  return invoke<string>("write_temp_png", { dataBase64: dataUrl });
}
