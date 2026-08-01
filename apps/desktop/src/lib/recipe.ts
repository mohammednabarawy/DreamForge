import type { GenerationSettings } from "./tauri-api";
import { CUSTOM_PERFORMANCE } from "./generationSettingsUi";
import { isVramProfile } from "./vramProfiles";

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

const finite = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value);

export function settingsPatchFromRecipe(value: unknown): Partial<GenerationSettings> {
  if (!isRecord(value) || value.schema_version !== "2.0") {
    throw new Error("This is not a DreamForge Recipe v2 file.");
  }
  const patch: Partial<GenerationSettings> = {};
  if (typeof value.model === "string" && value.model.trim()) patch.model = value.model;
  if (typeof value.positive_prompt === "string") patch.prompt = value.positive_prompt;
  if (typeof value.negative_prompt === "string") patch.negative_prompt = value.negative_prompt;
  if (finite(value.seed) && Number.isInteger(value.seed)) patch.seed = value.seed;
  if (typeof value.sampler === "string" && value.sampler.trim()) patch.sampler = value.sampler;
  if (finite(value.cfg_scale) && value.cfg_scale > 0 && value.cfg_scale <= 100) patch.cfg_scale = value.cfg_scale;
  if (finite(value.steps) && Number.isInteger(value.steps) && value.steps > 0 && value.steps <= 1000) patch.steps = value.steps;
  if (typeof value.aspect_ratio === "string" && value.aspect_ratio.trim()) patch.aspect_ratio = value.aspect_ratio.replace("×", "x");
  if (typeof value.performance === "string" && value.performance.trim()) {
    patch.performance = value.performance;
  } else if (
    (finite(value.cfg_scale) && value.cfg_scale > 0)
    || (finite(value.steps) && value.steps > 0)
    || (typeof value.sampler === "string" && value.sampler.trim())
    || (isRecord(value.settings) && typeof value.settings.scheduler === "string" && value.settings.scheduler.trim())
  ) {
    patch.performance = CUSTOM_PERFORMANCE;
  }
  if (Array.isArray(value.styles)) patch.styles = value.styles.filter((item): item is string => typeof item === "string");
  if (Array.isArray(value.loras)) {
    patch.lora = value.loras
      .filter(isRecord)
      .filter((item) => typeof item.filename === "string" && item.filename.trim())
      .map((item) => `${item.filename}:${finite(item.weight) && item.weight >= -5 && item.weight <= 5 ? item.weight : 1}`);
  }
  if (isRecord(value.settings)) {
    const settings = value.settings;
    if (typeof settings.scheduler === "string" && settings.scheduler.trim()) patch.scheduler = settings.scheduler;
    if (finite(settings.width) && Number.isInteger(settings.width) && settings.width >= 64 && settings.width <= 16384) patch.width = settings.width;
    if (finite(settings.height) && Number.isInteger(settings.height) && settings.height >= 64 && settings.height <= 16384) patch.height = settings.height;
    if (isVramProfile(String(settings.vram_profile))) {
      patch.vram_profile = settings.vram_profile as GenerationSettings["vram_profile"];
    }
  }
  return patch;
}
