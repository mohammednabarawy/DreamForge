import type { StudioMode } from "./model-selection";

/** Fallback label before the first backend progress event arrives. */
export function studioPrepareFallbackLabel(
  studioMode: StudioMode | string | undefined,
): string {
  switch (studioMode) {
    case "upscale":
      return "Checking Ultimate SD Upscale model and nodes…";
    case "inpaint":
      return "Checking inpaint models and mask tools…";
    case "edit":
      return "Checking edit models and reference tools…";
    default:
      return "Checking required assets…";
  }
}

/** Latest companion-download activity line for modal subtitles. */
export function latestActivityLine(
  lines: Array<{ text: string }>,
  fallback: string,
): string {
  const last = lines.length > 0 ? lines[lines.length - 1]?.text?.trim() : "";
  return last || fallback;
}
