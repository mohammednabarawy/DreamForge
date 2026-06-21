import type { GenerationSettings } from "./tauri-api";

type ManifestBundle = {
  prompt?: string;
  negative_prompt?: string;
  seed?: number;
  model?: { name?: string; family?: string } | string;
  settings?: Record<string, unknown>;
  routing?: Record<string, unknown>;
};

/** Map a saved generation manifest into GenerationSettings (paths omitted). */
export function settingsFromManifestBundle(
  bundle: ManifestBundle,
): Partial<GenerationSettings> {
  const raw = bundle.settings ?? {};
  const routing = bundle.routing ?? {};
  const modelInfo = bundle.model;
  const modelName =
    typeof modelInfo === "string"
      ? modelInfo
      : typeof modelInfo === "object" && modelInfo
        ? modelInfo.name
        : undefined;

  const patch: Partial<GenerationSettings> = {
    prompt: bundle.prompt ?? "",
    negative_prompt:
      bundle.negative_prompt ??
      (typeof raw.negative === "string" ? raw.negative : undefined),
    model:
      modelName ??
      (typeof raw.model === "string" ? raw.model : undefined) ??
      (typeof raw.model_name === "string" ? raw.model_name : undefined),
    seed: typeof bundle.seed === "number" ? bundle.seed : undefined,
    steps: typeof raw.steps === "number" ? raw.steps : undefined,
    cfg_scale:
      typeof raw.cfg === "number"
        ? raw.cfg
        : typeof raw.cfg_scale === "number"
          ? raw.cfg_scale
          : undefined,
    sampler:
      (typeof raw.sampler_name === "string" ? raw.sampler_name : undefined) ??
      (typeof raw.sampler === "string" ? raw.sampler : undefined),
    scheduler: typeof raw.scheduler === "string" ? raw.scheduler : undefined,
    styles: Array.isArray(raw.styles) ? (raw.styles as string[]) : undefined,
    style: typeof raw.style === "string" ? raw.style : undefined,
    performance:
      (typeof raw.performance_selection === "string"
        ? raw.performance_selection
        : undefined) ??
      (typeof raw.performance === "string" ? raw.performance : undefined),
    aspect_ratio:
      typeof raw.aspect_ratio === "string" ? raw.aspect_ratio : undefined,
    width: typeof raw.width === "number" ? raw.width : undefined,
    height: typeof raw.height === "number" ? raw.height : undefined,
    lora: Array.isArray(raw.lora) ? (raw.lora as string[]) : undefined,
    edit_type: routing.edit_type as GenerationSettings["edit_type"],
    edit_strength:
      typeof routing.edit_strength === "number"
        ? routing.edit_strength
        : undefined,
    cn_selection:
      typeof routing.cn_selection === "string"
        ? routing.cn_selection
        : undefined,
    cn_type:
      typeof routing.cn_type === "string" ? routing.cn_type : undefined,
    upscale_method:
      typeof raw.upscale_method === "string" ? raw.upscale_method : undefined,
    template_id:
      typeof routing.template_id === "string"
        ? routing.template_id
        : typeof raw.template_id === "string"
          ? raw.template_id
          : undefined,
    post_upscale:
      typeof routing.post_upscale === "string"
        ? routing.post_upscale
        : typeof raw.post_upscale === "string"
          ? raw.post_upscale
          : undefined,
    post_upscale_enabled: Boolean(
      routing.post_upscale ?? raw.post_upscale ?? routing.post_upscale_enabled,
    ),
    vram_profile: raw.vram_profile as GenerationSettings["vram_profile"],
  };

  for (const key of Object.keys(patch) as (keyof GenerationSettings)[]) {
    if (patch[key] === undefined) {
      delete patch[key];
    }
  }
  return patch;
}
