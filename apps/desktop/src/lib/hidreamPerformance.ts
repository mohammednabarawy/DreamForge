import type { GenerationSettings } from "./tauri-api";
import { isCustomPerformance } from "./generationSettingsUi";
import {
  applyHiDreamO1DevAtSubmit,
  HIDREAM_O1_DEV_PREVIEW,
  isHiDreamO1DevCheckpoint,
} from "./hidreamO1Profiles";

/** ComfyUI official: distilled Dev/Fast use CFG 1.0 (not 0 — prompt still needs guidance). */
export const HIDREAM_DISTILLED_CFG = 1.0;
export const HIDREAM_FULL_CFG = 5.0;

/** Generic HiDream I1 / O1 Full previews (non-O1-Dev checkpoints). */
export const HIDREAM_PERFORMANCE_PREVIEW: Record<
  string,
  { steps: number; cfg: number; sampler: string; scheduler: string }
> = {
  Lightning: { steps: 16, cfg: HIDREAM_DISTILLED_CFG, sampler: "euler", scheduler: "normal" },
  Speed: { steps: 28, cfg: HIDREAM_DISTILLED_CFG, sampler: "euler", scheduler: "normal" },
  Quality: { steps: 50, cfg: HIDREAM_FULL_CFG, sampler: "euler", scheduler: "normal" },
};

export function hidreamPerformancePreview(
  model?: string,
  performance?: string,
): { steps: number; cfg: number; sampler: string; scheduler: string } | undefined {
  const perf = performance ?? "Speed";
  if (isHiDreamO1DevCheckpoint(model)) {
    return HIDREAM_O1_DEV_PREVIEW[perf] ?? HIDREAM_O1_DEV_PREVIEW.Speed;
  }
  return HIDREAM_PERFORMANCE_PREVIEW[perf];
}

function modelLower(model?: string): string {
  return (model ?? "").toLowerCase();
}

export function hidreamIsFastVariant(model?: string): boolean {
  return modelLower(model).includes("fast");
}

export function hidreamIsDevVariant(model?: string): boolean {
  const name = modelLower(model);
  if (hidreamIsFastVariant(name)) return false;
  return ["dev", "mxfp8", "fp8", "distill", "2604"].some((token) => name.includes(token));
}

export function hidreamIsDistilledVariant(model?: string): boolean {
  return hidreamIsFastVariant(model) || hidreamIsDevVariant(model);
}

export function hidreamRecommendedCfg(model?: string): number {
  return hidreamIsDistilledVariant(model) ? HIDREAM_DISTILLED_CFG : HIDREAM_FULL_CFG;
}

function resolveHiDreamCfg(model: string | undefined, cfg: number | undefined): number {
  const recommended = hidreamRecommendedCfg(model);
  if (cfg == null || Number.isNaN(cfg)) return recommended;
  if (hidreamIsDistilledVariant(model) && cfg > 1.5) return recommended;
  if (!hidreamIsDistilledVariant(model) && cfg >= 6) return recommended;
  return cfg;
}

/** Last-mile guard before submit — blocks SDXL CFG 7 on distilled HiDream. */
export function applyHiDreamPerformanceAtSubmit(
  settings: GenerationSettings,
  modelFamily?: string,
  modelName?: string,
): GenerationSettings {
  const family = (modelFamily ?? "").toLowerCase();
  if (!family.startsWith("hidream")) return settings;

  const model = modelName ?? settings.model;
  if (isHiDreamO1DevCheckpoint(model)) {
    return applyHiDreamO1DevAtSubmit(settings, model);
  }

  const perf = settings.performance ?? "Speed";
  const custom = isCustomPerformance(perf);
  const preview = HIDREAM_PERFORMANCE_PREVIEW[perf];

  const next: GenerationSettings = { ...settings };

  if (!custom && preview) {
    next.steps =
      perf === "Lightning"
        ? hidreamIsFastVariant(model)
          ? 16
          : 16
        : perf === "Speed"
          ? hidreamIsFastVariant(model)
            ? 16
            : hidreamIsDevVariant(model)
              ? 28
              : 50
          : 50;
    next.cfg_scale = preview.cfg;
    next.sampler = preview.sampler;
    next.scheduler = preview.scheduler;
    next.performance = perf;
  } else {
    next.cfg_scale = resolveHiDreamCfg(model, settings.cfg_scale);
  }

  if (hidreamIsDistilledVariant(model)) {
    next.negative_prompt = "";
    if (next.styles?.length) next.styles = [];
  }

  return next;
}

export { isHiDreamO1DevCheckpoint, HIDREAM_O1_DEV_PREVIEW } from "./hidreamO1Profiles";
