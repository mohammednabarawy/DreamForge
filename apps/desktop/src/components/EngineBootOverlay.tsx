import { Loader2 } from "lucide-react";
import type { EngineState } from "../lib/engine";

type Props = {
  engineState: EngineState;
  bootMessage: string;
  companionBootstrapBusy?: boolean;
};

/** Non-blocking restart spinner while the GPU engine comes back online. */
export function EngineBootOverlay({
  engineState,
  bootMessage,
  companionBootstrapBusy,
}: Props) {
  if (
    engineState !== "restarting" ||
    companionBootstrapBusy
  ) {
    return null;
  }

  return (
    <div className="pointer-events-none absolute inset-0 z-20 flex items-center justify-center bg-dfui-bg/40 p-6 backdrop-blur-[2px]">
      <div className="pointer-events-auto flex max-w-sm items-start gap-3 rounded-xl border border-dfui-border/70 bg-dfui-panel/95 px-4 py-3 shadow-lg">
        <Loader2 className="mt-0.5 shrink-0 animate-spin text-dfui-forge" size={20} />
        <div className="min-w-0">
          <p className="text-sm font-medium text-dfui-fg">Restarting GPU engine</p>
          <p className="mt-0.5 text-xs leading-relaxed text-dfui-secondary">
            {bootMessage || "ComfyUI and the worker are restarting. This usually takes a few seconds."}
          </p>
        </div>
      </div>
    </div>
  );
}
