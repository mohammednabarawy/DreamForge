import type { GenerationSettings } from "./tauri-api";
import { classifyAspectRatio, type AspectOrientation } from "./generationSettingsUi";
import { isCustomPerformance } from "./generationSettingsUi";

/** Official Dev locks — CFG 1.0, LCM, no negative. */
export const HIDREAM_O1_DEV_LOCKED = {
  cfg: 1.0,
  sampler: "lcm",
  scheduler: "normal",
  hidream_noise_scale: 7.6,
  denoise: 1.0,
  hidream_s_noise: 1.0,
  hidream_s_noise_end: 1.0,
  hidream_noise_clip_std: 2.5,
} as const;

type O1DevProfile = {
  steps: number;
  promptRefinement: boolean;
  patchSeamSmoothing: boolean;
  referenceMegapixels: number;
  square: string;
  portrait: string;
  landscape: string;
};

export const HIDREAM_O1_DEV_PROFILES: Record<string, O1DevProfile> = {
  Lightning: {
    steps: 16,
    promptRefinement: false,
    patchSeamSmoothing: false,
    referenceMegapixels: 1.0,
    square: "1024x1024",
    portrait: "896x1152",
    landscape: "1152x896",
  },
  Speed: {
    steps: 22,
    promptRefinement: false,
    patchSeamSmoothing: false,
    referenceMegapixels: 2.0,
    square: "1536x1536",
    portrait: "1344x1792",
    landscape: "1792x1344",
  },
  Quality: {
    steps: 28,
    promptRefinement: true,
    patchSeamSmoothing: true,
    referenceMegapixels: 4.0,
    square: "2048x2048",
    portrait: "1728x2304",
    landscape: "2304x1728",
  },
};

export const HIDREAM_O1_DEV_PREVIEW: Record<
  string,
  { steps: number; cfg: number; sampler: string; scheduler: string }
> = {
  Lightning: { steps: 16, cfg: 1.0, sampler: "lcm", scheduler: "normal" },
  Speed: { steps: 22, cfg: 1.0, sampler: "lcm", scheduler: "normal" },
  Quality: { steps: 28, cfg: 1.0, sampler: "lcm", scheduler: "normal" },
};

export function isHiDreamO1DevCheckpoint(model?: string): boolean {
  const name = (model ?? "").toLowerCase();
  if (!name.includes("hidream") || !name.includes("o1")) return false;
  if (name.includes("fast")) return false;
  if (name.includes("full") && !name.includes("dev")) return false;
  return ["dev", "mxfp8", "fp8", "distill", "2604", "o1"].some((t) => name.includes(t));
}

function aspectPresetForProfile(
  performance: string,
  aspectRatio?: string,
  width?: number,
  height?: number,
): string {
  const profile = HIDREAM_O1_DEV_PROFILES[performance] ?? HIDREAM_O1_DEV_PROFILES.Speed;
  let orient: AspectOrientation = "square";
  if (aspectRatio?.trim()) {
    orient = classifyAspectRatio(aspectRatio.replace(/×/g, "x"));
  } else if (width && height) {
    orient = width === height ? "square" : height > width ? "portrait" : "landscape";
  }
  return profile[orient];
}

export function applyHiDreamO1DevAtSubmit(
  settings: GenerationSettings,
  modelName?: string,
): GenerationSettings {
  const model = modelName ?? settings.model;
  if (!isHiDreamO1DevCheckpoint(model)) return settings;

  const perf = settings.performance ?? "Speed";
  if (isCustomPerformance(perf)) {
    const next = { ...settings };
    if ((next.cfg_scale ?? 7) > 1.5) next.cfg_scale = HIDREAM_O1_DEV_LOCKED.cfg;
    next.negative_prompt = "";
    next.sampler = next.sampler ?? HIDREAM_O1_DEV_LOCKED.sampler;
    next.scheduler = next.scheduler ?? HIDREAM_O1_DEV_LOCKED.scheduler;
    return next;
  }

  const profile = HIDREAM_O1_DEV_PROFILES[perf] ?? HIDREAM_O1_DEV_PROFILES.Speed;
  const aspect = aspectPresetForProfile(perf, settings.aspect_ratio, settings.width, settings.height);
  const [w, h] = aspect.split("x").map(Number);

  return {
    ...settings,
    steps: profile.steps,
    cfg_scale: HIDREAM_O1_DEV_LOCKED.cfg,
    sampler: HIDREAM_O1_DEV_LOCKED.sampler,
    scheduler: HIDREAM_O1_DEV_LOCKED.scheduler,
    denoise: HIDREAM_O1_DEV_LOCKED.denoise,
    hidream_noise_scale: HIDREAM_O1_DEV_LOCKED.hidream_noise_scale,
    hidream_s_noise: HIDREAM_O1_DEV_LOCKED.hidream_s_noise,
    hidream_s_noise_end: HIDREAM_O1_DEV_LOCKED.hidream_s_noise_end,
    hidream_noise_clip_std: HIDREAM_O1_DEV_LOCKED.hidream_noise_clip_std,
    hidream_patch_seam_smoothing: profile.patchSeamSmoothing,
    hidream_reference_megapixels: profile.referenceMegapixels,
    hidream_prompt_refinement: profile.promptRefinement,
    prompt_enhancer: profile.promptRefinement ? "gemma4" : "none",
    aspect_ratio: aspect,
    width: w,
    height: h,
    negative_prompt: "",
    styles: [],
  };
}

/** True when HiDream O1 Quality (or explicit flag) needs the Gemma4 encoder. */
export function hidreamO1Gemma4Requested(
  settings: Pick<GenerationSettings, "performance" | "hidream_prompt_refinement">,
): boolean {
  if (settings.hidream_prompt_refinement != null) {
    return settings.hidream_prompt_refinement;
  }
  return (settings.performance ?? "").trim().toLowerCase() === "quality";
}
