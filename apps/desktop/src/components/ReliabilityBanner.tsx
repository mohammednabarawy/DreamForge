import type { ReactNode } from "react";
import { AlertTriangle, Clipboard, Download, RefreshCw, ShieldCheck, Wrench, X, Zap } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import type { FriendlyError } from "../lib/errors";
import type { RepairAction } from "../lib/tauri-api";

type Props = {
  lastError: FriendlyError | null;
  warnings: FriendlyError[];
  onDismissError: () => void;
  onDismissWarning: (code: string) => void;
  onDismissAllWarnings: () => void;
  onRestartEngine: () => void;
  onDownloadCompanions: () => void;
  onLowerVramProfile: () => void;
  companionDownloadBusy?: boolean;
  restarting?: boolean;
};

function ActionButton({
  onClick,
  disabled,
  children,
}: {
  onClick: () => void;
  disabled?: boolean;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="inline-flex items-center gap-1 rounded-md border border-dfui-border/60 bg-dfui-panel/80 px-2 py-1 text-[10px] font-medium text-dfui-fg transition hover:border-dfui-accent/50 hover:bg-dfui-accent/10 disabled:opacity-50"
    >
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
  if (code === "comfy_server_crashed" || code === "worker_crashed" || code === "worker_pipe_closed") return "Engine failure";
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
    // Clipboard can be unavailable in hardened WebViews; diagnostics remain visible.
  }
}

function ErrorActions({
  error,
  onDismiss,
  onRestartEngine,
  onDownloadCompanions,
  onLowerVramProfile,
  companionDownloadBusy,
  restarting,
}: {
  error: FriendlyError;
  onDismiss: () => void;
  onRestartEngine: () => void;
  onDownloadCompanions: () => void;
  onLowerVramProfile: () => void;
  companionDownloadBusy?: boolean;
  restarting?: boolean;
}) {
  const code = error.code;
  const repairActions = error.failureReport?.repair_actions ?? [];
  const nodeHint = nodeIssueHint(error);
  const downloadable = repairActions.some((a) => a.action === "download_model_companions");
  const installableNodes = repairActions.some((a) => a.action === "install_custom_node_pack");
  const restartable = repairActions.some((a) => a.action === "restart_local_backend");
  const lowerable = repairActions.some(
    (a) => a.action === "switch_vram_profile" || a.action === "reduce_resolution",
  );
  return (
    <motion.div
      initial={{ opacity: 0, y: -6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -6 }}
      className="mx-3 mb-1 rounded-lg border border-rose-500/35 bg-rose-950/35 px-3 py-3 backdrop-blur-md"
    >
      <div className="flex items-start gap-3">
        <div className="mt-0.5 rounded-md border border-rose-400/25 bg-rose-500/10 p-1.5 text-rose-300">
          <AlertTriangle size={15} />
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
          <p className="mt-1 text-xs font-semibold text-rose-100">{error.title}</p>
          <p className="mt-0.5 text-[11px] leading-snug text-dfui-secondary">
            {error.message}
          </p>
          {nodeHint && (
            <p className="mt-1 text-[10px] text-dfui-tertiary">
              Affected step: {nodeHint}
            </p>
          )}
          {error.suggestions.length > 0 && (
            <p className="mt-2 text-[10px] font-medium text-rose-100/90">
              Next step: {error.suggestions[0]}
            </p>
          )}
          {error.suggestions.length > 1 && (
            <ul className="mt-2 grid gap-1 text-[10px] text-dfui-tertiary sm:grid-cols-2">
              {error.suggestions.slice(1, 4).map((s) => (
                <li key={s} className="flex gap-1.5">
                  <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-rose-300/70" />
                  <span>{s}</span>
                </li>
              ))}
            </ul>
          )}
          <div className="mt-2 flex flex-wrap gap-1.5">
            {(code === "worker_crashed" ||
              code === "generation_failed" ||
              code === "comfy_workflow_validation" ||
              code === "comfy_server_crashed" ||
              restartable) && (
              <ActionButton onClick={onRestartEngine} disabled={restarting}>
                <RefreshCw size={11} className={restarting ? "animate-spin" : ""} />
                Restart GPU engine
              </ActionButton>
            )}
            {(code === "missing_model_dependencies" ||
              code === "missing_custom_node_pack" ||
              downloadable ||
              installableNodes) && (
              <ActionButton
                onClick={onDownloadCompanions}
                disabled={companionDownloadBusy}
              >
                <Download size={11} />
                Download assets
              </ActionButton>
            )}
            {(code === "out_of_memory" || lowerable) && (
              <ActionButton onClick={onLowerVramProfile}>
                <Zap size={11} />
                Lower VRAM profile
              </ActionButton>
            )}
            <ActionButton onClick={() => void copyDiagnostics(error)}>
              <Clipboard size={11} />
              Copy diagnostics
            </ActionButton>
            <ActionButton onClick={onDismiss}>
              <X size={11} />
              Dismiss
            </ActionButton>
          </div>
          {repairActions.length > 0 && (
            <div className="mt-2 rounded-md border border-rose-400/20 bg-black/15 px-2.5 py-2">
              <div className="mb-1.5 flex items-center gap-1 text-[10px] font-medium text-rose-100">
                <Wrench size={11} />
                Repair plan
              </div>
              <ul className="space-y-1 text-[10px] text-dfui-tertiary">
                {repairActions.slice(0, 4).map((action, i) => {
                  const hint = repairActionHint(action);
                  return (
                    <li key={`${action.action ?? "repair"}-${i}`} className="flex gap-1.5">
                      <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-rose-300/70" />
                      <span>
                        <span className="text-dfui-secondary">{actionLabel(action)}</span>
                        {hint ? ` - ${hint}` : ""}
                      </span>
                    </li>
                  );
                })}
              </ul>
            </div>
          )}
          {(error.details || error.failureReport) && (
            <details className="mt-2 rounded-md border border-dfui-border/45 bg-black/10 px-2 py-1.5">
              <summary className="cursor-pointer text-[10px] font-medium text-dfui-secondary">
                Technical diagnostics
              </summary>
              <pre className="mt-1 max-h-36 overflow-auto whitespace-pre-wrap break-words rounded bg-black/25 p-2 text-[9px] leading-snug text-dfui-tertiary">
                {diagnosticPayload(error)}
              </pre>
            </details>
          )}
        </div>
      </div>
    </motion.div>
  );
}

