import { Check, Play, X } from "lucide-react";
import type { AgentPlanSnapshot } from "../lib/studioBridge";
import {
  canRunApprovedPlan,
  labelRequiredInput,
  plannedModelLabel,
  requiredInputRows,
} from "../lib/workflowPlanActions";

type Props = {
  plan: AgentPlanSnapshot;
  applied?: boolean;
  approvalRequired?: boolean;
  runBusy?: boolean;
  canRunGeneration?: boolean;
  runBlockReason?: string;
  onApply?: () => void;
  onRun?: () => void;
  onDismiss?: () => void;
  onDownloadCompanions?: () => void;
  companionDownloadBusy?: boolean;
};

function ReadinessBadge({ ready }: { ready?: boolean }) {
  if (ready === undefined) return null;
  return (
    <span
      className={
        ready
          ? "rounded bg-emerald-500/15 px-1.5 py-0.5 text-[9px] font-medium uppercase tracking-wide text-emerald-300"
          : "rounded bg-amber-500/15 px-1.5 py-0.5 text-[9px] font-medium uppercase tracking-wide text-amber-300"
      }
    >
      {ready ? "Ready" : "Needs setup"}
    </span>
  );
}

export function WorkflowPlanPanel({
  plan,
  applied,
  approvalRequired = true,
  runBusy,
  canRunGeneration = true,
  runBlockReason,
  onApply,
  onRun,
  onDismiss,
  onDownloadCompanions,
  companionDownloadBusy,
}: Props) {
  const blueprint = plan.workflow_blueprint as
    | { template_ids?: string[]; templates?: Record<string, { title?: string; builder?: string }> }
    | undefined;
  const templateIds = blueprint?.template_ids ?? [];
  const templates = blueprint?.templates ?? {};
  const readiness = plan.readiness;
  const steps = plan.workflow_plan ?? [];
  const modelLabel = plannedModelLabel(plan);
  const inputRows = requiredInputRows(readiness);
  const missingInputs = readiness?.missing_inputs ?? [];
  const presetApplied = plan.dynamic_preset?.applied ?? {};
  const presetEntries = Object.entries(presetApplied).filter(
    ([, value]) => value !== undefined && value !== null && value !== "",
  );
  const presetSources = plan.dynamic_preset?.source ?? [];
  const runCheck = canRunApprovedPlan(plan, readiness);
  const runDisabled =
    runBusy ||
    !runCheck.ok ||
    !canRunGeneration ||
    Boolean(runBlockReason && !runCheck.ok);

  return (
    <div className="absolute right-4 top-4 z-20 flex max-h-[55%] w-[min(22rem,90vw)] flex-col gap-2 overflow-hidden rounded-lg border border-dfui-border bg-dfui-bg/90 p-3 shadow-lg backdrop-blur-sm">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <p className="font-mono text-[9px] uppercase tracking-wider text-dfui-tertiary">
            Agent plan {applied ? "(applied)" : "(preview)"}
            {approvalRequired ? " · approval required" : ""}
          </p>
          <p className="text-xs font-medium text-dfui-fg">{plan.message}</p>
          {plan.mode && (
            <p className="mt-0.5 font-mono text-[10px] text-dfui-secondary">
              Mode: {plan.mode}
              {plan.source ? ` · ${plan.source}` : ""}
            </p>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <ReadinessBadge ready={readiness?.ready} />
          {onDismiss && (
            <button
              type="button"
              onClick={onDismiss}
              className="rounded p-0.5 text-dfui-tertiary hover:bg-dfui-surface hover:text-dfui-fg"
              title="Dismiss plan"
            >
              <X size={14} />
            </button>
          )}
        </div>
      </div>

      {modelLabel && (
        <div>
          <p className="mb-1 font-mono text-[9px] uppercase tracking-wider text-dfui-tertiary">
            Selected model
          </p>
          <p className="rounded border border-dfui-border/60 bg-dfui-surface/40 px-2 py-1 font-mono text-[10px] text-dfui-fg">
            {modelLabel}
          </p>
        </div>
      )}

      {presetEntries.length > 0 && (
        <div>
          <p className="mb-1 font-mono text-[9px] uppercase tracking-wider text-dfui-tertiary">
            Style preset
            {presetSources.length > 0
              ? ` · ${presetSources.join(", ").replace(/_/g, " ")}`
              : ""}
          </p>
          <ul className="space-y-1">
            {presetEntries.map(([key, value]) => (
              <li
                key={key}
                className="rounded border border-dfui-border/60 bg-dfui-surface/40 px-2 py-1 font-mono text-[10px] text-dfui-secondary"
              >
                <span className="text-dfui-tertiary">{key}: </span>
                <span className="text-dfui-fg">{String(value)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {(inputRows.length > 0 || missingInputs.length > 0) && (
        <div>
          <p className="mb-1 font-mono text-[9px] uppercase tracking-wider text-dfui-tertiary">
            Required inputs
          </p>
          <ul className="space-y-1">
            {(inputRows.length ? inputRows : missingInputs.map((name) => ({
              name,
              label: labelRequiredInput(name),
              satisfied: false,
            }))).map((row) => (
              <li
                key={row.name}
                className="flex items-center gap-1.5 rounded border border-dfui-border/60 px-2 py-1 text-[10px]"
              >
                <span
                  className={
                    row.satisfied
                      ? "text-emerald-400"
                      : "text-amber-300"
                  }
                >
                  {row.satisfied ? "✓" : "○"}
                </span>
                <span className={row.satisfied ? "text-dfui-secondary" : "text-dfui-fg"}>
                  {row.label}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {(plan.operations?.length ?? 0) > 0 && (
        <div>
          <p className="mb-1 font-mono text-[9px] uppercase tracking-wider text-dfui-tertiary">
            Operations
          </p>
          <div className="flex flex-wrap gap-1">
            {plan.operations!.map((op) => (
              <span
                key={op}
                className="rounded border border-dfui-border/80 bg-dfui-surface/60 px-1.5 py-0.5 font-mono text-[10px] text-dfui-secondary"
              >
                {op}
              </span>
            ))}
          </div>
        </div>
      )}

      {steps.length > 0 && (
        <div>
          <p className="mb-1 font-mono text-[9px] uppercase tracking-wider text-dfui-tertiary">
            Workflow steps
          </p>
          <ol className="space-y-1">
            {steps.map((step, index) => (
              <li
                key={step.id ?? `${step.operation}-${index}`}
                className="rounded border border-dfui-border/60 bg-dfui-surface/40 px-2 py-1"
              >
                <span className="font-mono text-[10px] text-dfui-fg">
                  {index + 1}. {step.operation ?? "step"}
                </span>
                {step.mode && (
                  <span className="ml-1 font-mono text-[9px] text-dfui-tertiary">
                    ({step.mode})
                  </span>
                )}
              </li>
            ))}
          </ol>
        </div>
      )}

      {templateIds.length > 0 && (
        <div>
          <p className="mb-1 font-mono text-[9px] uppercase tracking-wider text-dfui-tertiary">
            Templates
          </p>
          <ul className="space-y-1">
            {templateIds.map((id) => {
              const meta = templates[id];
              return (
                <li
                  key={id}
                  className="rounded border border-dfui-border/60 px-2 py-1 text-[10px] text-dfui-secondary"
                >
                  <span className="font-medium text-dfui-fg">{meta?.title ?? id}</span>
                  {meta?.builder && (
                    <span className="mt-0.5 block font-mono text-[9px] text-dfui-tertiary">
                      {meta.builder}
                    </span>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {readiness && !readiness.ready && (
        <div className="max-h-32 overflow-y-auto text-[10px] text-dfui-secondary">
          {(readiness.missing_node_packs?.length ?? 0) > 0 && (
            <p className="mb-1">
              Missing packs: {readiness.missing_node_packs!.join(", ")}
            </p>
          )}
          {(readiness.missing_models?.length ?? 0) > 0 && (
            <p className="mb-1">
              Missing models: {readiness.missing_models!.join(", ")}
            </p>
          )}
          {(readiness.recommended_actions?.length ?? 0) > 0 && (
            <ul className="list-disc pl-4">
              {readiness.recommended_actions!.slice(0, 4).map((action, i) => (
                <li key={i}>{String(action.hint ?? action.action ?? JSON.stringify(action))}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {(plan.actions?.length ?? 0) > 0 && (
        <ul className="max-h-20 list-disc overflow-y-auto pl-4 text-[10px] text-dfui-tertiary">
          {plan.actions!.map((action) => (
            <li key={action}>{action}</li>
          ))}
        </ul>
      )}

      <div className="mt-auto flex flex-wrap gap-2 border-t border-dfui-border/50 pt-2">
        {onApply && !applied && plan.proposed && (
          <button
            type="button"
            onClick={onApply}
            disabled={runBusy}
            className="inline-flex flex-1 items-center justify-center gap-1 rounded-lg border border-dfui-border px-2 py-1.5 text-[11px] text-dfui-fg hover:border-df-blue/40 disabled:opacity-50"
          >
            <Check size={12} />
            Apply plan
          </button>
        )}
        {onRun && (
          <button
            type="button"
            onClick={onRun}
            disabled={runDisabled}
            title={
              runBlockReason && !runCheck.ok
                ? runBlockReason
                : runCheck.reason ?? "Apply settings and start local generation"
            }
            className="inline-flex flex-1 items-center justify-center gap-1 rounded-lg bg-gradient-to-r from-df-orange to-df-orange-deep px-2 py-1.5 text-[11px] font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Play size={12} fill="currentColor" />
            {runBusy ? "Running…" : "Run plan"}
          </button>
        )}
        {onDownloadCompanions &&
          ((readiness?.missing_models?.length ?? 0) > 0 ||
            (readiness?.recommended_actions?.length ?? 0) > 0) && (
            <button
              type="button"
              onClick={onDownloadCompanions}
              disabled={companionDownloadBusy}
              className="w-full rounded-lg border border-df-blue/40 bg-df-blue/10 px-2 py-1.5 text-[11px] text-df-blue hover:bg-df-blue/20 disabled:opacity-50"
            >
              {companionDownloadBusy ? "Downloading…" : "Download missing assets"}
            </button>
          )}
      </div>
    </div>
  );
}
