import { motion } from "framer-motion";
import { ExternalLink, Loader2, Maximize2, Paintbrush, Wand2 } from "lucide-react";
import { BRAND } from "../lib/brand";
import type { ReferenceImageMode } from "../lib/referenceImage";
import type { OutputItem } from "../lib/tauri-api";
import { EngineBootBanner } from "./EngineBootBanner";
import { EngineBootOverlay } from "./EngineBootOverlay";
import { PromptBar } from "./PromptBar";
import type { EngineState } from "../lib/engine";
import type { GenerationSettings } from "../lib/tauri-api";
import type { StudioMode } from "../lib/model-selection";
import type { EditFamilyPlanState } from "../lib/generationReadiness";
import { WorkflowPlanPanel } from "./WorkflowPlanPanel";
import type { AgentPlanSnapshot, AgentTranscriptMessage } from "../lib/studioBridge";
import { AgentTranscriptPanel } from "./AgentTranscriptPanel";

type Mention = { kind: "model" | "style"; label: string; value: string };

type Props = {
  previewUrl: string | null;
  liveProgress: { percentage: number; title: string } | null;
  workerReady: boolean;
  canGenerate: boolean;
  generateBlockReason?: string;
  needsCompanionDownload?: boolean;
  missingCompanionCount?: number;
  companionDownloadBusy?: boolean;
  onDownloadCompanions?: () => void;
  engineState: EngineState;
  bootMessage: string;
  workerLogTail: string;
  restarting: boolean;
  onRestartEngine: () => void;
  selected: OutputItem | null;
  studioMode: StudioMode;
  agentPlannedMode?: StudioMode | null;
  onStudioModeChange: (mode: StudioMode) => void;
  settings: GenerationSettings;
  onChange: (patch: Partial<GenerationSettings>) => void;
  mentions: Mention[];
  generating: boolean;
  generationLog: string;
  agentPlan: AgentPlanSnapshot | null;
  agentTranscript?: AgentTranscriptMessage[];
  agentRuntimeLabel?: string;
  planApprovalRequired?: boolean;
  planRunBusy?: boolean;
  onApplyAgentPlan?: () => void;
  onRunApprovedPlan?: () => void;
  onDismissAgentPlan?: () => void;
  onClearAgentTranscript?: () => void;
  onDryRun: () => void;
  onGenerate: () => void;
  onCancel: () => void;
  onUseSelectedImageFor: (mode: "edit" | "inpaint" | "upscale") => void;
  onAttachReferenceImage: (path: string, mode: ReferenceImageMode) => void;
  onAttachExtraReferenceImage?: (path: string) => void;
  onRemoveExtraReferenceImage?: (index: number) => void;
  onClearReferenceImage: () => void;
  onOpenInpaintMask?: () => void;
  onOpenFullLog: () => void;
  activeModelLabel: string;
  referenceModelFamily?: string;
  editPlanState?: EditFamilyPlanState;
};

