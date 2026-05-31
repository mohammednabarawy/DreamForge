/**
 * Lightweight in-memory thumbnail URL cache.
 *
 * Gallery thumbnails are small JPEG/PNG files that never change between
 * sessions — we convert the backend-supplied local path into a Tauri
 * `asset://` URL and keep the result in an LRU map so the browser can
 * serve them from its image cache on subsequent renders without an
 * expensive IPC round-trip through `read_image_preview`.
 */

import { convertFileSrc } from "@tauri-apps/api/core";

const MAX_ENTRIES = 2000;
const cache = new Map<string, string>();

/** Normalise a Windows backslash path to forward slashes. */
function normalisePath(p: string): string {
  return p.replace(/\\/g, "/");
}

/**
 * Resolve a local file path to an `asset://` URL the webview can load
 * directly — no IPC, no base64 encoding, no resize.
 *
 * Results are cached so repeated renders are instant.
 */
export function thumbnailAssetUrl(path: string | undefined): string | null {
  if (!path?.trim()) return null;

  const key = normalisePath(path);
  const hit = cache.get(key);
  if (hit !== undefined) return hit;

  try {
    const url = convertFileSrc(key);
    // LRU eviction – delete oldest entry when at capacity.
    if (cache.size >= MAX_ENTRIES) {
      const oldest = cache.keys().next().value;
      if (oldest) cache.delete(oldest);
    }
    cache.set(key, url);
    return url;
  } catch {
    return null;
  }
}

/** Bust all cached entries (e.g. after a model scan refresh). */
export function clearThumbnailCache(): void {
  cache.clear();
}