export function ReliabilityBanner({
  lastError,
  warnings,
  onDismissError,
  onDismissWarning,
  onDismissAllWarnings,
  onRestartEngine,
  onDownloadCompanions,
  onLowerVramProfile,
  companionDownloadBusy,
  restarting,
}: Props) {
  const hasWarnings = warnings.length > 0;
  if (!lastError && !hasWarnings) return null;

  return (
    <div className="flex flex-col gap-1 pb-1">
      <AnimatePresence mode="popLayout">
        {lastError && (
          <ErrorActions
            key={`err-${lastError.code}`}
            error={lastError}
            onDismiss={onDismissError}
            onRestartEngine={onRestartEngine}
            onDownloadCompanions={onDownloadCompanions}
            onLowerVramProfile={onLowerVramProfile}
            companionDownloadBusy={companionDownloadBusy}
            restarting={restarting}
          />
        )}
      </AnimatePresence>

      <AnimatePresence mode="popLayout">
        {hasWarnings && (
          <motion.div
            key="warnings"
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            className="mx-3 rounded-lg border border-amber-500/30 bg-amber-950/30 px-3 py-2 backdrop-blur-md"
          >
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0 flex-1 space-y-1.5">
                {warnings.map((w) => (
                  <div key={w.code} className="flex gap-2">
                    <AlertTriangle
                      size={13}
                      className="mt-0.5 shrink-0 text-amber-400"
                    />
                    <div className="min-w-0">
                      <p className="text-[11px] font-medium text-amber-100">
                        {w.title}
                      </p>
                      <p className="text-[10px] leading-snug text-dfui-secondary">
                        {w.message}
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => onDismissWarning(w.code)}
                      className="shrink-0 text-dfui-tertiary hover:text-dfui-fg"
                      aria-label="Dismiss warning"
                    >
                      <X size={12} />
                    </button>
                  </div>
                ))}
              </div>
              {warnings.length > 1 && (
                <button
                  type="button"
                  onClick={onDismissAllWarnings}
                  className="shrink-0 text-[10px] text-dfui-muted hover:text-dfui-fg"
                >
                  Dismiss all
                </button>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
