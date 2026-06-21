import { useEffect, useRef } from "react";
import {
  AlertCircle,
  CheckCircle2,
  ClipboardCopy,
  Download,
  ExternalLink,
  FileDown,
  HardDrive,
  Info,
  Loader2,
  X,
} from "lucide-react";
import type {
  CompanionDownloadLine,
  CompanionDownloadPhase,
} from "../hooks/useCompanionDownload";
import { latestActivityLine } from "../lib/loadingMessages";
import type { DownloadProgressPayload, ModelDependencyItem } from "../lib/tauri-api";

type Props = {
  open: boolean;
  phase: CompanionDownloadPhase;
  lines: CompanionDownloadLine[];
  currentIndex: number;
  totalCount: number;
  currentItem: ModelDependencyItem | null;
  fileProgress: DownloadProgressPayload | null;
  modelName: string;
  pendingMissing: ModelDependencyItem[];
  onClose: () => void;
  onApprove: () => void;
  onCopyLinks: () => void;
  onCopyManualList: () => void;
  onRetry: () => void;
};

function lineClass(level: CompanionDownloadLine["level"]): string {
  switch (level) {
    case "ok":
      return "text-emerald-400/90";
    case "warn":
      return "text-amber-300/90";
    case "error":
      return "text-red-300/90";
    default:
      return "text-dfui-secondary";
  }
}

function formatBytes(n: number): string {
  if (n <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  let v = n;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i += 1;
  }
  return `${v < 10 && i > 0 ? v.toFixed(1) : Math.round(v)} ${units[i]}`;
}

function assetLabel(item: ModelDependencyItem | null, fallback: string): string {
  return item?.filename ?? item?.id ?? fallback;
}

function assetDestination(item: ModelDependencyItem | null, progress: DownloadProgressPayload | null): string {
  if (progress?.path) return progress.path;
  if (item?.expected_path) return item.expected_path;
  if (item?.relative) return item.relative;
  if (item?.category || item?.filename) {
    return `${item?.category ?? "models"}/${item?.filename ?? ""}`.replace(/\/$/, "");
  }
  return "DreamForge models folder";
}

function phaseMessage(phase: CompanionDownloadPhase, pct: number): string {
  if (phase === "confirm") return "Review what DreamForge needs before anything is downloaded.";
  if (phase === "done") return "Downloads finished and DreamForge verified the required files.";
  if (phase === "error") return "Some files still need attention. You can retry or install them manually.";
  if (phase === "running") {
    if (pct <= 0) return "Connecting to the model host and preparing the transfer.";
    if (pct < 100) return "Downloading the current file. Large models can take several minutes.";
    return "Finishing this file and checking it on disk.";
  }
  return "Ready.";
}

