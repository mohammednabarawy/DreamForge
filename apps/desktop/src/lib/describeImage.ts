import type { GenerationSettings } from "./tauri-api";
import { activeReferencePath } from "./referenceImage";
import { interrogateImage } from "./studioBridge";

/** Best local file path to describe (reference, canvas result, or attach). */
export function resolveDescribeImagePath(
  settings: GenerationSettings,
  selectedImagePath?: string | null,
): string {
  const selected = (selectedImagePath ?? "").trim();
  if (selected) return selected;
  const ref = activeReferencePath(settings)?.trim();
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
  hint?: string,
): Promise<{ ok: boolean; prompt?: string; error?: string }> {
  const normalized = path.trim();
  if (!normalized) {
    return { ok: false, error: "no_image" };
  }
  try {
    const res = await interrogateImage(normalized, hint);
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
