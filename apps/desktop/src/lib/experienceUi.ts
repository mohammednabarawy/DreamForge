import type { StudioMode } from "./model-selection";

export type UiExperience = "simple" | "pro";

export function isSimpleExperience(experience?: UiExperience | null): boolean {
  return experience === "simple";
}

/** Pro experience enables manual checkpoint / advanced inspector controls. */
export function isAdvancedMode(experience?: UiExperience | null): boolean {
  return !isSimpleExperience(experience);
}

export function normalizeStudioModeForExperience(
  mode: StudioMode,
  _experience?: UiExperience | null,
): StudioMode {
  if ((mode as string) === "extract") return "generate";
  if (mode === "edit" || mode === "inpaint" || mode === "toolbox") return "edit";
  return "generate";
}
