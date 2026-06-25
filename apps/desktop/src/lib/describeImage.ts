import type { GenerationSettings } from "./tauri-api";
import { activeReferencePath } from "./referenceImage";
import type { StudioMode } from "./model-selection";
import { interrogateImage } from "./studioBridge";

export type DescribeImageSource = {
  selectedImagePath?: string | null;
  canvasPreviewPath?: string | null;
  studioMode?: StudioMode;
};

/** Best local file path to describe (canvas, history, or attached reference). */
export function resolveDescribeImagePath(
  settings: GenerationSettings,
  source?: DescribeImageSource,
): string {
  const selected = (source?.selectedImagePath ?? "").trim();
  if (selected) return selected;

  const canvas = (source?.canvasPreviewPath ?? "").trim();
  if (canvas) return canvas;

  const studioMode = source?.studioMode ?? "generate";
  const ref = activeReferencePath(settings, studioMode)?.trim();
  if (ref) return ref;

  return (
    settings.input_image?.trim() ||
    settings.reference_image?.trim() ||
    settings.upscale_image?.trim() ||
    ""
  );
}

export async function describeImageToPrompt(
  path: string,
  options?: { interrogator?: "brainblip" | "clip" | "florence" },
): Promise<{ ok: boolean; prompt?: string; error?: string }> {
  const normalized = path.trim();
  if (!normalized) {
    return { ok: false, error: "no_image" };
  }
  try {
    const res = await interrogateImage(normalized, options?.interrogator);
    const prompt = (res.prompt ?? "").trim();
    if (!prompt) {
      return { ok: false, error: "empty_caption" };
    }
    return { ok: true, prompt };
  } catch (err) {
    return {
      ok: false,
      error: err instanceof Error ? err.message : "describe_failed",
    };
  }
}
