import { emit, listen, type UnlistenFn } from "@tauri-apps/api/event";
import { WebviewWindow } from "@tauri-apps/api/webviewWindow";
import type { GenerationSettings } from "./tauri-api";

export const IDEOGRAM_LAYOUT_WINDOW_LABEL = "ideogram-layout";
export const IDEOGRAM_LAYOUT_STORAGE_KEY = "dreamforge.ideogramLayout.settings";
export const IDEOGRAM_LAYOUT_REFRESH_EVENT = "ideogram-layout:refresh";
export const IDEOGRAM_LAYOUT_APPLY_EVENT = "ideogram-layout:apply";

export type IdeogramLayoutApplyPayload = {
  caption: string;
};

export function saveIdeogramLayoutSettings(settings: GenerationSettings) {
  window.localStorage.setItem(IDEOGRAM_LAYOUT_STORAGE_KEY, JSON.stringify(settings));
}

export function readIdeogramLayoutSettings(): GenerationSettings | null {
  const raw = window.localStorage.getItem(IDEOGRAM_LAYOUT_STORAGE_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as unknown;
    return parsed && typeof parsed === "object" ? (parsed as GenerationSettings) : null;
  } catch {
    return null;
  }
}

export async function openIdeogramLayoutWindow(settings: GenerationSettings): Promise<boolean> {
  if (typeof window === "undefined" || !("__TAURI_INTERNALS__" in window)) return false;
  saveIdeogramLayoutSettings(settings);

  const existing = await WebviewWindow.getByLabel(IDEOGRAM_LAYOUT_WINDOW_LABEL);
  if (existing) {
    await existing.show();
    await existing.setFocus();
    await emit(IDEOGRAM_LAYOUT_REFRESH_EVENT, {});
    return true;
  }

  const url = new URL(window.location.href);
  url.search = "";
  url.hash = "";
  url.searchParams.set("tool", "ideogram-layout");

  const win = new WebviewWindow(IDEOGRAM_LAYOUT_WINDOW_LABEL, {
    url: url.toString(),
    title: "DreamForge - Ideogram Layout Builder",
    width: 1320,
    height: 900,
    minWidth: 980,
    minHeight: 700,
    center: true,
    resizable: true,
    decorations: true,
    focus: true,
    dragDropEnabled: false,
  });

  return new Promise((resolve) => {
    let settled = false;
    const finish = (ok: boolean) => {
      if (settled) return;
      settled = true;
      resolve(ok);
    };
    void win.once("tauri://created", () => finish(true));
    void win.once("tauri://error", () => finish(false));
    window.setTimeout(() => finish(true), 1200);
  });
}

export function listenForIdeogramLayoutApply(
  handler: (payload: IdeogramLayoutApplyPayload) => void,
): Promise<UnlistenFn> {
  if (typeof window === "undefined" || !("__TAURI_INTERNALS__" in window)) {
    void handler;
    return Promise.resolve(() => {});
  }
  return listen<IdeogramLayoutApplyPayload>(IDEOGRAM_LAYOUT_APPLY_EVENT, (event) => {
    if (event.payload?.caption) handler(event.payload);
  });
}
