import type { GenerationSettings, ModelGalleryItem } from "./tauri-api";
import { selectPhotoRestoreModel } from "./photoRestore";

export const PORTRAIT_MASTER_SAMPLING = {
  steps: 20,
  cfg_scale: 5.5,
  sampler: "dpmpp_2m",
  scheduler: "karras",
  edit_strength: 0.55,
  portrait_pose_strength: 0.65,
  portrait_depth_strength: 0.55,
} as const;

export const PORTRAIT_SHOTS = [
  { id: "closeup", label: "Close-up" },
  { id: "portrait", label: "Portrait" },
  { id: "medium", label: "Medium" },
  { id: "full", label: "Full body" },
] as const;

export const PORTRAIT_EXPRESSIONS = [
  { id: "neutral", label: "Neutral" },
  { id: "happy", label: "Happy" },
  { id: "serious", label: "Serious" },
  { id: "confident", label: "Confident" },
] as const;

export const PORTRAIT_LIGHTING = [
  { id: "soft", label: "Soft" },
  { id: "studio", label: "Studio" },
  { id: "natural", label: "Natural" },
  { id: "dramatic", label: "Dramatic" },
] as const;

function detailPhrase(
  value: number | undefined,
  low: string,
  mid: string,
  high: string,
): string | null {
  const amount = Number.isFinite(value) ? Number(value) : 0.5;
  if (amount < 0.34) return low;
  if (amount < 0.67) return mid;
  return high;
}

export function buildPortraitMasterPrompt(settings: GenerationSettings): string {
  const parts = ["professional portrait photograph", "photorealistic", "sharp focus"];

  const shot = (settings.portrait_shot ?? "portrait").toLowerCase();
  const shotLabel =
    PORTRAIT_SHOTS.find((item) => item.id === shot)?.label.toLowerCase() ?? "head and shoulders portrait";
  parts.push(
    shot === "closeup"
      ? "extreme close-up portrait"
      : shot === "medium"
        ? "medium shot portrait"
        : shot === "full"
          ? "full body portrait"
          : `${shotLabel} portrait`,
  );

  const age = Math.max(1, Math.min(100, Math.round(settings.portrait_age ?? 30)));
  parts.push(`${age} years old`);

  const expression = (settings.portrait_expression ?? "neutral").toLowerCase();
  parts.push(
    expression === "happy"
      ? "warm smile, happy expression"
      : expression === "serious"
        ? "serious expression"
        : expression === "confident"
          ? "confident expression"
          : "neutral expression",
  );

  const lighting = (settings.portrait_lighting ?? "studio").toLowerCase();
  parts.push(
    lighting === "soft"
      ? "soft diffused lighting"
      : lighting === "natural"
        ? "natural window light"
        : lighting === "dramatic"
          ? "dramatic cinematic lighting"
          : "studio portrait lighting",
  );

  const skin = detailPhrase(
    settings.portrait_skin_detail,
    "natural skin texture",
    "detailed skin texture",
    "highly detailed skin pores and texture",
  );
  if (skin) parts.push(skin);

  const eyes = detailPhrase(
    settings.portrait_eye_detail,
    "natural eyes",
    "detailed eyes",
    "highly detailed eyes with catchlights",
  );
  if (eyes) parts.push(eyes);

  return Array.from(new Set(parts.map((part) => part.trim()).filter(Boolean))).join(", ");
}

export function patchForPortraitMasterTask(
  settings: GenerationSettings,
  gallery: ModelGalleryItem[],
): Partial<GenerationSettings> {
  const portraitModel = selectPhotoRestoreModel(gallery);
  return {
    edit_task: "portrait_master",
    edit_type: undefined,
    cn_type: undefined,
    cn_selection: undefined,
    inpaint_mask_path: undefined,
    inpaint_intent: undefined,
    model: portraitModel || settings.model,
    style: "image_edit",
    portrait_shot: settings.portrait_shot ?? "portrait",
    portrait_age: settings.portrait_age ?? 30,
    portrait_expression: settings.portrait_expression ?? "neutral",
    portrait_lighting: settings.portrait_lighting ?? "studio",
    portrait_skin_detail: settings.portrait_skin_detail ?? 0.5,
    portrait_eye_detail: settings.portrait_eye_detail ?? 0.5,
    ...PORTRAIT_MASTER_SAMPLING,
    prompt: (settings.prompt ?? "").trim() || buildPortraitMasterPrompt({
      ...settings,
      portrait_shot: settings.portrait_shot ?? "portrait",
      portrait_age: settings.portrait_age ?? 30,
      portrait_expression: settings.portrait_expression ?? "neutral",
      portrait_lighting: settings.portrait_lighting ?? "studio",
      portrait_skin_detail: settings.portrait_skin_detail ?? 0.5,
      portrait_eye_detail: settings.portrait_eye_detail ?? 0.5,
    }),
  };
}

export function isPortraitMasterTask(settings: GenerationSettings): boolean {
  return (settings.edit_task ?? "").toLowerCase() === "portrait_master";
}
