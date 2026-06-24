import type { GenerationSettings } from "./tauri-api";
import { bridgeInvoke } from "./studioBridge";

export type ImageMetadataImportResult = {
  ok: boolean;
  error?: string;
  file_path?: string;
  patch?: Partial<GenerationSettings>;
  parameters?: Record<string, unknown>;
};

export async function importImageMetadata(
  path: string,
): Promise<ImageMetadataImportResult> {
  return bridgeInvoke<ImageMetadataImportResult>("import_image_metadata", {
    path,
  });
}

export function mergeMetadataPatch(
  current: GenerationSettings,
  patch: Partial<GenerationSettings>,
): Partial<GenerationSettings> {
  const next: Partial<GenerationSettings> = { ...patch };
  if (!patch.prompt && current.prompt?.trim()) {
    delete next.prompt;
  }
  return next;
}
