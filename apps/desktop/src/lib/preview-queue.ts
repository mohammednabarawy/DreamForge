import { readImagePreview } from "./tauri-api";

const MAX_CONCURRENT = 4;
let active = 0;
const waiters: Array<() => void> = [];

function drain() {
  while (active < MAX_CONCURRENT && waiters.length > 0) {
    active += 1;
    waiters.shift()!();
  }
}

/** Limits concurrent image decode IPC so the UI stays responsive after boot. */
export function readImagePreviewQueued(path: string) {
  return new Promise<Awaited<ReturnType<typeof readImagePreview>>>((resolve, reject) => {
    const run = () => {
      void readImagePreview(path)
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
