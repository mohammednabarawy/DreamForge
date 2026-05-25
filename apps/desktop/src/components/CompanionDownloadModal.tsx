import { useEffect, useRef } from "react";
import { AlertCircle, CheckCircle2, Download, Loader2, X } from "lucide-react";
import type {
  CompanionDownloadLine,
  CompanionDownloadPhase,
} from "../hooks/useCompanionDownload";
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
  onClose: () => void;
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

export function CompanionDownloadModal({
  open,
  phase,
  lines,
  currentIndex,
  totalCount,
  currentItem,
  fileProgress,
  modelName,
  onClose,
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

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/65 backdrop-blur-sm">
      <div className="flex h-[82vh] w-[92vw] max-w-3xl flex-col rounded-xl border border-dfui-border bg-dfui-panel shadow-2xl">
        <div className="flex items-center justify-between gap-3 border-b border-dfui-border/50 px-4 py-3">
          <div className="flex min-w-0 items-center gap-2">
            {phase === "done" ? (
              <CheckCircle2 size={18} className="shrink-0 text-emerald-400" />
            ) : phase === "error" ? (
              <AlertCircle size={18} className="shrink-0 text-amber-400" />
            ) : (
              <Download
                size={18}
                className={`shrink-0 text-df-blue ${running ? "animate-pulse" : ""}`}
              />
            )}
            <div className="min-w-0">
              <h2 className="truncate text-sm font-semibold text-dfui-fg">
                Companion downloads
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
          <div className="flex items-center justify-between text-xs text-dfui-muted">
            <span>
              {running
                ? `File ${currentIndex} of ${totalCount || "—"}`
                : totalCount > 0
                  ? `Processed ${totalCount} file(s)`
                  : "Ready"}
            </span>
            {running && <Loader2 size={14} className="animate-spin text-df-blue" />}
          </div>
          <div>
            <p className="mb-1 truncate font-mono text-[11px] text-dfui-fg">{fileName}</p>
            <div className="h-2 overflow-hidden rounded-full bg-dfui-bg">
              <div
                className="h-full rounded-full bg-gradient-to-r from-df-blue to-df-orange transition-all duration-300"
                style={{ width: `${Math.min(100, Math.max(0, pct))}%` }}
              />
            </div>
            <p className="mt-1 text-[10px] text-dfui-muted">
              {fileProgress?.downloaded != null && fileProgress?.total != null
                ? `${formatBytes(fileProgress.downloaded)} / ${formatBytes(fileProgress.total)} (${pct}%)`
                : running
                  ? "Starting transfer…"
                  : "—"}
            </p>
          </div>
        </div>

        <div className="relative min-h-0 flex-1 overflow-hidden">
          <pre
            className="h-full overflow-auto whitespace-pre-wrap break-all bg-dfui-bg/80 p-4 font-mono text-[11px] leading-relaxed"
            onScroll={(e) => {
              const el = e.currentTarget;
              const atBottom =
                el.scrollHeight - el.scrollTop - el.clientHeight < 48;
              autoScrollRef.current = atBottom;
            }}
          >
            {lines.length === 0 ? (
              <span className="text-dfui-muted">Preparing download log…</span>
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

        <div className="flex items-center justify-end gap-2 border-t border-dfui-border/50 px-4 py-3">
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
