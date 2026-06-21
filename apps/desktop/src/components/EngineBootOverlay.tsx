import { AlertCircle, Loader2, RefreshCw, ScrollText } from "lucide-react";
import type { EngineState } from "../lib/engine";

type Props = {
  engineState: EngineState;
  bootMessage: string;
  workerLogTail: string;
  onRestart: () => void;
  restarting: boolean;
  onOpenFullLog: () => void;
  companionBootstrapBusy?: boolean;
};

export function EngineBootOverlay({
  engineState,
  bootMessage,
  workerLogTail,
  onRestart,
  restarting,
  onOpenFullLog,
  companionBootstrapBusy,
}: Props) {
  if (
    engineState === "ready" ||
    engineState === "generating" ||
    engineState === "booting" ||
    companionBootstrapBusy
  ) {
    return null;
  }

  const failed = engineState === "failed";
  const title = failed
    ? "GPU engine failed to start"
    : "Restarting GPU engine";

  return (
    <div className="absolute inset-0 z-20 flex items-center justify-center bg-dfui-bg/75 p-6 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-xl border border-dfui-border bg-dfui-panel/95 p-5 shadow-xl">
        <div className="flex items-start gap-3">
          {failed ? (
            <AlertCircle className="mt-0.5 shrink-0 text-red-400" size={22} />
          ) : (
            <Loader2
              className="mt-0.5 shrink-0 animate-spin text-dfui-forge"
              size={22}
            />
          )}
          <div className="min-w-0 flex-1">
            <h2 className="text-sm font-semibold text-dfui-fg">{title}</h2>
            <p className="mt-1 text-xs leading-relaxed text-dfui-secondary">
              {bootMessage ||
                "First launch loads PyTorch and the generation pipeline. This usually takes 20–90 seconds."}
            </p>
            {failed && workerLogTail.trim() ? (
              <pre className="mt-3 max-h-24 overflow-auto whitespace-pre-wrap rounded border border-dfui-border bg-dfui-bg p-2 text-[10px] text-dfui-tertiary">
                {workerLogTail.slice(-1200)}
              </pre>
            ) : null}
            {failed ? (
              <button
                type="button"
                onClick={onOpenFullLog}
                className="mt-3 inline-flex items-center gap-1.5 rounded-md px-1 py-0.5 text-[11px] text-dfui-tertiary transition hover:bg-dfui-surface hover:text-dfui-fg"
              >
                <ScrollText size={14} strokeWidth={1.75} />
                View worker log
              </button>
            ) : null}
            {failed ? (
              <button
                type="button"
                onClick={onRestart}
                disabled={restarting}
                className="mt-4 inline-flex items-center gap-2 rounded-lg border border-dfui-forge/50 bg-dfui-forge/15 px-3 py-1.5 text-xs font-medium text-dfui-fg transition hover:bg-dfui-forge/25 disabled:opacity-50"
              >
                <RefreshCw
                  size={14}
                  className={restarting ? "animate-spin" : undefined}
                />
                {restarting ? "Restarting…" : "Restart GPU engine"}
              </button>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}
