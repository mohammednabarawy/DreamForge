import { emit, listen } from "@tauri-apps/api/event";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { useEffect, useState } from "react";
import {
  IDEOGRAM_LAYOUT_APPLY_EVENT,
  IDEOGRAM_LAYOUT_REFRESH_EVENT,
  readIdeogramLayoutSettings,
  type IdeogramLayoutApplyPayload,
} from "../lib/ideogramLayoutWindow";
import type { GenerationSettings } from "../lib/tauri-api";
import { IdeogramLayoutModal } from "./IdeogramLayoutModal";

export function IdeogramLayoutWindow() {
  const [settings, setSettings] = useState<GenerationSettings | null>(() =>
    readIdeogramLayoutSettings(),
  );

  useEffect(() => {
    const refresh = () => setSettings(readIdeogramLayoutSettings());
    const unlistenPromise = listen(IDEOGRAM_LAYOUT_REFRESH_EVENT, refresh);
    window.addEventListener("storage", refresh);
    return () => {
      window.removeEventListener("storage", refresh);
      void unlistenPromise.then((unlisten) => unlisten());
    };
  }, []);

  if (!settings) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-dfui-bg p-6 text-sm text-dfui-muted">
        Open the Ideogram layout builder from the main DreamForge prompt bar.
      </div>
    );
  }

  return (
    <IdeogramLayoutModal
      open
      presentation="window"
      settings={settings}
      onClose={() => {
        void getCurrentWindow().close();
      }}
      onApply={(caption) => {
        const payload: IdeogramLayoutApplyPayload = { caption };
        void emit(IDEOGRAM_LAYOUT_APPLY_EVENT, payload);
        void getCurrentWindow().close();
      }}
    />
  );
}
