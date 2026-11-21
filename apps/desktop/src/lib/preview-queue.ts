import { pathToAssetUrl } from "./preview-display";
import { readImagePreview, type ImagePreviewResponse } from "./tauri-api";

const MAX_CONCURRENT = 4;
const THUMB_CACHE_LIMIT = 400;
const THUMB_RETRY_DELAYS_MS = [250, 650];

let active = 0;
const waiters: Array<() => void> = [];

type CachedPreview = ImagePreviewResponse & { data_url: string };

const thumbnailCache = new Map<string, CachedPreview>();
const inflightThumbnails = new Map<string, Promise<CachedPreview>>();

function cacheKey(path: string): string {
  return path.trim().replace(/\\/g, "/");
}

function touchCache(key: string, entry: CachedPreview) {
  if (thumbnailCache.has(key)) {
    thumbnailCache.delete(key);
  }
  thumbnailCache.set(key, entry);
  while (thumbnailCache.size > THUMB_CACHE_LIMIT) {
    const oldestKey = thumbnailCache.keys().next().value;
    if (oldestKey === undefined) break;
    thumbnailCache.delete(oldestKey);
  }
}

export function getCachedThumbnailUrl(path: string | undefined): string | null {
  if (!path) return null;
  const key = cacheKey(path);
  const hit = thumbnailCache.get(key);
  if (!hit?.data_url) return null;
  // Promote on read (LRU)
  thumbnailCache.delete(key);
  thumbnailCache.set(key, hit);
  return hit.data_url;
}

export function invalidateThumbnailCache(path?: string) {
  if (!path) {
    thumbnailCache.clear();
    inflightThumbnails.clear();
    return;
  }
  const key = cacheKey(path);
  thumbnailCache.delete(key);
  inflightThumbnails.delete(key);
}

function drain() {
  while (active < MAX_CONCURRENT && waiters.length > 0) {
    active += 1;
    waiters.shift()!();
  }
}

function runQueued<T>(priority: "normal" | "final", fn: () => Promise<T>): Promise<T> {
  if (priority === "final") {
    return fn();
  }
  return new Promise<T>((resolve, reject) => {
    const run = () => {
      void fn()
        .then(resolve, reject)
        .finally(() => {
          active -= 1;
          drain();
        });
    };
    if (active < MAX_CONCURRENT) {
      active += 1;
      run();
    } else {
      waiters.push(run);
    }
  });
}

function withDisplayUrl(r: ImagePreviewResponse): CachedPreview {
  const data_url = r.data_url ?? pathToAssetUrl(r.path) ?? "";
  return { ...r, data_url };
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

async function readThumbnailWithRetry(path: string): Promise<CachedPreview> {
  let lastError: unknown;
  for (let attempt = 0; attempt <= THUMB_RETRY_DELAYS_MS.length; attempt += 1) {
    try {
      const res = await runQueued("normal", () =>
        readImagePreview(path, { quality: "thumbnail" }).then(withDisplayUrl),
      );
      if (res.data_url) {
        return res;
      }
      lastError = new Error("Empty thumbnail preview response");
    } catch (err) {
      lastError = err;
    }
    if (attempt < THUMB_RETRY_DELAYS_MS.length) {
      await delay(THUMB_RETRY_DELAYS_MS[attempt]);
    }
  }
  const asset = pathToAssetUrl(path);
  if (asset) {
    return { path, mime: "image/png", quality: "thumbnail", data_url: asset };
  }
  throw lastError instanceof Error ? lastError : new Error(String(lastError ?? "thumbnail_failed"));
}

/** Limits concurrent image decode IPC, deduplicates in-flight thumbnails, and caches decoded URLs. */
export function readImagePreviewQueued(
  path: string,
  opts?: { quality?: "live" | "final" | "thumbnail"; bypassCache?: boolean },
): Promise<CachedPreview> {
  const quality = opts?.quality ?? "final";
  if (quality === "thumbnail") {
    const key = cacheKey(path);
    if (!opts?.bypassCache) {
      const cached = thumbnailCache.get(key);
      if (cached?.data_url) {
        touchCache(key, cached);
        return Promise.resolve(cached);
      }
    } else {
      thumbnailCache.delete(key);
    }
    const existing = inflightThumbnails.get(key);
    if (existing) {
      return existing;
    }
    const pending = readThumbnailWithRetry(path)
      .then((res) => {
        if (res.data_url) {
          touchCache(key, res);
        }
        return res;
      })
      .finally(() => {
        inflightThumbnails.delete(key);
      });
    inflightThumbnails.set(key, pending);
    return pending;
  }

  const priority = quality === "final" ? "final" : "normal";
  return runQueued(priority, () =>
    readImagePreview(path, { quality }).then(withDisplayUrl),
  );
}
