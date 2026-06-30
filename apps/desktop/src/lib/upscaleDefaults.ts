import type { GenerationSettings } from "./tauri-api";
import { CUSTOM_PERFORMANCE } from "./generationSettingsUi";
import { UPSCALE_MODEL_DEFAULT } from "./upscaleNodeUi";
/** Proven Ultimate SD Upscale defaults (SDXL, 1024 tiles, Chess mode). */
export const UPSCALE_BY_DEFAULT = 2;
export const UPSCALE_DENOISE_DEFAULT = 0.25;
export const UPSCALE_TILE_DEFAULT = 1024;
export const UPSCALE_TILE_PADDING_DEFAULT = 64;
export const UPSCALE_MASK_BLUR_DEFAULT = 8;
export const UPSCALE_SEAM_FIX_MODE_DEFAULT = "None";
export const UPSCALE_MODE_TYPE_DEFAULT = "Chess";
export const UPSCALE_METHOD_DEFAULT = "ultimate_sd_upscale";

export const UPSCALE_STEPS_DEFAULT = 20;
export const UPSCALE_CFG_DEFAULT = 6;
export const UPSCALE_SAMPLER_DEFAULT = "euler";
export const UPSCALE_SCHEDULER_DEFAULT = "normal";
export const UPSCALE_SEAM_FIX_DENOISE_DEFAULT = 1;
export const UPSCALE_SEAM_FIX_WIDTH_DEFAULT = 64;
export const UPSCALE_SEAM_FIX_MASK_BLUR_DEFAULT = 8;
export const UPSCALE_SEAM_FIX_PADDING_DEFAULT = 16;
export const UPSCALE_FORCE_UNIFORM_TILES_DEFAULT = true;
export const UPSCALE_TILED_DECODE_DEFAULT = false;
export const UPSCALE_BATCH_SIZE_DEFAULT = 1;

/** Full patch applied when entering Enhance mode from another tab. */
export const UPSCALE_SETTINGS_DEFAULTS: Partial<GenerationSettings> = {
  style: "image_edit",
  edit_type: "auto",
  cn_selection: "Custom...",
  cn_type: "upscale",
  upscale_method: UPSCALE_METHOD_DEFAULT,
  upscale_by: UPSCALE_BY_DEFAULT,
  upscale_denoise: UPSCALE_DENOISE_DEFAULT,
  upscale_tile_width: UPSCALE_TILE_DEFAULT,
  upscale_tile_height: UPSCALE_TILE_DEFAULT,
  upscale_tile_padding: UPSCALE_TILE_PADDING_DEFAULT,
  upscale_mask_blur: UPSCALE_MASK_BLUR_DEFAULT,
  upscale_seam_fix_mode: UPSCALE_SEAM_FIX_MODE_DEFAULT,
  upscale_seam_fix_denoise: UPSCALE_SEAM_FIX_DENOISE_DEFAULT,
  upscale_seam_fix_width: UPSCALE_SEAM_FIX_WIDTH_DEFAULT,
  upscale_seam_fix_mask_blur: UPSCALE_SEAM_FIX_MASK_BLUR_DEFAULT,
  upscale_seam_fix_padding: UPSCALE_SEAM_FIX_PADDING_DEFAULT,
  upscale_force_uniform_tiles: UPSCALE_FORCE_UNIFORM_TILES_DEFAULT,
  upscale_tiled_decode: UPSCALE_TILED_DECODE_DEFAULT,
  upscale_mode_type: UPSCALE_MODE_TYPE_DEFAULT,
  cn_upscale: UPSCALE_MODEL_DEFAULT,
  batch_size: UPSCALE_BATCH_SIZE_DEFAULT,
  performance: CUSTOM_PERFORMANCE,
  steps: UPSCALE_STEPS_DEFAULT,
  cfg_scale: UPSCALE_CFG_DEFAULT,
  sampler: UPSCALE_SAMPLER_DEFAULT,
  scheduler: UPSCALE_SCHEDULER_DEFAULT,
};
/** Fill missing upscale fields without overwriting user overrides. */
export function applyUpscaleFallbacks(
  settings: GenerationSettings,
): Partial<GenerationSettings> {
  return {
    upscale_method: settings.upscale_method ?? UPSCALE_METHOD_DEFAULT,
    upscale_by: settings.upscale_by ?? UPSCALE_BY_DEFAULT,
    upscale_denoise: settings.upscale_denoise ?? UPSCALE_DENOISE_DEFAULT,
    upscale_tile_width: settings.upscale_tile_width ?? UPSCALE_TILE_DEFAULT,
    upscale_tile_height: settings.upscale_tile_height ?? UPSCALE_TILE_DEFAULT,
    upscale_tile_padding: settings.upscale_tile_padding ?? UPSCALE_TILE_PADDING_DEFAULT,
    upscale_mask_blur: settings.upscale_mask_blur ?? UPSCALE_MASK_BLUR_DEFAULT,
    upscale_seam_fix_mode: settings.upscale_seam_fix_mode ?? UPSCALE_SEAM_FIX_MODE_DEFAULT,
    upscale_mode_type: settings.upscale_mode_type ?? UPSCALE_MODE_TYPE_DEFAULT,
    upscale_seam_fix_denoise: settings.upscale_seam_fix_denoise ?? UPSCALE_SEAM_FIX_DENOISE_DEFAULT,
    upscale_seam_fix_width: settings.upscale_seam_fix_width ?? UPSCALE_SEAM_FIX_WIDTH_DEFAULT,
    upscale_seam_fix_mask_blur:
      settings.upscale_seam_fix_mask_blur ?? UPSCALE_SEAM_FIX_MASK_BLUR_DEFAULT,
    upscale_seam_fix_padding: settings.upscale_seam_fix_padding ?? UPSCALE_SEAM_FIX_PADDING_DEFAULT,
    upscale_force_uniform_tiles:
      settings.upscale_force_uniform_tiles ?? UPSCALE_FORCE_UNIFORM_TILES_DEFAULT,
    upscale_tiled_decode: settings.upscale_tiled_decode ?? UPSCALE_TILED_DECODE_DEFAULT,
    cn_upscale: settings.cn_upscale ?? UPSCALE_MODEL_DEFAULT,
    batch_size: settings.batch_size ?? UPSCALE_BATCH_SIZE_DEFAULT,
    steps: settings.steps ?? UPSCALE_STEPS_DEFAULT,
    cfg_scale: settings.cfg_scale ?? UPSCALE_CFG_DEFAULT,
    sampler: settings.sampler ?? UPSCALE_SAMPLER_DEFAULT,
    scheduler: settings.scheduler ?? UPSCALE_SCHEDULER_DEFAULT,
  };
}
