import { convertFileSrc } from "@tauri-apps/api/core";

import { readImagePreview } from "./tauri-api";

export type PreviewSource = {
  data_url?: string;
  preview_path?: string;
  asset_url?: string;
  live?: boolean;
  final?: boolean;
};

let activeObjectUrl: string | null = null;

function revokeObjectUrl() {
  if (activeObjectUrl) {
    URL.revokeObjectURL(activeObjectUrl);
    activeObjectUrl = null;
  }
}

/** Prefer asset:// URLs (no base64 decode); fall back to data URLs from the worker. */
export function pathToAssetUrl(path: string | undefined): string | undefined {
  if (!path?.trim()) return undefined;
  try {
    const normalized = path.replace(/\\/g, "/");
    return convertFileSrc(normalized);
  } catch {
    return undefined;
  }
}

/**
 * Resolve the best URL for the canvas <img> src.
 * Returns { url, via: "asset" | "data" | "blob" } for debugging.
 */
export async function resolveCanvasPreviewUrl(
  source: PreviewSource,
): Promise<string | null> {
  if (source.asset_url) {
    revokeObjectUrl();
    return source.asset_url;
  }

  const asset = pathToAssetUrl(source.preview_path);
  if (asset && (source.final || !source.data_url)) {
    revokeObjectUrl();
    return asset;
  }

  if (source.data_url) {
    revokeObjectUrl();
    return source.data_url;
  }

  if (source.preview_path) {
    try {
      const r = await readImagePreview(source.preview_path, {
        quality: source.final ? "final" : "live",
      });
      if (r.asset_url) {
        revokeObjectUrl();
        return r.asset_url;
      }
      if (r.data_url) {
        revokeObjectUrl();
        return r.data_url;
      }
    } catch {
      /* fall through */
    }
    const fallbackAsset = pathToAssetUrl(source.preview_path);
    if (fallbackAsset) {
      revokeObjectUrl();
      return fallbackAsset;
    }
  }

  return null;
}

export function cleanupCanvasPreviewUrls() {
  revokeObjectUrl();
}
