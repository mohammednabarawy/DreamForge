import type { GenerationSettings } from "./tauri-api";
import { CUSTOM_PERFORMANCE } from "./generationSettingsUi";
import {
  UPSCALE_BY_DEFAULT,
  UPSCALE_DENOISE_DEFAULT,
  UPSCALE_TILE_DEFAULT,
} from "./upscaleDefaults";

export type UpscalePresetId = "1.5x" | "2x" | "fast_2x";

export const UPSCALE_PRESETS: Array<{
  id: UpscalePresetId;
  label: string;
  short: string;
  hint: string;
}> = [
  {
    id: "1.5x",
    label: "Upscale 1.5×",
    short: "1.5×",
    hint: "Moderate upscale with Ultimate SD tiling.",
  },
  {
    id: "2x",
    label: "Upscale 2×",
    short: "2×",
    hint: "Default quality upscale (recommended).",
  },
  {
    id: "fast_2x",
    label: "Fast 2×",
    short: "Fast 2×",
    hint: "2× with fewer steps and smaller tiles for quicker results.",
  },
];

const PRESET_PATCHES: Record<UpscalePresetId, Partial<GenerationSettings>> = {
  "1.5x": {
    upscale_preset: "1.5x",
    upscale_by: 1.5,
    upscale_denoise: UPSCALE_DENOISE_DEFAULT,
    upscale_tile_width: UPSCALE_TILE_DEFAULT,
    upscale_tile_height: UPSCALE_TILE_DEFAULT,
    performance: CUSTOM_PERFORMANCE,
  },
  "2x": {
    upscale_preset: "2x",
    upscale_by: UPSCALE_BY_DEFAULT,
    upscale_denoise: UPSCALE_DENOISE_DEFAULT,
    upscale_tile_width: UPSCALE_TILE_DEFAULT,
    upscale_tile_height: UPSCALE_TILE_DEFAULT,
    performance: CUSTOM_PERFORMANCE,
  },
  fast_2x: {
    upscale_preset: "fast_2x",
    upscale_by: 2,
    upscale_denoise: 0.2,
    upscale_tile_width: 768,
    upscale_tile_height: 768,
    steps: 12,
    performance: CUSTOM_PERFORMANCE,
  },
};

export function normalizeUpscalePreset(
  value: string | undefined | null,
): UpscalePresetId | undefined {
  const key = (value ?? "").trim().toLowerCase();
  if (key === "1.5x" || key === "2x" || key === "fast_2x") return key;
  return undefined;
}

export function patchForUpscalePreset(
  preset: UpscalePresetId,
): Partial<GenerationSettings> {
  return { ...PRESET_PATCHES[preset] };
}

export function inferUpscalePreset(
  settings: GenerationSettings,
): UpscalePresetId | undefined {
  const explicit = normalizeUpscalePreset(settings.upscale_preset);
  if (explicit) return explicit;
  const by = settings.upscale_by ?? UPSCALE_BY_DEFAULT;
  const steps = settings.steps ?? 20;
  const tile = settings.upscale_tile_width ?? UPSCALE_TILE_DEFAULT;
  if (by === 1.5) return "1.5x";
  if (by === 2 && steps <= 12 && tile <= 768) return "fast_2x";
  if (by === 2) return "2x";
  return undefined;
}

export function applyUpscalePresetAtSubmit(
  settings: GenerationSettings,
): GenerationSettings {
  const preset = normalizeUpscalePreset(settings.upscale_preset);
  if (!preset) return settings;
  return {
    ...settings,
    ...patchForUpscalePreset(preset),
  };
}
