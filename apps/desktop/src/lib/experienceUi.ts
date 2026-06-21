import type { StudioMode } from "./model-selection";

export type UiExperience = "simple" | "pro";

export const SIMPLE_STUDIO_MODES: Array<{ id: StudioMode; label: string }> = [
  { id: "generate", label: "Create" },
  { id: "edit", label: "Edit" },
  { id: "inpaint", label: "Fix region" },
  { id: "upscale", label: "Enhance" },
  { id: "extract", label: "Extract" },
];

export const PRO_STUDIO_MODES: Array<{ id: StudioMode; label: string }> = [
  { id: "generate", label: "Generate" },
  { id: "edit", label: "Edit" },
  { id: "inpaint", label: "Inpaint" },
  { id: "upscale", label: "Upscale" },
  { id: "extract", label: "Extract" },
  { id: "agent", label: "Agent" },
];

export function isSimpleExperience(experience?: UiExperience | null): boolean {
  return experience === "simple";
}

/** Pro experience enables manual checkpoint / advanced inspector controls. */
export function isAdvancedMode(experience?: UiExperience | null): boolean {
  return !isSimpleExperience(experience);
}

export function studioModesForExperience(
  experience?: UiExperience | null,
): Array<{ id: StudioMode; label: string }> {
  return isSimpleExperience(experience) ? SIMPLE_STUDIO_MODES : PRO_STUDIO_MODES;
}

export function normalizeStudioModeForExperience(
  mode: StudioMode,
  experience?: UiExperience | null,
): StudioMode {
  if (!isSimpleExperience(experience)) return mode;
  if (mode === "agent") return "generate";
  return mode;
}
