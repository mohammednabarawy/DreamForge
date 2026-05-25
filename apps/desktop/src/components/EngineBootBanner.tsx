import { Loader2 } from "lucide-react";
import type { EngineState } from "../lib/engine";

type Props = {
  engineState: EngineState;
  bootMessage: string;
};

/** Non-blocking boot status (Gradio-style: UI stays usable while GPU loads). */
export function EngineBootBanner({ engineState, bootMessage }: Props) {
  if (engineState !== "booting" && engineState !== "restarting") {
    return null;
  }

  return (
    <div className="absolute inset-x-4 top-4 z-10 flex items-center gap-2 rounded-lg border border-amber-500/35 bg-dfui-panel/90 px-3 py-2 text-xs backdrop-blur-md">
      <Loader2 size={14} className="shrink-0 animate-spin text-amber-400" />
      <span className="min-w-0 truncate text-dfui-fg">
        {bootMessage ||
          "Loading GPU engine in background — you can browse sessions and plan prompts."}
      </span>
    </div>
  );
}