export function CompanionDownloadModal({
  open,
  phase,
  lines,
  currentIndex,
  totalCount,
  currentItem,
  fileProgress,
  modelName,
  pendingMissing,
  onClose,
  onApprove,
  onCopyLinks,
  onCopyManualList,
  onRetry,
}: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const autoScrollRef = useRef(true);

  useEffect(() => {
    if (autoScrollRef.current) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [lines, fileProgress]);

  if (!open) return null;

  const running = phase === "running";
  const confirming = phase === "confirm";
  const pct =
    fileProgress?.percentage ??
    (fileProgress?.status === "complete" || fileProgress?.status === "exists"
      ? 100
      : 0);
  const fileName =
    fileProgress?.filename ??
    currentItem?.filename ??
    currentItem?.id ??
    "—";
  const downloadableCount = pendingMissing.filter((item) => item.url).length;
  const customNodeCount = pendingMissing.filter((item) => item.kind === "custom_node_pack").length;
  const canApprove = pendingMissing.length > 0 && (downloadableCount > 0 || customNodeCount > 0);
  const fileDownloaded = fileProgress?.downloaded ?? 0;
  const fileTotal = fileProgress?.total ?? 0;
  const overallPct =
    totalCount > 0
      ? Math.min(
          100,
          Math.max(
            0,
            Math.round((((Math.max(0, currentIndex - 1) + pct / 100) / totalCount) * 100)),
          ),
        )
      : phase === "done"
        ? 100
        : 0;
  const destination = assetDestination(currentItem, fileProgress);
  const latestLine = latestActivityLine(lines, "");
  const friendlyStatus =
    running && latestLine
      ? latestLine
      : phaseMessage(phase, pct);

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/65 backdrop-blur-sm">
      <div className="flex h-[82vh] w-[92vw] max-w-3xl flex-col rounded-xl border border-dfui-border bg-dfui-panel shadow-2xl">
        <div className="flex items-center justify-between gap-3 border-b border-dfui-border/50 px-4 py-3">
          <div className="flex min-w-0 items-center gap-2">
            {phase === "done" ? (
              <CheckCircle2 size={18} className="shrink-0 text-emerald-400" />
            ) : phase === "error" ? (
              <AlertCircle size={18} className="shrink-0 text-amber-400" />
            ) : confirming ? (
              <AlertCircle size={18} className="shrink-0 text-df-orange" />
            ) : (
              <Download
                size={18}
                className={`shrink-0 text-df-blue ${running ? "animate-pulse" : ""}`}
              />
            )}
            <div className="min-w-0">
              <h2 className="truncate text-sm font-semibold text-dfui-fg">
                {confirming ? "Approve missing asset downloads" : "Companion downloads"}
              </h2>
              <p className="truncate font-mono text-[10px] text-dfui-muted">
                {modelName || "—"}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={running}
            className="rounded-md p-1 text-dfui-tertiary transition hover:bg-dfui-surface hover:text-dfui-fg disabled:cursor-not-allowed disabled:opacity-40"
            title={running ? "Wait for downloads to finish" : "Close"}
          >
            <X size={18} />
          </button>
        </div>

        <div className="space-y-3 border-b border-dfui-border/40 px-4 py-3">
          <div className="grid gap-2 md:grid-cols-[1.2fr_0.8fr]">
            <div className="rounded-lg border border-dfui-border/45 bg-dfui-bg/35 px-3 py-2">
              <div className="mb-1 flex items-center gap-2">
                {running ? (
                  <Loader2 size={14} className="animate-spin text-df-blue" />
                ) : phase === "done" ? (
                  <CheckCircle2 size={14} className="text-emerald-400" />
                ) : (
                  <Info size={14} className="text-df-orange" />
                )}
                <p className="text-xs font-medium text-dfui-fg">
                  {confirming
                    ? `${pendingMissing.length} asset(s) need approval`
                    : running
                      ? `Downloading asset ${currentIndex} of ${totalCount || "—"}`
                      : phase === "done"
                        ? "Assets ready"
                        : phase === "error"
                          ? "Action needed"
                          : "Ready"}
                </p>
              </div>
              <p className="text-[11px] leading-snug text-dfui-secondary">
                {friendlyStatus}
              </p>
            </div>
            <div className="rounded-lg border border-dfui-border/45 bg-dfui-bg/35 px-3 py-2">
              <div className="mb-1 flex items-center gap-2">
                <HardDrive size={14} className="text-df-blue" />
                <p className="text-xs font-medium text-dfui-fg">Install location</p>
              </div>
              <p className="truncate font-mono text-[10px] text-dfui-muted" title={destination}>
                {destination}
              </p>
            </div>
          </div>

          <div>
            <div className="mb-1 flex items-center justify-between gap-2">
              <p className="truncate font-mono text-[11px] text-dfui-fg" title={fileName}>
                {assetLabel(currentItem, fileName)}
              </p>
              <span className="shrink-0 font-mono text-[10px] text-dfui-muted">
                {overallPct}% overall
              </span>
            </div>
            <div className="mb-2 h-1.5 overflow-hidden rounded-full bg-dfui-bg">
              <div
                className="h-full rounded-full bg-df-blue/80 transition-all duration-300"
                style={{ width: `${overallPct}%` }}
              />
            </div>
            <div className="mb-1 flex items-center justify-between gap-2">
              <span className="inline-flex min-w-0 items-center gap-1.5 text-[10px] text-dfui-muted">
                <FileDown size={11} className="shrink-0 text-df-orange" />
                Current file
              </span>
              <span className="shrink-0 font-mono text-[10px] text-dfui-muted">
                {Math.min(100, Math.max(0, pct))}%
              </span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-dfui-bg">
              <div
                className="h-full rounded-full bg-gradient-to-r from-df-blue to-df-orange transition-all duration-300"
                style={{ width: `${Math.min(100, Math.max(0, pct))}%` }}
              />
            </div>
            <p className="mt-1 text-[10px] text-dfui-muted">
              {confirming
                ? "DreamForge will not download anything until you approve. You can also copy the links and install them manually."
                : fileDownloaded > 0 || fileTotal > 0
                ? `${formatBytes(fileDownloaded)}${fileTotal > 0 ? ` / ${formatBytes(fileTotal)}` : ""} downloaded`
                : running
                  ? latestLine || "Starting transfer…"
                  : "—"}
            </p>
          </div>
        </div>

        {confirming && pendingMissing.length > 0 && (
          <div className="max-h-52 overflow-y-auto border-b border-dfui-border/40 bg-dfui-bg/35 px-4 py-3">
            <div className="mb-2 flex items-center justify-between gap-2">
              <p className="text-[10px] font-semibold uppercase tracking-wide text-dfui-muted">
                Required local assets
              </p>
              <p className="text-[10px] text-dfui-tertiary">
                {downloadableCount}/{pendingMissing.length} with direct links
              </p>
            </div>
            <ul className="space-y-2">
              {pendingMissing.map((item, index) => (
                <li
                  key={`${item.id ?? item.relative ?? item.filename ?? "asset"}-${index}`}
                  className="rounded-lg border border-dfui-border/45 bg-dfui-panel/55 px-3 py-2"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="truncate text-xs font-medium text-dfui-fg">
                        {item.filename ?? item.id ?? "Required asset"}
                      </p>
                      <p className="mt-0.5 truncate font-mono text-[10px] text-dfui-muted">
                        {item.relative ?? item.expected_path ?? item.category ?? "models"}
                      </p>
                    </div>
                    {item.url ? (
                      <a
                        href={item.url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex shrink-0 items-center gap-1 rounded-md border border-dfui-border/60 px-2 py-1 text-[10px] text-dfui-secondary transition hover:border-df-blue/50 hover:text-df-blue"
                        title="Open download link"
                      >
                        <ExternalLink size={11} />
                        Link
                      </a>
                    ) : (
                      <span className="shrink-0 rounded-md border border-amber-400/30 px-2 py-1 text-[10px] text-amber-200">
                        Manual
                      </span>
                    )}
                  </div>
                  {item.note && (
                    <p className="mt-1 text-[10px] leading-snug text-dfui-tertiary">
                      {item.note}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="relative min-h-0 flex-1 overflow-hidden">
          <div className="flex h-full flex-col bg-dfui-bg/80">
            <div className="flex items-center justify-between border-b border-dfui-border/35 px-4 py-2">
              <p className="text-[10px] font-semibold uppercase tracking-wide text-dfui-muted">
                Detailed activity
              </p>
              <p className="text-[10px] text-dfui-tertiary">
                Useful if a download stalls or fails
              </p>
            </div>
            <pre
              className="min-h-0 flex-1 overflow-auto whitespace-pre-wrap break-all p-4 font-mono text-[11px] leading-relaxed"
              onScroll={(e) => {
                const el = e.currentTarget;
                const atBottom =
                  el.scrollHeight - el.scrollTop - el.clientHeight < 48;
                autoScrollRef.current = atBottom;
              }}
            >
              {lines.length === 0 ? (
                <span className="text-dfui-muted">
                  {confirming
                    ? `Reviewing ${pendingMissing.length} required asset(s)…`
                    : "Preparing download details…"}
                </span>
              ) : (
                lines.map((line, i) => (
                  <div key={`${line.ts}-${i}`} className={lineClass(line.level)}>
                    {line.text}
                  </div>
                ))
              )}
              <div ref={bottomRef} />
            </pre>
          </div>
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-dfui-border/50 px-4 py-3">
          {confirming && (
            <>
              <button
                type="button"
                onClick={onCopyLinks}
                disabled={downloadableCount === 0}
                className="inline-flex items-center gap-1.5 rounded-lg border border-dfui-border px-3 py-1.5 text-xs font-medium text-dfui-fg hover:bg-dfui-surface disabled:cursor-not-allowed disabled:opacity-50"
              >
                <ClipboardCopy size={13} />
                Copy links
              </button>
              <button
                type="button"
                onClick={onCopyManualList}
                className="inline-flex items-center gap-1.5 rounded-lg border border-dfui-border px-3 py-1.5 text-xs font-medium text-dfui-fg hover:bg-dfui-surface"
              >
                <ClipboardCopy size={13} />
                Copy manual list
              </button>
              <button
                type="button"
                onClick={onApprove}
                disabled={!canApprove}
                title={
                  !canApprove
                    ? "No installable assets are configured for this request"
                    : undefined
                }
                className="rounded-lg bg-df-blue px-3 py-1.5 text-xs font-semibold text-white hover:bg-df-blue/90 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {customNodeCount > 0 && downloadableCount === 0
                  ? `Install ${customNodeCount} node pack(s)`
                  : customNodeCount > 0
                    ? `Install & download ${pendingMissing.length} item(s)`
                    : downloadableCount
                      ? `Download ${downloadableCount} file(s)`
                      : "Install files"}
              </button>
            </>
          )}
          {phase === "error" && (
            <button
              type="button"
              onClick={onRetry}
              className="rounded-lg border border-df-blue/50 bg-df-blue/15 px-3 py-1.5 text-xs font-semibold text-df-blue hover:bg-df-blue/25"
            >
              Retry failed
            </button>
          )}
          <button
            type="button"
            onClick={onClose}
            disabled={running}
            className="rounded-lg border border-dfui-border px-4 py-1.5 text-xs font-medium text-dfui-fg hover:bg-dfui-surface disabled:cursor-not-allowed disabled:opacity-40"
          >
            {running ? "Downloading…" : "Close"}
          </button>
        </div>
      </div>
    </div>
  );
}
