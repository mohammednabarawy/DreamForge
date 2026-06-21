import { pathToAssetUrl } from "./preview-display";
import { readImagePreview, type ImagePreviewResponse } from "./tauri-api";

const MAX_CONCURRENT = 4;
let active = 0;
const waiters: Array<() => void> = [];

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

function withDisplayUrl(r: ImagePreviewResponse): ImagePreviewResponse & { data_url: string } {
  const data_url = r.data_url ?? pathToAssetUrl(r.path) ?? "";
  return { ...r, data_url };
}

/** Limits concurrent image decode IPC so the UI stays responsive after boot. */
export function readImagePreviewQueued(
  path: string,
  opts?: { quality?: "live" | "final" },
): Promise<ImagePreviewResponse & { data_url: string }> {
  const quality = opts?.quality ?? "final";
  const priority = quality === "final" ? "final" : "normal";
  return runQueued(priority, () =>
    readImagePreview(path, { quality }).then(withDisplayUrl),
  );
}
