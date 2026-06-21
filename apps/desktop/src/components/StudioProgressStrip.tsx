import { Loader2, ScrollText } from "lucide-react";
import {
  resolveStudioProgress,
  type StudioProgressKind,
} from "../lib/studioProgress";
import type { EngineState } from "../lib/engine";
import type { LiveProgress } from "../lib/generationProgressUi";

type Props = {
  engineState: EngineState;
  bootMessage: string;
  bootPhase?: string;
  generating: boolean;
  liveProgress: LiveProgress | null;
  logSummary?: string;
  companionBootstrapBusy?: boolean;
  companionBootstrapLabel?: string;
  companionBootstrapMessage?: string;
  onOpenFullLog?: () => void;
};

const KIND_SPIN: Record<StudioProgressKind, boolean> = {
  idle: false,
  boot: true,
  prepare: true,
  job: true,
};

export function StudioProgressStrip({
  engineState,
  bootMessage,
  bootPhase,
  generating,
  liveProgress,
  logSummary,
  companionBootstrapBusy,
  companionBootstrapLabel,
  companionBootstrapMessage,
  onOpenFullLog,
}: Props) {
  const view = resolveStudioProgress({
    engineState,
    bootMessage,
    bootPhase,
    generating,
    liveProgress,
    logSummary,
    companionBootstrapBusy,
    companionBootstrapLabel,
    companionBootstrapMessage,
  });

  if (!view.active) {
    return null;
  }

  const showPercent =
    view.kind === "job" &&
    view.percentage != null &&
    view.percentage > 0 &&
    !view.indeterminate;
  const barWidth = showPercent
    ? Math.min(100, Math.max(0, view.percentage ?? 0))
    : view.indeterminate
      ? 35
      : 0;

  return (
    <div
      className="flex shrink-0 flex-col gap-1 border-t border-dfui-border/50 bg-dfui-bg/25 px-3 py-1.5"
      aria-live="polite"
      aria-busy={view.active}
    >
      <div className="flex min-w-0 items-center gap-2">
        {KIND_SPIN[view.kind] ? (
          <Loader2
            size={12}
            className="shrink-0 animate-spin text-dfui-forge"
            aria-hidden
          />
        ) : null}
        <p
          className="min-w-0 flex-1 truncate text-[11px] text-dfui-secondary"
          title={view.title}
        >
          {view.title}
        </p>
        {showPercent ? (
          <span
            className="shrink-0 font-mono text-[11px] tabular-nums text-dfui-forge"
            aria-label={`Progress ${view.percentage} percent`}
          >
            {view.percentage}%
          </span>
        ) : null}
        {onOpenFullLog ? (
          <button
            type="button"
            onClick={onOpenFullLog}
            className="inline-flex shrink-0 items-center justify-center rounded-md p-1 text-dfui-tertiary transition hover:bg-dfui-surface hover:text-dfui-fg"
            title="Open full log"
            aria-label="Open full log"
          >
            <ScrollText size={15} strokeWidth={1.75} />
          </button>
        ) : null}
      </div>
      <div
        className="h-1 overflow-hidden rounded-full bg-dfui-bg"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={showPercent ? (view.percentage ?? undefined) : undefined}
        aria-label={view.title}
      >
        <div
          className={`h-full rounded-full bg-gradient-to-r from-dfui-dream to-dfui-forge ${
            view.indeterminate ? "animate-pulse" : "transition-[width] duration-300 ease-out"
          }`}
          style={{
            width: view.indeterminate ? `${barWidth}%` : `${barWidth}%`,
          }}
        />
      </div>
    </div>
  );
}
