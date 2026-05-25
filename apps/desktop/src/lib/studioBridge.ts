import { invoke } from "@tauri-apps/api/core";

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
