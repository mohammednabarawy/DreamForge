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
  studioMode?: string;
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

type TemplateMeta = {
  id?: string;
  title?: string;
  label?: string;
  builder?: string;
};

function text(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function textList(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => text(item)).filter(Boolean) : [];
}

function templateMap(value: unknown): Record<string, TemplateMeta> {
  if (Array.isArray(value)) {
    return Object.fromEntries(
      value
        .filter((item): item is TemplateMeta => typeof item === "object" && item !== null)
        .map((item) => [item.id ?? item.label ?? "", item])
        .filter(([id]) => id),
    );
  }
  if (typeof value === "object" && value) {
    return value as Record<string, TemplateMeta>;
  }
  return {};
}

export function WorkflowPlanPanel({
  plan,
  applied,
  approvalRequired = true,
  studioMode,
  runBusy,
  canRunGeneration = true,
  runBlockReason,
  onApply,
  onRun,
  onDismiss,
  onDownloadCompanions,
  companionDownloadBusy,
}: Props) {
  const planLabel = studioMode === "agent" ? "Agent plan" : "Workflow plan";
  const blueprint = plan.workflow_blueprint as
    | { template_ids?: string[]; templates?: unknown }
    | undefined;
  const templateIds = textList(blueprint?.template_ids);
  const templates = templateMap(blueprint?.templates);
  const readiness = plan.readiness;
  const steps = plan.workflow_plan ?? [];
  const modelLabel = plannedModelLabel(plan);
  const inputRows = requiredInputRows(readiness);
  const missingInputs = textList(readiness?.missing_inputs);
  const presetApplied = plan.dynamic_preset?.applied ?? {};
  const presetEntries = Object.entries(presetApplied).filter(
    ([, value]) => value !== undefined && value !== null && value !== "",
  );
  const presetSources = textList(plan.dynamic_preset?.source);
  const modeContract = plan.mode_contract;
  const inpaintContext = plan.inpaint_context;
  const finalEditRequest = plan.final_edit_request;
  const editTaskDefaults = plan.edit_task_defaults;
  const changedFields = textList(modeContract?.changed_fields);
  const preservedFields = textList(modeContract?.preserved_fields);
  const preservationHints = textList(modeContract?.preservation_hints);
  const runCheck = canRunApprovedPlan(plan, readiness);
  const runDisabled =
    runBusy ||
    !runCheck.ok ||
    !canRunGeneration ||
    Boolean(runBlockReason);
  const modelCapabilities = plan.model_capabilities;
  const requiredCapabilities = textList(modelCapabilities?.required);
  const missingCapabilities = textList(modelCapabilities?.missing);

  const proposedSteps = plan.proposed?.steps;
  const proposedCfg = plan.proposed?.cfg_scale;
  const proposedSampler = plan.proposed?.sampler;
  const proposedScheduler = plan.proposed?.scheduler;
  const useQwenLora = plan.proposed?.use_qwen_lightning_lora;
  const qwenLoraWeight = plan.proposed?.qwen_lightning_strength;

  return (
    <div className="absolute right-4 top-4 z-20 flex max-h-[min(55vh,calc(100%-5rem))] w-[min(22rem,90vw)] flex-col overflow-hidden rounded-lg border border-dfui-border bg-dfui-bg/90 shadow-lg backdrop-blur-sm">
      <div className="flex shrink-0 items-start justify-between gap-2 px-3 pt-3">
        <div className="min-w-0 flex-1">
          <p className="font-mono text-[9px] uppercase tracking-wider text-dfui-tertiary">
            {planLabel} {applied ? "(applied)" : "(preview)"}
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

      <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto px-3 py-2">
      {plan.escalation_reason && (
        <div className="rounded border border-amber-500/35 bg-amber-500/10 px-2 py-1.5 text-[9px] leading-relaxed text-amber-200">
          ⚠️ {plan.escalation_reason}
        </div>
      )}

      {modelLabel && (
        <div>
          <p className="mb-1 font-mono text-[9px] uppercase tracking-wider text-dfui-tertiary">
            Selected model
          </p>
          <p className="rounded border border-dfui-border/60 bg-dfui-surface/40 px-2 py-1 font-mono text-[10px] text-dfui-fg">
            {modelLabel}
          </p>
          {modelCapabilities && requiredCapabilities.length > 0 && (
            <p
              className={`mt-1 rounded border px-2 py-1 font-mono text-[9px] ${
                modelCapabilities.compatible
                  ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-200"
                  : "border-amber-500/30 bg-amber-500/10 text-amber-200"
              }`}
            >
              route needs {requiredCapabilities.join(", ")}
              {missingCapabilities.length > 0
                ? `; missing ${missingCapabilities.join(", ")}`
                : "; model supports route"}
            </p>
          )}
        </div>
      )}

      {(proposedSteps !== undefined || proposedCfg !== undefined || proposedSampler || proposedScheduler) && (
        <div>
          <p className="mb-1 font-mono text-[9px] uppercase tracking-wider text-dfui-tertiary">
            Resolved parameters
          </p>
          <div className="grid grid-cols-2 gap-1 rounded border border-dfui-border/60 bg-dfui-surface/40 px-2 py-1.5 font-mono text-[10px] text-dfui-secondary">
            {proposedSteps !== undefined && (
              <div>
                <span className="text-dfui-tertiary">steps: </span>
                <span className="text-dfui-fg">{proposedSteps}</span>
              </div>
            )}
            {proposedCfg !== undefined && (
              <div>
                <span className="text-dfui-tertiary">cfg: </span>
                <span className="text-dfui-fg">{proposedCfg}</span>
              </div>
            )}
            {proposedSampler && (
              <div>
                <span className="text-dfui-tertiary">sampler: </span>
                <span className="text-dfui-fg">{proposedSampler}</span>
              </div>
            )}
            {proposedScheduler && (
              <div>
                <span className="text-dfui-tertiary">scheduler: </span>
                <span className="text-dfui-fg">{proposedScheduler}</span>
              </div>
            )}
            {useQwenLora && (
              <div className="col-span-2 mt-1 border-t border-dfui-border/30 pt-1 text-[9px] text-emerald-400">
                ⚡ Qwen Lightning LoRA active ({qwenLoraWeight ?? 0.75} weight)
              </div>
            )}
          </div>
        </div>
      )}

      {modeContract && (
        <div>
          <p className="mb-1 font-mono text-[9px] uppercase tracking-wider text-dfui-tertiary">
            Mode contract
          </p>
          <div className="space-y-1 rounded border border-dfui-border/60 bg-dfui-surface/40 px-2 py-1.5 text-[10px] text-dfui-secondary">
            {modeContract.summary && (
              <p className="text-dfui-fg">{modeContract.summary}</p>
            )}
            <p className="font-mono">
              <span className="text-dfui-tertiary">model policy: </span>
              <span className="text-dfui-fg">
                {text(modeContract.model_policy, "unknown").replace(/_/g, " ")}
              </span>
            </p>
            {changedFields.length > 0 && (
              <p className="font-mono">
                <span className="text-dfui-tertiary">changes: </span>
                <span>{changedFields.slice(0, 8).join(", ")}</span>
              </p>
            )}
            {preservedFields.length > 0 && (
              <p className="font-mono">
                <span className="text-dfui-tertiary">preserves: </span>
                <span>{preservedFields.slice(0, 8).join(", ")}</span>
              </p>
            )}
            {preservationHints.length > 0 && (
              <p className="font-mono">
                <span className="text-dfui-tertiary">intents: </span>
                <span>{preservationHints.join(" · ")}</span>
              </p>
            )}
          </div>
        </div>
      )}

      {inpaintContext && inpaintContext.status !== "missing_input" && (
        <div>
          <p className="mb-1 font-mono text-[9px] uppercase tracking-wider text-dfui-tertiary">
            Inpaint context
          </p>
          <div className="space-y-1 rounded border border-dfui-border/60 bg-dfui-surface/40 px-2 py-1.5 text-[10px] text-dfui-secondary">
            {inpaintContext.status === "outpaint" ? (
              <>
                <p className="font-mono">
                  <span className="text-dfui-tertiary">extend: </span>
                  <span className="text-dfui-fg">
                    {inpaintContext.outpaint?.direction ?? "right"} ·{" "}
                    {inpaintContext.outpaint?.amount ?? 256}px
                  </span>
                </p>
                <p className="font-mono">
                  <span className="text-dfui-tertiary">edge feather: </span>
                  <span>{inpaintContext.outpaint?.feathering ?? 40}px</span>
                </p>
              </>
            ) : inpaintContext.mask_empty ? (
              <p className="text-amber-300">Mask is empty — paint a selection before generating.</p>
            ) : (
              <>
                {typeof inpaintContext.mask_coverage === "number" && (
                  <p className="font-mono">
                    <span className="text-dfui-tertiary">coverage: </span>
                    <span className="text-dfui-fg">
                      {(inpaintContext.mask_coverage * 100).toFixed(2)}%
                    </span>
                  </p>
                )}
                {Array.isArray(inpaintContext.mask_bbox) && (
                  <p className="font-mono">
                    <span className="text-dfui-tertiary">mask bbox: </span>
                    <span>{inpaintContext.mask_bbox.join(", ")}</span>
                  </p>
                )}
                {inpaintContext.crop?.enabled && Array.isArray(inpaintContext.crop.size) && (
                  <p className="font-mono">
                    <span className="text-dfui-tertiary">crop: </span>
                    <span>
                      {inpaintContext.crop.size[0]}×{inpaintContext.crop.size[1]}
                      {Array.isArray(inpaintContext.crop.box)
                        ? ` @ ${inpaintContext.crop.box.join(", ")}`
                        : ""}
                    </span>
                  </p>
                )}
              </>
            )}
          </div>
        </div>
      )}

      {(finalEditRequest || editTaskDefaults) && (
        <div>
          <p className="mb-1 font-mono text-[9px] uppercase tracking-wider text-dfui-tertiary">
            Model instruction
          </p>
          <div className="space-y-1 rounded border border-dfui-border/60 bg-dfui-surface/40 px-2 py-1.5 text-[10px] text-dfui-secondary">
            {(editTaskDefaults?.label || finalEditRequest?.task) && (
              <p className="font-mono">
                <span className="text-dfui-tertiary">task: </span>
                <span className="text-dfui-fg">
                  {editTaskDefaults?.label ?? finalEditRequest?.task}
                </span>
                {finalEditRequest?.scope ? (
                  <span className="text-dfui-tertiary"> · {finalEditRequest.scope}</span>
                ) : null}
              </p>
            )}
            {(editTaskDefaults?.hint || finalEditRequest?.task_hint) && (
              <p className="text-dfui-fg">{editTaskDefaults?.hint ?? finalEditRequest?.task_hint}</p>
            )}
            {finalEditRequest?.user_instruction && (
              <p className="font-mono">
                <span className="text-dfui-tertiary">user: </span>
                <span className="text-dfui-fg">{finalEditRequest.user_instruction}</span>
              </p>
            )}
            {finalEditRequest?.model_instruction && (
              <p className="font-mono">
                <span className="text-dfui-tertiary">model: </span>
                <span className="text-dfui-fg">{finalEditRequest.model_instruction}</span>
              </p>
            )}
          </div>
        </div>
      )}

      {presetEntries.length > 0 && (
        <div>
          <p className="mb-1 font-mono text-[9px] uppercase tracking-wider text-dfui-tertiary">
            Style preset
            {presetSources.length > 0 ? ` · ${presetSources.join(", ").replace(/_/g, " ")}` : ""}
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
                  <span className="font-medium text-dfui-fg">{meta?.title ?? meta?.label ?? id}</span>
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
              Missing packs: {textList(readiness.missing_node_packs).join(", ")}
            </p>
          )}
          {(readiness.missing_models?.length ?? 0) > 0 && (
            <p className="mb-1">
              Missing models: {textList(readiness.missing_models).join(", ")}
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
          {textList(plan.actions).map((action) => (
            <li key={action}>{action}</li>
          ))}
        </ul>
      )}
      </div>

      <div className="flex shrink-0 flex-wrap gap-2 border-t border-dfui-border/50 bg-dfui-bg/90 px-3 py-2">
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
              runBlockReason
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
            (readiness?.recommended_actions?.length ?? 0) > 0 ||
            (plan.downloads?.length ?? 0) > 0) && (
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
