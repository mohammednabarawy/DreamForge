export type ConfirmDialogRequest = {
  title: string;
  message: string;
  detail?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  destructive?: boolean;
};

type PendingConfirm = ConfirmDialogRequest & {
  id: number;
  resolve: (confirmed: boolean) => void;
};

type Listener = (pending: PendingConfirm | null) => void;

let nextId = 1;
const queue: PendingConfirm[] = [];
const listeners = new Set<Listener>();

function notify() {
  const current = queue[0] ?? null;
  for (const listener of listeners) {
    listener(current);
  }
}

export function subscribeConfirmDialog(listener: Listener): () => void {
  listeners.add(listener);
  listener(queue[0] ?? null);
  return () => {
    listeners.delete(listener);
  };
}

export function resolveConfirmDialog(id: number, confirmed: boolean) {
  const index = queue.findIndex((item) => item.id === id);
  if (index === -1) return;
  const [entry] = queue.splice(index, 1);
  notify();
  entry.resolve(confirmed);
}

/**
 * In-app confirmation dialog promise.
 * Unlike `window.confirm()`, works reliably across Tauri WKWebView (macOS),
 * WebView2 (Windows), WebKitGTK (Linux), and standard browsers.
 */
export function requestConfirm(req: ConfirmDialogRequest): Promise<boolean> {
  if (listeners.size === 0) {
    // Fallback for headless tests where ConfirmDialogModal is not mounted.
    if (typeof window !== "undefined" && typeof window.confirm === "function") {
      return Promise.resolve(window.confirm(req.message));
    }
    return Promise.resolve(false);
  }
  return new Promise<boolean>((resolve) => {
    queue.push({
      ...req,
      id: nextId++,
      resolve,
    });
    if (queue.length === 1) {
      notify();
    }
  });
}
