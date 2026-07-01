import { useEffect, type ReactNode } from "react";
import {
  AlertTriangle,
  Clipboard,
  Download,
  RefreshCw,
  ScrollText,
  ShieldCheck,
  Wrench,
  X,
  Zap,
} from "lucide-react";
import type { FriendlyError } from "../lib/errors";
import type { RepairAction } from "../lib/tauri-api";

type Props = {
  error: FriendlyError | null;
  workerLogTail?: string;
  onDismiss: () => void;
  onRestartEngine: () => void;
  onDownloadCompanions: () => void;
  onLowerVramProfile: () => void;
  onOpenFullLog?: () => void;
  companionDownloadBusy?: boolean;
  restarting?: boolean;
};

const ENGINE_FAILURE_CODES = new Set([
  "worker_boot_failed",
  "worker_crashed",
  "worker_pipe_closed",
  "comfy_server_crashed",
]);

function ActionButton({
  onClick,
  disabled,
  variant = "secondary",
  children,
}: {
  onClick: () => void;
  disabled?: boolean;
  variant?: "primary" | "secondary";
  children: ReactNode;
}) {
  const base =
    "inline-flex items-center justify-center gap-1.5 rounded-lg px-3 py-2 text-xs font-medium transition disabled:opacity-50";
  const styles =
    variant === "primary"
      ? "border border-rose-400/40 bg-rose-500/20 text-rose-50 hover:bg-rose-500/30"
      : "border border-dfui-border/60 bg-dfui-panel/80 text-dfui-fg hover:border-dfui-accent/45 hover:bg-dfui-accent/10";
  return (
    <button type="button" onClick={onClick} disabled={disabled} className={`${base} ${styles}`}>
      {children}
    </button>
  );
}

function actionLabel(action: RepairAction) {
  switch (action.action) {
    case "download_model_companions":
      return "Download missing assets";
    case "install_custom_node_pack":
      return `Install ${String(action.pack_id ?? "custom node pack")}`;
    case "replace_node_pattern":
      return "Rebuild with fallback nodes";
    case "disable_optional_stage":
      return "Disable optional stage";
    case "restart_local_backend":
      return "Restart local backend";
    case "reduce_resolution":
      return "Reduce resolution";
    case "reduce_batch":
      return "Use single image";
    case "switch_vram_profile":
      return `Switch VRAM profile${action.vram_profile ? ` to ${action.vram_profile}` : ""}`;
    case "switch_model_route":
      return "Switch local model";
    case "retry_with_safer_settings":
      return "Retry with safer settings";
    case "request_input":
      return "Attach required input";
    case "reimport_asset":
      return "Re-import asset";
    case "rebuild_workflow_plan":
      return "Rebuild workflow plan";
    case "inspect_logs":
      return "Inspect logs";
    default:
      return String(action.action ?? "Repair action");
  }
}

function repairActionHint(action: RepairAction) {
  if (typeof action.hint === "string" && action.hint.trim()) return action.hint;
  if (Array.isArray(action.nodes) && action.nodes.length > 0) {
    return `Nodes: ${action.nodes.slice(0, 3).join(", ")}`;
  }
  if (Array.isArray(action.missing) && action.missing.length > 0) {
    return `${action.missing.length} file(s)`;
  }
  return "";
}

function categoryLabel(code: string) {
  if (code === "comfy_workflow_validation") return "Workflow validation";
  if (code === "missing_model_dependencies") return "Missing component";
  if (code === "missing_custom_node_pack") return "Custom node failure";
  if (code === "out_of_memory" || code === "virtual_memory_low") return "Memory pressure";
  if (code === "comfy_server_crashed" || code === "worker_crashed" || code === "worker_pipe_closed" || code === "worker_boot_failed") {
    return "Engine failure";
  }
  if (code === "unsupported_workflow_class") return "Workflow incompatible";
  if (code === "missing_input_image" || code === "invalid_input_image") return "Input required";
  return "Generation issue";
}

function nodeIssueHint(error: FriendlyError): string | null {
  const issues = error.details?.node_issues;
  if (!Array.isArray(issues) || issues.length === 0) return null;
  const first = issues[0] as { nodeLabel?: string; issue?: string };
  if (first?.nodeLabel && first?.issue) {
    return `${first.nodeLabel}: ${first.issue}`;
  }
  return null;
}

