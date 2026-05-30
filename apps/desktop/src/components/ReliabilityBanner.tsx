import type { ReactNode } from "react";
import { AlertTriangle, Download, RefreshCw, ShieldCheck, Wrench, X, Zap } from "lucide-react";
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
  const downloadable = repairActions.some((a) => a.action === "download_model_companions");
  const restartable = repairActions.some((a) => a.action === "restart_local_backend");
  const lowerable = repairActions.some(
    (a) => a.action === "switch_vram_profile" || a.action === "reduce_resolution",
  );
  return (
    <motion.div
      initial={{ opacity: 0, y: -6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -6 }}
      className="mx-3 mb-1 rounded-lg border border-rose-500/35 bg-rose-950/40 px-3 py-2.5 backdrop-blur-md"
    >
      <motion.div layout className="flex items-start gap-2">
        <AlertTriangle size={15} className="mt-0.5 shrink-0 text-rose-400" />
        <motion.div layout className="min-w-0 flex-1">
          <p className="text-xs font-medium text-rose-100">{error.title}</p>
          <p className="mt-0.5 text-[11px] leading-snug text-dfui-secondary">
            {error.message}
          </p>
          {error.suggestions.length > 0 && (
            <ul className="mt-1.5 list-inside list-disc space-y-0.5 text-[10px] text-dfui-tertiary">
              {error.suggestions.slice(0, 3).map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ul>
          )}
          {repairActions.length > 0 && (
            <div className="mt-2 rounded-md border border-rose-400/20 bg-black/15 px-2 py-1.5">
              <div className="mb-1 flex items-center gap-1 text-[10px] font-medium text-rose-100">
                <Wrench size={11} />
                Repair plan
                {error.failureReport?.requires_user_approval && (
                  <span className="inline-flex items-center gap-1 rounded border border-amber-400/30 px-1 text-[9px] text-amber-200">
                    <ShieldCheck size={9} />
                    Approval required
                  </span>
                )}
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
          <div className="mt-2 flex flex-wrap gap-1.5">
            {(code === "worker_crashed" ||
              code === "generation_failed" ||
              code === "comfy_server_crashed" ||
              restartable) && (
              <ActionButton onClick={onRestartEngine} disabled={restarting}>
                <RefreshCw size={11} className={restarting ? "animate-spin" : ""} />
                Restart GPU engine
              </ActionButton>
            )}
            {(code === "missing_model_dependencies" || downloadable) && (
              <ActionButton
                onClick={onDownloadCompanions}
                disabled={companionDownloadBusy}
              >
                <Download size={11} />
                Download companions
              </ActionButton>
            )}
            {(code === "out_of_memory" || lowerable) && (
              <ActionButton onClick={onLowerVramProfile}>
                <Zap size={11} />
                Lower VRAM profile
              </ActionButton>
            )}
            <ActionButton onClick={onDismiss}>
              <X size={11} />
              Dismiss
            </ActionButton>
          </div>
        </motion.div>
      </motion.div>
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
