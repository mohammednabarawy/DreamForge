/** UI helpers for Fooocus / RuinedFooocus-style generation settings. */

export type AspectOrientation = "portrait" | "square" | "landscape";

export const CUSTOM_PERFORMANCE = "Custom...";

export const PERFORMANCE_HINTS: Record<string, string> = {
  Lightning: "Fastest family profile for previews and rough ideas.",
  Speed: "Balanced family profile for normal generation.",
  Quality: "Higher-detail family profile; slower and more VRAM.",
  [CUSTOM_PERFORMANCE]: "Manual steps, guidance (CFG), sampler, and scheduler.",
};

/** Generic inline previews; model-family panels override these when known. */
export const PERFORMANCE_PREVIEW: Record<
  string,
  { steps: number; cfg: number; sampler: string; scheduler: string }
> = {
  Lightning: { steps: 4, cfg: 2, sampler: "dpmpp_sde", scheduler: "karras" },
  Speed: { steps: 30, cfg: 8, sampler: "dpmpp_2m_sde_gpu", scheduler: "karras" },
  Quality: { steps: 60, cfg: 8, sampler: "dpmpp_2m_sde_gpu", scheduler: "karras" },
};

export function classifyAspectRatio(preset: string): AspectOrientation {
  const parts = preset.toLowerCase().split("x");
  if (parts.length !== 2) return "square";
  const w = Number(parts[0]);
  const h = Number(parts[1]);
  if (!w || !h) return "square";
  if (w === h) return "square";
  return h > w ? "portrait" : "landscape";
}

export function groupAspectPresets(presets: string[]): Record<AspectOrientation, string[]> {
  const groups: Record<AspectOrientation, string[]> = {
    portrait: [],
    square: [],
    landscape: [],
  };
  for (const preset of presets) {
    groups[classifyAspectRatio(preset)].push(preset);
  }
  return groups;
}

export const ASPECT_GROUP_LABELS: Record<AspectOrientation, string> = {
  portrait: "Portrait",
  square: "Square",
  landscape: "Landscape",
};

export const ASPECT_GROUP_ACCENT: Record<AspectOrientation, string> = {
  portrait: "border-rose-400/35 hover:border-rose-400/60 data-[active=true]:border-rose-400 data-[active=true]:bg-rose-400/15",
  square: "border-amber-400/35 hover:border-amber-400/60 data-[active=true]:border-amber-400 data-[active=true]:bg-amber-400/15",
  landscape: "border-emerald-400/35 hover:border-emerald-400/60 data-[active=true]:border-emerald-400 data-[active=true]:bg-emerald-400/15",
};

export function performanceHint(name: string): string {
  return PERFORMANCE_HINTS[name] ?? "Uses DreamForge's model-family performance profile.";
}

/** Ideogram 4 maps Lightning -> Turbo, Speed -> Default, Quality -> Quality. */
export const IDEOGRAM_PERFORMANCE_PREVIEW: Record<
  string,
  { steps: number; cfg: number; sampler: string; scheduler: string }
> = {
  Lightning: { steps: 12, cfg: 7, sampler: "euler", scheduler: "simple" },
  Speed: { steps: 20, cfg: 7, sampler: "euler", scheduler: "simple" },
  Quality: { steps: 48, cfg: 7, sampler: "euler", scheduler: "simple" },
};

const IDEOGRAM_PERFORMANCE_HINTS: Record<string, string> = {
  Lightning: "Ideogram Turbo — 12 steps, fastest iteration.",
  Speed: "Ideogram Default — 20 steps, balanced quality.",
  Quality: "Ideogram Quality — 48 steps; may cap on 16 GB VRAM.",
  [CUSTOM_PERFORMANCE]: "Custom steps: ≤14 Turbo, 15–39 Default, ≥40 Quality.",
};

export function ideogramPerformanceHint(name: string): string {
  return IDEOGRAM_PERFORMANCE_HINTS[name] ?? IDEOGRAM_PERFORMANCE_HINTS.Speed;
}

export function isCustomPerformance(performance: string | undefined): boolean {
  const p = performance ?? "Lightning";
  return p === CUSTOM_PERFORMANCE || p === "Custom";
}