function diagnosticPayload(error: FriendlyError) {
  return JSON.stringify(
    {
      code: error.code,
      title: error.title,
      message: error.message,
      recoverable: error.recoverable,
      details: error.details ?? null,
      failure_report: error.failureReport ?? null,
    },
    null,
    2,
  );
}

async function copyDiagnostics(error: FriendlyError) {
  try {
    await navigator.clipboard.writeText(diagnosticPayload(error));
  } catch {
    // Clipboard can be unavailable in hardened WebViews.
  }
}

function primaryAction(
  error: FriendlyError,
  handlers: {
    onRestartEngine: () => void;
    onDownloadCompanions: () => void;
    onLowerVramProfile: () => void;
    restarting?: boolean;
    companionDownloadBusy?: boolean;
  },
): { label: string; onClick: () => void; disabled?: boolean; icon: ReactNode } | null {
  const code = error.code;
  const repairActions = error.failureReport?.repair_actions ?? [];
  const downloadable = repairActions.some((a) => a.action === "download_model_companions");
  const installableNodes = repairActions.some((a) => a.action === "install_custom_node_pack");
  const restartable = repairActions.some((a) => a.action === "restart_local_backend");

  if (
    code === "missing_model_dependencies" ||
    code === "missing_custom_node_pack" ||
    downloadable ||
    installableNodes
  ) {
    return {
      label: "Download missing assets",
      onClick: handlers.onDownloadCompanions,
      disabled: handlers.companionDownloadBusy,
      icon: <Download size={14} />,
    };
  }
  if (code === "out_of_memory" || code === "virtual_memory_low") {
    return {
      label: "Lower VRAM profile",
      onClick: handlers.onLowerVramProfile,
      icon: <Zap size={14} />,
    };
  }
  if (
    code === "worker_boot_failed" ||
    code === "worker_crashed" ||
    code === "generation_failed" ||
    code === "comfy_workflow_validation" ||
    code === "comfy_server_crashed" ||
    code === "worker_pipe_closed" ||
    restartable
  ) {
    return {
      label: "Restart GPU engine",
      onClick: handlers.onRestartEngine,
      disabled: handlers.restarting,
      icon: <RefreshCw size={14} className={handlers.restarting ? "animate-spin" : ""} />,
    };
  }
  return null;
}

function workerLogPreview(error: FriendlyError, workerLogTail?: string): string {
  const fromDetails =
    typeof error.details?.worker_log_tail === "string"
      ? error.details.worker_log_tail
      : "";
  return (workerLogTail || fromDetails).trim();
}

