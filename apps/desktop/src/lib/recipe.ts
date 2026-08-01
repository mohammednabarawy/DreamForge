import type { GenerationSettings } from "./tauri-api";

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

export function settingsPatchFromRecipe(value: unknown): Partial<GenerationSettings> {
  if (!isRecord(value) || value.schema_version !== "2.0") {
    throw new Error("This is not a DreamForge Recipe v2 file.");
  }
  const patch: Partial<GenerationSettings> = {};
  if (typeof value.model === "string") patch.model = value.model;
  if (typeof value.positive_prompt === "string") patch.prompt = value.positive_prompt;
  if (typeof value.negative_prompt === "string") patch.negative_prompt = value.negative_prompt;
  if (typeof value.seed === "number") patch.seed = value.seed;
  if (typeof value.sampler === "string") patch.sampler = value.sampler;
  if (typeof value.cfg_scale === "number") patch.cfg_scale = value.cfg_scale;
  if (typeof value.steps === "number") patch.steps = value.steps;
  if (typeof value.aspect_ratio === "string") patch.aspect_ratio = value.aspect_ratio;
  if (typeof value.performance === "string") patch.performance = value.performance;
  if (Array.isArray(value.styles)) patch.styles = value.styles.filter((item): item is string => typeof item === "string");
  if (Array.isArray(value.loras)) {
    patch.lora = value.loras
      .filter(isRecord)
      .filter((item) => typeof item.filename === "string" && item.filename.trim())
      .map((item) => `${item.filename}:${typeof item.weight === "number" ? item.weight : 1}`);
  }
  if (isRecord(value.settings)) {
    const settings = value.settings;
    if (typeof settings.scheduler === "string") patch.scheduler = settings.scheduler;
    if (typeof settings.width === "number") patch.width = settings.width;
    if (typeof settings.height === "number") patch.height = settings.height;
    if (typeof settings.vram_profile === "string") {
      patch.vram_profile = settings.vram_profile as GenerationSettings["vram_profile"];
    }
  }
  return patch;
}
