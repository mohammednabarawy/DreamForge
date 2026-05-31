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
export function pathToAssetUrl(
  path: string | undefined,
  cacheBust?: number,
): string | undefined {
  if (!path?.trim()) return undefined;
  try {
    const normalized = path.replace(/\\/g, "/");
    const asset = convertFileSrc(normalized);
    if (cacheBust == null) return asset;
    return `${asset}?v=${cacheBust}`;
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
  const cacheBust = source.final || source.live ? Date.now() : undefined;

  if (source.asset_url) {
    revokeObjectUrl();
    if (cacheBust == null) return source.asset_url;
    const sep = source.asset_url.includes("?") ? "&" : "?";
    return `${source.asset_url}${sep}v=${cacheBust}`;
  }

  if (source.data_url) {
    revokeObjectUrl();
    return source.data_url;
  }

  const asset = pathToAssetUrl(source.preview_path, cacheBust);
  if (asset) {
    revokeObjectUrl();
    return asset;
  }

  if (source.preview_path) {
    try {
      const r = await readImagePreview(source.preview_path, {
        quality: source.final ? "final" : "live",
      });
      if (r.asset_url) {
        revokeObjectUrl();
        if (cacheBust == null) return r.asset_url;
        const sep = r.asset_url.includes("?") ? "&" : "?";
        return `${r.asset_url}${sep}v=${cacheBust}`;
      }
      if (r.data_url) {
        revokeObjectUrl();
        return r.data_url;
      }
    } catch {
      /* fall through */
    }
    const fallbackAsset = pathToAssetUrl(source.preview_path, cacheBust);
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

/** Stable key for comparing whether the canvas already shows this file. */
export function normalizePreviewPath(path: string | undefined): string {
  if (!path?.trim()) return "";
  return path.replace(/\\/g, "/").toLowerCase();
}

/** Prefer asset URL for finals — avoids data-url ↔ asset flicker. */
export async function finalPreviewUrlForPath(
  path: string,
): Promise<string | null> {
  const asset = pathToAssetUrl(path, Date.now());
  if (asset) return asset;
  return resolveCanvasPreviewUrl({ preview_path: path, final: true });
}