export function CanvasPanel({
  previewUrl,
  liveProgress,
  workerReady,
  canGenerate,
  generateBlockReason,
  needsCompanionDownload,
  missingCompanionCount,
  companionDownloadBusy,
  onDownloadCompanions,
  engineState,
  bootMessage,
  workerLogTail,
  restarting,
  onRestartEngine,
  selected,
  studioMode,
  agentPlannedMode,
  onStudioModeChange,
  settings,
  onChange,
  mentions,
  generating,
  generationLog,
  agentPlan,
  agentTranscript = [],
  agentRuntimeLabel,
  planApprovalRequired,
  planRunBusy,
  onApplyAgentPlan,
  onRunApprovedPlan,
  onDismissAgentPlan,
  onClearAgentTranscript,
  onDryRun,
  onGenerate,
  onCancel,
  onUseSelectedImageFor,
  onAttachReferenceImage,
  onAttachExtraReferenceImage,
  onRemoveExtraReferenceImage,
  onClearReferenceImage,
  onOpenInpaintMask,
  onOpenFullLog,
  activeModelLabel,
  referenceModelFamily,
  editPlanState,
}: Props) {
  return (
    <section className="flex h-full min-w-0 flex-col">
      <div className="relative flex flex-1 flex-col items-center justify-center overflow-hidden p-4">
        <EngineBootBanner engineState={engineState} bootMessage={bootMessage} />
        <EngineBootOverlay
          engineState={engineState}
          bootMessage={bootMessage}
          workerLogTail={workerLogTail}
          onRestart={onRestartEngine}
          restarting={restarting}
          onOpenFullLog={onOpenFullLog}
        />
        {generating && (
          <div className="absolute inset-x-4 top-4 z-10 flex flex-col gap-1 rounded-lg border border-dfui-forge/40 bg-dfui-panel/90 px-3 py-2 text-xs backdrop-blur-md">
            <div className="flex items-center gap-2">
              <Loader2 size={14} className="animate-spin text-dfui-forge" />
              <span className="text-dfui-fg">
                {liveProgress?.title || "Rendering on GPU — live preview"}
              </span>
              {liveProgress != null && (
                <span className="ml-auto font-mono text-dfui-forge">
                  {liveProgress.percentage}%
                </span>
              )}
            </div>
            {liveProgress != null && (
              <div className="h-1 overflow-hidden rounded-full bg-dfui-bg">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-dfui-dream to-dfui-forge transition-all duration-300"
                  style={{ width: `${Math.min(100, liveProgress.percentage)}%` }}
                />
              </div>
            )}
          </div>
        )}
        {previewUrl ? (
          <motion.img
            initial={false}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: generating ? 0.12 : 0 }}
            src={previewUrl}
            alt={generating ? "Live generation preview" : "Active generation"}
            decoding="async"
            className="max-h-full max-w-full rounded-xl border border-dfui-border/50 object-contain shadow-glass"
          />
        ) : generating ? (
          <div className="flex max-h-full max-w-full flex-col items-center gap-3 px-6 text-center">
            <img
              src={BRAND.logoIcon}
              alt=""
              className="h-14 w-14 animate-pulse opacity-90 shadow-glow"
            />
            <p className="text-sm text-dfui-secondary">
              Warming up models… live preview will appear on the next step
            </p>
          </div>
        ) : (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="flex flex-col items-center gap-5 text-dfui-muted"
          >
            <img
              src={BRAND.logoWordmark}
              alt={BRAND.name}
              className="h-16 max-w-[min(320px,80vw)] object-contain opacity-90 shadow-glow"
            />
            <div className="text-center">
              <p className="mt-1.5 text-sm text-dfui-secondary">
                Describe your vision below and press <kbd className="rounded border border-dfui-border/60 bg-dfui-surface px-1.5 py-0.5 font-mono text-[10px] text-dfui-fg">⌘⏎</kbd> to generate
              </p>
            </div>
            <div className="flex gap-3 text-[11px] text-dfui-tertiary">
              <span>@model</span>
              <span className="text-dfui-border/40">·</span>
              <span>@style</span>
              <span className="text-dfui-border/40">·</span>
              <span>Dry run first</span>
            </div>
          </motion.div>
        )}
        {selected && !generating && (
          <div className="absolute left-4 top-4 max-w-xs rounded-lg border border-dfui-border/60 bg-dfui-panel/80 px-3 py-2 text-[11px] backdrop-blur-md">
            <div className="font-medium text-dfui-fg">{selected.title}</div>
            <div className="mt-0.5 font-mono text-dfui-data">{selected.model_family}</div>
            <div className="truncate text-dfui-secondary">{selected.model_stem}</div>
            <div className="mt-2 grid grid-cols-3 gap-1">
              <button
                type="button"
                onClick={() => onUseSelectedImageFor("edit")}
                className="inline-flex items-center justify-center gap-1 rounded border border-dfui-border/60 bg-dfui-bg/50 px-1.5 py-1 text-[10px] text-dfui-fg hover:border-dfui-accent/50"
                title="Use selected image as edit reference"
              >
                <Wand2 size={11} />
                Edit
              </button>
              <button
                type="button"
                onClick={() => onUseSelectedImageFor("inpaint")}
                className="inline-flex items-center justify-center gap-1 rounded border border-dfui-border/60 bg-dfui-bg/50 px-1.5 py-1 text-[10px] text-dfui-fg hover:border-dfui-accent/50"
                title="Use selected image for inpaint-style editing"
              >
                <Paintbrush size={11} />
                Inpaint
              </button>
              <button
                type="button"
                onClick={() => onUseSelectedImageFor("upscale")}
                className="inline-flex items-center justify-center gap-1 rounded border border-dfui-border/60 bg-dfui-bg/50 px-1.5 py-1 text-[10px] text-dfui-fg hover:border-dfui-accent/50"
                title="Use selected image for 2x upscale"
              >
                <Maximize2 size={11} />
                2x
              </button>
            </div>
          </div>
        )}
        {agentPlan && !generating && (
          <WorkflowPlanPanel
            plan={agentPlan}
            applied={Boolean(agentPlan.applied && Object.keys(agentPlan.applied).length)}
            approvalRequired={planApprovalRequired}
            runBusy={planRunBusy}
            canRunGeneration={workerReady && !generating}
            runBlockReason={generateBlockReason}
            onApply={onApplyAgentPlan}
            onRun={onRunApprovedPlan}
            onDismiss={onDismissAgentPlan}
            onDownloadCompanions={onDownloadCompanions}
            companionDownloadBusy={companionDownloadBusy}
          />
        )}
        {studioMode === "agent" && !generating && (
          <AgentTranscriptPanel
            messages={agentTranscript}
            runtimeLabel={agentRuntimeLabel}
            onClear={onClearAgentTranscript}
          />
        )}
      </div>
      {(generating || generationLog) && (
        <div className="max-h-28 shrink-0 overflow-y-auto border-t border-dfui-border/50 bg-dfui-bg/60 px-3 py-2">
          <div className="mb-1 flex items-center justify-between">
            <p className="font-mono text-[9px] uppercase tracking-wider text-dfui-tertiary">
              Generation log
            </p>
            <button
              type="button"
              onClick={onOpenFullLog}
              className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 font-mono text-[9px] text-dfui-tertiary transition hover:bg-dfui-surface hover:text-dfui-fg"
            >
              <ExternalLink size={10} />
              Full log
            </button>
          </div>
          <pre className="whitespace-pre-wrap font-mono text-[10px] leading-snug text-dfui-secondary">
            {generationLog || "Waiting for output…"}
          </pre>
        </div>
      )}
      <PromptBar
        settings={settings}
        studioMode={studioMode}
        agentPlannedMode={agentPlannedMode}
        onStudioModeChange={onStudioModeChange}
        onChange={onChange}
        mentions={mentions}
        generating={generating}
        onDryRun={onDryRun}
        onGenerate={onGenerate}
        onCancel={onCancel}
        onAttachReferenceImage={onAttachReferenceImage}
        onAttachExtraReferenceImage={onAttachExtraReferenceImage}
        onRemoveExtraReferenceImage={onRemoveExtraReferenceImage}
        onClearReferenceImage={onClearReferenceImage}
        onOpenInpaintMask={onOpenInpaintMask}
        workerReady={workerReady}
        canGenerate={canGenerate}
        generateBlockReason={generateBlockReason}
        needsCompanionDownload={needsCompanionDownload}
        missingCompanionCount={missingCompanionCount}
        companionDownloadBusy={companionDownloadBusy}
        onDownloadCompanions={onDownloadCompanions}
        activeModelLabel={activeModelLabel}
        referenceModelFamily={referenceModelFamily}
        editPlanState={editPlanState}
      />
    </section>
  );
}
