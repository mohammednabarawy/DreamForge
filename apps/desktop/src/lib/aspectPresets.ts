/** Canonical aspect presets — keep in sync with backend/dreamforge_aspect_presets.py */

const RESOLUTION_DEFAULTS = [
  "768x768",
  "896x896",
  "1024x1024",
  "896x672",
  "672x896",
  "960x640",
  "640x960",
  "1024x576",
  "576x1024",
  "1024x448",
  "448x1024",
  "704x1056",
  "1056x704",
  "1152x896",
  "896x1152",
  "1344x768",
  "768x1344",
] as const;

const FOOOCUS_EXTRAS = [
  "896x704",
  "704x896",
  "1536x640",
  "640x1536",
] as const;

const HIDREAM_O1_TARGETS = [
  "1536x1536",
  "1344x1792",
  "1792x1344",
  "2048x2048",
  "1728x2304",
  "2304x1728",
  "1440x2560",
  "2560x1440",
] as const;

export function normalizeAspectPreset(value: string | undefined | null): string | null {
  const raw = (value ?? "").trim().replace(/×/g, "x");
  if (!raw) return null;
  const head = raw.split("(", 1)[0]?.trim() ?? "";
  const match = head.match(/^(\d+)x(\d+)$/i);
  if (!match) return null;
  const w = Number(match[1]);
  const h = Number(match[2]);
  if (!w || !h) return null;
  return `${w}x${h}`;
}

function mergeUniquePresets(...groups: readonly (readonly string[])[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const group of groups) {
    for (const item of group) {
      const normalized = normalizeAspectPreset(item);
      if (!normalized || seen.has(normalized)) continue;
      seen.add(normalized);
      out.push(normalized);
    }
  }
  out.sort((a, b) => {
    const [aw, ah] = a.split("x").map(Number);
    const [bw, bh] = b.split("x").map(Number);
    const areaA = aw * ah;
    const areaB = bw * bh;
    if (areaA !== areaB) return areaA - areaB;
    return a.localeCompare(b);
  });
  return out;
}

export const DEFAULT_ASPECT_PRESETS = mergeUniquePresets(
  RESOLUTION_DEFAULTS,
  FOOOCUS_EXTRAS,
  HIDREAM_O1_TARGETS,
);

/** Quick picks for Simple mode prompt bar. */
export const SIMPLE_ASPECT_PRESETS = [
  "1024x1024",
  "768x1344",
  "1344x768",
  "1536x1536",
  "2048x2048",
] as const;

export function resolveAspectPresets(uiDefaults?: string[] | null): string[] {
  const fromApi = (uiDefaults ?? [])
    .map((item) => normalizeAspectPreset(item))
    .filter((item): item is string => Boolean(item));
  if (!fromApi.length) return [...DEFAULT_ASPECT_PRESETS];
  return mergeUniquePresets(fromApi, DEFAULT_ASPECT_PRESETS);
}