export function EngineFailureModal({
  error,
  workerLogTail,
  onDismiss,
  onRestartEngine,
  onDownloadCompanions,
  onLowerVramProfile,
  onOpenFullLog,
  companionDownloadBusy,
  restarting,
}: Props) {
  useEffect(() => {
    if (!error?.recoverable) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onDismiss();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [error, onDismiss]);

  if (!error) return null;

  const code = error.code;
  const repairActions = error.failureReport?.repair_actions ?? [];
  const nodeHint = nodeIssueHint(error);
  const primary = primaryAction(error, {
    onRestartEngine,
    onDownloadCompanions,
    onLowerVramProfile,
    restarting,
    companionDownloadBusy,
  });
  const logPreview = workerLogPreview(error, workerLogTail);
  const showWorkerLog = ENGINE_FAILURE_CODES.has(code) && logPreview.length > 0;

  const handleBackdrop = () => {
    if (error.recoverable) onDismiss();
  };

  return (
    <div
      className="fixed inset-0 z-[70] flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="engine-failure-title"
      aria-describedby="engine-failure-message"
      onClick={handleBackdrop}
    >
      <div
        className="flex max-h-[min(88vh,42rem)] w-full max-w-lg flex-col overflow-hidden rounded-xl border border-rose-500/25 bg-dfui-panel shadow-2xl animate-fade-in"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start gap-3 border-b border-dfui-border/50 bg-rose-950/25 px-4 py-4">
          <div className="mt-0.5 rounded-lg border border-rose-400/25 bg-rose-500/10 p-2 text-rose-300">
            <AlertTriangle size={18} />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="rounded border border-rose-400/25 bg-rose-500/10 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-rose-200">
                {categoryLabel(code)}
              </span>
              <span className="rounded border border-dfui-border/50 px-1.5 py-0.5 text-[9px] text-dfui-tertiary">
                {error.recoverable ? "Recoverable" : "Needs manual repair"}
              </span>
              {error.failureReport?.requires_user_approval && (
                <span className="inline-flex items-center gap-1 rounded border border-amber-400/30 px-1.5 py-0.5 text-[9px] text-amber-200">
                  <ShieldCheck size={9} />
                  Approval required
                </span>
              )}
            </div>
            <h2 id="engine-failure-title" className="mt-2 text-sm font-semibold text-dfui-fg">
              {error.title}
            </h2>
          </div>
          <button
            type="button"
            onClick={onDismiss}
            className="rounded-md p-1 text-dfui-tertiary transition hover:bg-dfui-surface hover:text-dfui-fg"
            aria-label="Dismiss"
          >
            <X size={18} />
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
          <p id="engine-failure-message" className="text-sm leading-relaxed text-dfui-secondary">
            {error.message}
          </p>
          {nodeHint && (
            <p className="mt-2 text-xs text-dfui-tertiary">Affected step: {nodeHint}</p>
          )}
          {showWorkerLog && (
            <div className="mt-4">
              <pre className="max-h-28 overflow-auto whitespace-pre-wrap rounded-lg border border-dfui-border bg-dfui-bg p-2.5 text-[10px] leading-snug text-dfui-tertiary">
                {logPreview.slice(-1200)}
              </pre>
              {onOpenFullLog && (
                <button
                  type="button"
                  onClick={onOpenFullLog}
                  className="mt-2 inline-flex items-center gap-1.5 rounded-md px-1 py-0.5 text-xs text-dfui-tertiary transition hover:bg-dfui-surface hover:text-dfui-fg"
                >
                  <ScrollText size={14} strokeWidth={1.75} />
                  View worker log
                </button>
              )}
            </div>
          )}
          {error.suggestions.length > 0 && (
            <div className="mt-4 rounded-lg border border-dfui-border/45 bg-dfui-surface/30 px-3 py-2.5">
              <p className="text-[10px] font-semibold uppercase tracking-wide text-dfui-muted">
                Suggested next steps
              </p>
              <ul className="mt-2 space-y-1.5 text-xs text-dfui-secondary">
                {error.suggestions.slice(0, 4).map((suggestion) => (
                  <li key={suggestion} className="flex gap-2">
                    <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-rose-300/70" />
                    <span>{suggestion}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {repairActions.length > 0 && (
            <div className="mt-4 rounded-lg border border-rose-400/20 bg-black/15 px-3 py-2.5">
              <div className="mb-1.5 flex items-center gap-1 text-xs font-medium text-rose-100">
                <Wrench size={12} />
                Repair plan
              </div>
              <ul className="space-y-1 text-[11px] text-dfui-tertiary">
                {repairActions.slice(0, 4).map((action, index) => {
                  const hint = repairActionHint(action);
                  return (
                    <li key={`${action.action ?? "repair"}-${index}`} className="flex gap-2">
                      <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-rose-300/70" />
                      <span>
                        <span className="text-dfui-secondary">{actionLabel(action)}</span>
                        {hint ? ` — ${hint}` : ""}
                      </span>
                    </li>
                  );
                })}
              </ul>
            </div>
          )}
          {(error.details || error.failureReport) && (
            <details className="mt-4 rounded-lg border border-dfui-border/45 bg-black/10 px-3 py-2">
              <summary className="cursor-pointer text-xs font-medium text-dfui-secondary">
                Technical diagnostics
              </summary>
              <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap break-words rounded bg-black/25 p-2 text-[10px] leading-snug text-dfui-tertiary">
                {diagnosticPayload(error)}
              </pre>
            </details>
          )}
        </div>

        <div className="flex flex-wrap items-center justify-end gap-2 border-t border-dfui-border/50 bg-dfui-panel/80 px-4 py-3">
          <ActionButton onClick={() => void copyDiagnostics(error)}>
            <Clipboard size={13} />
            Copy diagnostics
          </ActionButton>
          <ActionButton onClick={onDismiss}>Dismiss</ActionButton>
          {primary && (
            <ActionButton
              variant="primary"
              onClick={primary.onClick}
              disabled={primary.disabled}
            >
              {primary.icon}
              {primary.label}
            </ActionButton>
          )}
        </div>
      </div>
    </div>
  );
}
