import type { GenerationSettings } from "./tauri-api";

export const QWEN_IMAGE21_PROFILES = {
  Speed: { steps: 25, cfg_scale: 1, sampler: "euler", scheduler: "simple" },
  Quality: { steps: 40, cfg_scale: 1, sampler: "euler", scheduler: "simple" },
} as const;

/** Qwen Image 2.1's Comfy workflow defaults for instruction and mask edits. */
export function qwenImage21Defaults(): Partial<GenerationSettings> {
  return {
    style: "image_edit",
    edit_type: "qwen_edit",
    performance: "Quality",
    edit_strength: 1.0,
    cn_selection: "None",
    cn_type: "qwen_edit",
    ...QWEN_IMAGE21_PROFILES.Quality,
  };
}
