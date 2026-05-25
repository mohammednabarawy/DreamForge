import { AlertCircle, ExternalLink, Loader2, RefreshCw } from "lucide-react";
import type { EngineState } from "../lib/engine";

type Props = {
  engineState: EngineState;
  bootMessage: string;
  workerLogTail: string;
  onRestart: () => void;
  restarting: boolean;
  onOpenFullLog: () => void;
};

export function EngineBootOverlay({
  engineState,
  bootMessage,
  workerLogTail,
  onRestart,
  restarting,
  onOpenFullLog,
}: Props) {
  if (
    engineState === "ready" ||
    engineState === "generating" ||
    engineState === "booting"
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
            {failed && workerLogTail ? (
              <>
                <div className="mt-3 flex items-center justify-between">
                  <span className="font-mono text-[9px] uppercase tracking-wider text-dfui-tertiary">Worker log</span>
                  <button
                    type="button"
                    onClick={onOpenFullLog}
                    className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 font-mono text-[9px] text-dfui-tertiary transition hover:bg-dfui-surface hover:text-dfui-fg"
                  >
                    <ExternalLink size={10} />
                    Full log
                  </button>
                </div>
                <pre className="mt-1 max-h-32 overflow-auto rounded-lg border border-dfui-border/80 bg-dfui-bg/80 p-2 font-mono text-[10px] leading-snug text-dfui-secondary">
                  {workerLogTail}
                </pre>
              </>
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
