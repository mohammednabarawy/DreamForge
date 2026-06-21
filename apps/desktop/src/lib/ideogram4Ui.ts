/** Client helpers for Ideogram 4 structured captions (mirrors backend layout utils). */

import type { GenerationSettings } from "./tauri-api";

export type IdeogramLayoutElement = {
  id: string;
  type: "obj" | "text";
  /** Normalized 0–1 rect (top-left origin). */
  x: number;
  y: number;
  w: number;
  h: number;
  desc?: string;
  text?: string;
  color_palette?: string[];
};

export type IdeogramCaptionDraft = {
  aspect_ratio?: string;
  high_level_description?: string;
  style_description?: Record<string, unknown>;
  compositional_deconstruction?: {
    background?: string;
    elements?: Array<Record<string, unknown>>;
  };
};

export function extractJsonObject(text: string): string {
  const trimmed = text.trim();
  const fence = trimmed.match(/^```(?:json)?\s*([\s\S]*?)```$/i);
  return (fence?.[1] ?? trimmed).trim();
}

export function looksLikeIdeogramJson(text: string): boolean {
  try {
    const obj = JSON.parse(extractJsonObject(text)) as unknown;
    if (!obj || typeof obj !== "object" || Array.isArray(obj)) return false;
    const record = obj as Record<string, unknown>;
    return (
      "high_level_description" in record ||
      "compositional_deconstruction" in record ||
      "aspect_ratio" in record ||
      "style_description" in record
    );
  } catch {
    return false;
  }
}

export function parseIdeogramCaption(text: string): IdeogramCaptionDraft | null {
  try {
    const obj = JSON.parse(extractJsonObject(text)) as IdeogramCaptionDraft;
    if (!obj || typeof obj !== "object") return null;
    return obj;
  } catch {
    return null;
  }
}

/** UI rect (0–1) → Ideogram bbox [y1, x1, y2, x2] in 0–1000. */
export function uiRectToBbox(x: number, y: number, w: number, h: number): number[] {
  const x1 = Math.max(0, Math.min(1000, Math.round(x * 1000)));
  const y1 = Math.max(0, Math.min(1000, Math.round(y * 1000)));
  let x2 = Math.max(0, Math.min(1000, Math.round((x + w) * 1000)));
  let y2 = Math.max(0, Math.min(1000, Math.round((y + h) * 1000)));
  if (y2 <= y1) y2 = Math.min(1000, y1 + 1);
  if (x2 <= x1) x2 = Math.min(1000, x1 + 1);
  return [y1, x1, y2, x2];
}

/** Ideogram bbox → UI rect (0–1). */
export function bboxToUiRect(bbox: number[]): { x: number; y: number; w: number; h: number } {
  const [y1, x1, y2, x2] = bbox.map((v) => Number(v) || 0);
  return {
    x: x1 / 1000,
    y: y1 / 1000,
    w: Math.max(0.01, (x2 - x1) / 1000),
    h: Math.max(0.01, (y2 - y1) / 1000),
  };
}

export function layoutElementsFromCaption(caption: IdeogramCaptionDraft | null): IdeogramLayoutElement[] {
  const raw = caption?.compositional_deconstruction?.elements;
  if (!Array.isArray(raw)) return [];
  return raw.map((el, index) => {
    const type = el.type === "text" ? "text" : "obj";
    const bbox = Array.isArray(el.bbox) ? el.bbox : [100, 100, 300, 300];
    const rect = bboxToUiRect(bbox as number[]);
    return {
      id: `el-${index}`,
      type,
      ...rect,
      desc: typeof el.desc === "string" ? el.desc : "",
      text: typeof el.text === "string" ? el.text : "",
      color_palette: Array.isArray(el.color_palette)
        ? (el.color_palette as string[]).filter(Boolean)
        : [],
    };
  });
}

export function layoutElementsToApi(elements: IdeogramLayoutElement[]): Array<Record<string, unknown>> {
  return elements.map((el) => {
    const out: Record<string, unknown> = {
      type: el.type,
      bbox: uiRectToBbox(el.x, el.y, el.w, el.h),
    };
    if (el.type === "text" && el.text?.trim()) out.text = el.text.trim();
    if (el.desc?.trim()) out.desc = el.desc.trim();
    const palette = normalizeHexPalette(el.color_palette ?? [], 5);
    if (palette.length) out.color_palette = palette;
    return out;
  });
}

export function normalizeHexPalette(values: string[], maxItems: number): string[] {
  return values
    .map((value) => value.trim().toUpperCase())
    .filter((value) => /^#[0-9A-F]{6}$/.test(value))
    .slice(0, maxItems);
}

export function splitPaletteInput(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

/** Default Ideogram 4 generation settings (model family defaults). */
export function ideogram4SettingsDefaults(): Pick<
  GenerationSettings,
  "ideogram4_prompt_mode" | "ideogram4_enhance_on_generate" | "performance" | "aspect_ratio" | "seed"
> {
  return {
    ideogram4_prompt_mode: "auto",
    ideogram4_enhance_on_generate: true,
    performance: "Lightning",
    aspect_ratio: "768x768",
    seed: -1,
  };
}

const ASPECT_RATIO_TO_IDEOGRAM: Record<string, string> = {
  "768x768": "1:1",
  "1024x1024": "1:1",
  "704x880": "4:5",
  "896x1120": "4:5",
  "576x1024": "9:16",
  "768x1344": "9:16",
  "1024x576": "16:9",
  "1344x768": "16:9",
  "704x1056": "2:3",
  "896x1344": "2:3",
};

export function ideogramAspectLabel(settings: {
  width?: number;
  height?: number;
  aspect_ratio?: string;
  ideogram4_aspect_preset?: string;
}): string {
  const ar = settings.aspect_ratio?.toLowerCase().replace("×", "x").replace(/\s/g, "");
  if (ar && ASPECT_RATIO_TO_IDEOGRAM[ar]) return ASPECT_RATIO_TO_IDEOGRAM[ar];
  const preset = settings.ideogram4_aspect_preset;
  if (preset && preset !== "custom") return preset;
  const w = settings.width ?? 768;
  const h = settings.height ?? 768;
  const divisor = gcd(w, h);
  return `${Math.round(w / divisor)}:${Math.round(h / divisor)}`;
}

function gcd(a: number, b: number): number {
  let x = Math.max(1, Math.abs(Math.round(a)));
  let y = Math.max(1, Math.abs(Math.round(b)));
  while (y) {
    const next = x % y;
    x = y;
    y = next;
  }
  return x || 1;
}
