import { generationPhaseLabel } from "./engine";

export type LiveProgress = {
  percentage: number;
  title: string;
};

const GENERIC_PROGRESS_TITLES = new Set([
  "Sampling…",
  "Sampling...",
  "Working…",
  "Generating…",
]);

/** Keep progress monotonic and avoid resetting when events omit a numeric percent. */
export function mergeLiveProgress(
  prev: LiveProgress | null,
  next: {
    phase?: string;
    progress?: number | null;
    message?: string;
    title?: string;
    percentage?: number;
  },
): LiveProgress {
  const phase = next.phase;
  const rawPct =
    typeof next.progress === "number"
      ? next.progress
      : typeof next.percentage === "number"
        ? next.percentage
        : undefined;

  let pct = rawPct ?? prev?.percentage ?? 0;
  if (rawPct === undefined) {
    if (phase === "loading_models") {
      pct = Math.max(pct, 3);
    } else if (phase === "preflight" || phase === "preparing") {
      pct = Math.max(pct, 5);
    } else if (phase === "finalizing" || phase === "post_upscale") {
      pct = Math.max(pct, 95);
    }
  } else if (phase === "complete") {
    pct = 100;
  }

  const monotonic = Math.max(prev?.percentage ?? 0, Math.min(100, Math.round(pct)));

  const incomingTitle = (next.message ?? next.title ?? "").trim();
  const title =
    incomingTitle && !GENERIC_PROGRESS_TITLES.has(incomingTitle)
      ? generationPhaseLabel(phase, incomingTitle)
      : prev?.title ||
        generationPhaseLabel(phase, incomingTitle) ||
        "Generating…";

  return { percentage: monotonic, title };
}

/** Footer status line while generating — prefer structured progress over raw log tail. */
export function generationFooterStatus(
  generating: boolean,
  liveProgress: LiveProgress | null,
  logSummary: string,
): string {
  if (generating && liveProgress?.title) {
    return liveProgress.title;
  }
  return logSummary;
}
