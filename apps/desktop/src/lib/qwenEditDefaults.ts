import type { GenerationSettings } from "./tauri-api";

/** Default patch for Qwen Image Edit 2511 Lightning (Edit tab / agent routes). */
export function qwenEdit2511LightningPatch(): Partial<GenerationSettings> {
  return {
    style: "image_edit",
    edit_type: "qwen_edit",
    performance: "Lightning",
    edit_strength: 1.0,
    cn_selection: "Custom...",
    cn_type: "qwen_edit",
    steps: 8,
    cfg_scale: 1.0,
    sampler: "euler",
    scheduler: "simple",
    qwen_scale_megapixels: 1.25,
  };
}
