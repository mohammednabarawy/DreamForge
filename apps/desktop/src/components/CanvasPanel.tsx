import { motion } from "framer-motion";
import {
  Move,
  RotateCcw,
  SplitSquareHorizontal,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { PointerEvent } from "react";
import { BRAND } from "../lib/brand";
import { studioPrepareFallbackLabel } from "../lib/loadingMessages";
import { summarizeGenerationLog } from "../lib/generationLogUi";
import type { ReferenceImageMode } from "../lib/referenceImage";
import type { GenerationSettings } from "../lib/tauri-api";
import { EngineBootOverlay } from "./EngineBootOverlay";
import { PromptBar } from "./PromptBar";
import { StudioProgressStrip } from "./StudioProgressStrip";
import type { EngineState } from "../lib/engine";
import type { LiveProgress } from "../lib/generationProgressUi";
import type { StudioMode } from "../lib/model-selection";
import type { AgentPlanSnapshot, AgentTranscriptMessage } from "../lib/studioBridge";
import type { UiExperience } from "../lib/experienceUi";
import { isSimpleExperience } from "../lib/experienceUi";
import { pathToAssetUrl } from "../lib/preview-display";
import { AgentTranscriptPanel } from "./AgentTranscriptPanel";
import { WorkflowPlanPanel } from "./WorkflowPlanPanel";
import { CanvasMaskEditor } from "./CanvasMaskEditor";

type Mention = { kind: "model" | "style"; label: string; value: string };
type CompareMode = "before" | "after" | "split";

type Props = {
  previewUrl: string | null;
  liveProgress: LiveProgress | null;
  workerReady: boolean;
  canGenerate: boolean;
  companionBlockedOnly?: boolean;
  generateBlockReason?: string;
  needsCompanionDownload?: boolean;
  missingCompanionCount?: number;
  companionDownloadBusy?: boolean;
  onDownloadCompanions?: () => void;
  engineState: EngineState;
  bootMessage: string;
  bootPhase?: string;
  workerLogTail: string;
  restarting: boolean;
  onRestartEngine: () => void;
  companionBootstrapBusy?: boolean;
  companionBootstrapMessage?: string;
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
  onEnhancePrompt?: () => void;
  enhancePromptBusy?: boolean;
  onGenerate: () => void;
  onGenerateVariants?: (count: number) => void;
  imageNumberMax?: number;
  onCancel: () => void;
  onAttachReferenceImage: (path: string, mode: ReferenceImageMode) => void;
  onAttachExtraReferenceImage?: (path: string) => void;
  onRemoveExtraReferenceImage?: (index: number) => void;
  onClearReferenceImage: () => void;
  onOpenInpaintMask?: () => void;
  onOpenInpaintMaskModal?: () => void;
  inpaintCanvasFocus?: boolean;
  onInpaintCanvasFocusChange?: (focused: boolean) => void;
  onInpaintMaskChange?: (path: string) => void;
  onOpenFullLog: () => void;
  activeModelLabel: string;
  referenceModelFamily?: string;
  experience?: UiExperience;
};

export function CanvasPanel({
  previewUrl,
  liveProgress,
  workerReady,
  canGenerate,
  companionBlockedOnly = false,
  generateBlockReason,
  needsCompanionDownload,
  missingCompanionCount,
  companionDownloadBusy,
  onDownloadCompanions,
  engineState,
  bootMessage,
  bootPhase,
  workerLogTail,
  restarting,
  onRestartEngine,
  companionBootstrapBusy,
  companionBootstrapMessage,
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
  onEnhancePrompt,
  enhancePromptBusy,
  onGenerate,
  onGenerateVariants,
  imageNumberMax,
  onCancel,
  onAttachReferenceImage,
  onAttachExtraReferenceImage,
  onRemoveExtraReferenceImage,
  onClearReferenceImage,
  onOpenInpaintMask,
  onOpenInpaintMaskModal,
  inpaintCanvasFocus = false,
  onInpaintCanvasFocusChange,
  onInpaintMaskChange,
  onOpenFullLog,
  activeModelLabel,
  referenceModelFamily,
  experience = "pro",
}: Props) {
  const simpleExperience = isSimpleExperience(experience);
  const [compareMode, setCompareMode] = useState<CompareMode>("after");
  const [compareSplit, setCompareSplit] = useState(50);
  const [canvasZoom, setCanvasZoom] = useState(1);
  const [canvasPan, setCanvasPan] = useState({ x: 0, y: 0 });
  const [isCanvasPanning, setIsCanvasPanning] = useState(false);
  const compareImageRef = useRef<HTMLDivElement | null>(null);
  const canvasViewportRef = useRef<HTMLDivElement | null>(null);
  const compareModeRef = useRef<CompareMode>(compareMode);
  compareModeRef.current = compareMode;
  const compareImageClass =
    "block max-h-[calc(100vh-12rem)] max-w-full select-none object-contain";
  const panStartRef = useRef({
    pointerId: -1,
    x: 0,
    y: 0,
    panX: 0,
    panY: 0,
  });
  const companionBootstrapLabel = studioPrepareFallbackLabel(studioMode);
  const inputImagePath = (settings.input_image ?? "").trim();
  const upscaleImagePath = (settings.upscale_image ?? "").trim();
  const compareSourcePath =
    studioMode === "upscale" ? upscaleImagePath : inputImagePath;
  const inpaintMaskPath = settings.inpaint_mask_path;
  const sourceAssetUrl = pathToAssetUrl(compareSourcePath);
  const canCompare =
    !generating &&
    Boolean(previewUrl) &&
    Boolean(compareSourcePath) &&
    (studioMode === "edit" || studioMode === "inpaint" || studioMode === "upscale");
  const showInlineMask =
    studioMode === "inpaint" &&
    Boolean(inputImagePath) &&
    !generating &&
    Boolean(inpaintCanvasFocus);
  const canvasPreviewUrl =
    canCompare && compareMode === "before" && sourceAssetUrl ? sourceAssetUrl : previewUrl;
  const showCompareSplit =
    canCompare && compareMode === "split" && Boolean(sourceAssetUrl) && Boolean(previewUrl);
  const showCompareCanvas = showCompareSplit || Boolean(canvasPreviewUrl);

  useEffect(() => {
    if (previewUrl && compareSourcePath) {
      setCompareMode("after");
    }
  }, [previewUrl, compareSourcePath]);

  useEffect(() => {
    setCanvasZoom(1);
    setCanvasPan({ x: 0, y: 0 });
    setIsCanvasPanning(false);
  }, [previewUrl, compareSourcePath]);

  const clampCanvasZoom = (value: number) => Math.max(0.25, Math.min(8, value));

  const clampCanvasPan = (
    pan: { x: number; y: number },
    zoom: number,
  ): { x: number; y: number } => {
    if (zoom <= 1) return { x: 0, y: 0 };
    const frame = canvasViewportRef.current;
    if (!frame) return pan;
    const maxX = Math.max(0, (frame.clientWidth * (zoom - 1)) / 2);
    const maxY = Math.max(0, (frame.clientHeight * (zoom - 1)) / 2);
    return {
      x: Math.max(-maxX, Math.min(maxX, pan.x)),
      y: Math.max(-maxY, Math.min(maxY, pan.y)),
    };
  };

  useEffect(() => {
    const el = canvasViewportRef.current;
    if (!el || !showCompareCanvas) return;
    const onWheel = (event: WheelEvent) => {
      event.preventDefault();
      const delta = event.deltaY < 0 ? 0.12 : -0.12;
      setCanvasZoom((current) => {
        const zoom = clampCanvasZoom(current * (1 + delta));
        if (zoom <= 1) setCanvasPan({ x: 0, y: 0 });
        return zoom;
      });
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [showCompareCanvas]);

  const setZoomKeepingPan = (nextZoom: number) => {
    const zoom = clampCanvasZoom(nextZoom);
    setCanvasZoom(zoom);
    if (zoom <= 1) {
      setCanvasPan({ x: 0, y: 0 });
    }
  };

  const resetCanvasView = () => {
    setCanvasZoom(1);
    setCanvasPan({ x: 0, y: 0 });
    setIsCanvasPanning(false);
  };

  const handleCanvasPanStart = (event: PointerEvent<HTMLDivElement>) => {
    if (canvasZoom <= 1) return;
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    panStartRef.current = {
      pointerId: event.pointerId,
      x: event.clientX,
      y: event.clientY,
      panX: canvasPan.x,
      panY: canvasPan.y,
    };
    setIsCanvasPanning(true);
  };

  const handleCanvasPanMove = (event: PointerEvent<HTMLDivElement>) => {
    if (!isCanvasPanning || panStartRef.current.pointerId !== event.pointerId) return;
    const start = panStartRef.current;
    setCanvasPan(() =>
      clampCanvasPan(
        {
          x: start.panX + event.clientX - start.x,
          y: start.panY + event.clientY - start.y,
        },
        canvasZoom,
      ),
    );
  };

  const handleCanvasPanEnd = (event: PointerEvent<HTMLDivElement>) => {
    if (panStartRef.current.pointerId === event.pointerId) {
      setIsCanvasPanning(false);
      panStartRef.current.pointerId = -1;
      setCanvasPan((pan) => clampCanvasPan(pan, canvasZoom));
    }
  };

  const updateCompareSplit = (clientX: number) => {
    const frame = compareImageRef.current;
    if (!frame) return;
    const rect = frame.getBoundingClientRect();
    if (rect.width <= 0) return;
    const next = ((clientX - rect.left) / rect.width) * 100;
    setCompareSplit(Math.max(0, Math.min(100, next)));
  };

  const handleComparePointer = (event: PointerEvent<HTMLDivElement>) => {
    if (compareMode !== "split") return;
    event.preventDefault();
    event.stopPropagation();
    event.currentTarget.setPointerCapture(event.pointerId);
    updateCompareSplit(event.clientX);
  };

  const handleCompareDrag = (event: PointerEvent<HTMLDivElement>) => {
    if (compareMode !== "split" || event.buttons !== 1) return;
    event.stopPropagation();
    updateCompareSplit(event.clientX);
  };

  const handleComparePointerEnd = (event: PointerEvent<HTMLDivElement>) => {
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  };

  const canvasTransformStyle = {
    transform: `translate(${canvasPan.x}px, ${canvasPan.y}px) scale(${canvasZoom})`,
    transformOrigin: "center center",
  } as const;

  const logSummary = summarizeGenerationLog(generationLog);

  return (
    <section className="flex h-full min-h-0 min-w-0 flex-col overflow-hidden">
      <div className="relative flex min-h-0 flex-1 flex-col items-center justify-center overflow-hidden p-4">
        <EngineBootOverlay
          engineState={engineState}
          bootMessage={bootMessage}
          workerLogTail={workerLogTail}
          onRestart={onRestartEngine}
          restarting={restarting}
          onOpenFullLog={onOpenFullLog}
          companionBootstrapBusy={companionBootstrapBusy}
        />
        {showInlineMask ? (
          <CanvasMaskEditor
            imagePath={inputImagePath}
            initialMaskPath={inpaintMaskPath}
            onMaskChange={onInpaintMaskChange}
            disabled={generating}
            onOpenExpanded={
              !simpleExperience && onOpenInpaintMaskModal
                ? onOpenInpaintMaskModal
                : undefined
            }
          />
        ) : showCompareCanvas ? (
          <motion.div
            initial={false}
            animate={{ opacity: 1 }}
            transition={{ duration: generating ? 0.12 : 0 }}
            className={`relative max-h-full max-w-full overflow-hidden rounded-xl border border-dfui-border/50 shadow-glass ${
              showCompareSplit
                ? "cursor-ew-resize"
                : canvasZoom > 1
                  ? isCanvasPanning
                    ? "cursor-grabbing"
                    : "cursor-grab"
                  : "cursor-zoom-in"
            }`}
            ref={canvasViewportRef}
            onPointerDown={
              showCompareSplit && canvasZoom <= 1 ? handleComparePointer : handleCanvasPanStart
            }
            onPointerMove={
              showCompareSplit && canvasZoom <= 1 ? handleCompareDrag : handleCanvasPanMove
            }
            onPointerUp={
              showCompareSplit && canvasZoom <= 1
                ? handleComparePointerEnd
                : handleCanvasPanEnd
            }
            onPointerCancel={
              showCompareSplit && canvasZoom <= 1
                ? handleComparePointerEnd
                : handleCanvasPanEnd
            }
            title="Mouse wheel to zoom. Drag to pan when zoomed."
          >
            {showCompareSplit ? (
              <div
                ref={compareImageRef}
                className="relative inline-block max-w-full"
                style={canvasTransformStyle}
              >
                <img
                  src={previewUrl ?? undefined}
                  alt="After"
                  decoding="async"
                  draggable={false}
                  className={compareImageClass}
                />
                <div
                  className="pointer-events-none absolute inset-0 overflow-hidden"
                  style={{ clipPath: `inset(0 ${100 - compareSplit}% 0 0)` }}
                >
                  <img
                    src={sourceAssetUrl ?? undefined}
                    alt="Before"
                    decoding="async"
                    draggable={false}
                    className="h-full w-full select-none object-contain"
                  />
                </div>
                <div
                  role="slider"
                  aria-label="Before after split position"
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={Math.round(compareSplit)}
                  tabIndex={0}
                  className="absolute top-0 z-10 h-full w-8 -translate-x-1/2 cursor-ew-resize outline-none focus-visible:ring-2 focus-visible:ring-dfui-accent"
                  style={{ left: `${compareSplit}%` }}
                  onPointerDown={handleComparePointer}
                  onPointerMove={handleCompareDrag}
                  onPointerUp={handleComparePointerEnd}
                  onPointerCancel={handleComparePointerEnd}
                  onKeyDown={(event) => {
                    if (event.key === "ArrowLeft") {
                      event.preventDefault();
                      setCompareSplit((value) => Math.max(0, value - 2));
                    } else if (event.key === "ArrowRight") {
                      event.preventDefault();
                      setCompareSplit((value) => Math.min(100, value + 2));
                    }
                  }}
                >
                  <div className="mx-auto h-full w-px bg-white/90 shadow-[0_0_0_1px_rgba(0,0,0,0.35)]" />
                  <div className="absolute left-1/2 top-1/2 flex h-9 w-9 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border border-white/70 bg-dfui-panel/90 text-[10px] font-semibold text-dfui-fg shadow-glass backdrop-blur-md">
                    <SplitSquareHorizontal size={16} />
                  </div>
                </div>
                <div className="pointer-events-none absolute left-3 top-3 rounded bg-dfui-panel/80 px-2 py-1 text-[10px] font-medium text-dfui-fg backdrop-blur">
                  Before
                </div>
                <div className="pointer-events-none absolute right-3 top-3 rounded bg-dfui-panel/80 px-2 py-1 text-[10px] font-medium text-dfui-fg backdrop-blur">
                  After
                </div>
              </div>
            ) : (
              <img
                src={canvasPreviewUrl ?? undefined}
                alt={generating ? "Live generation preview" : "Active generation"}
                decoding="async"
                draggable={false}
                className={compareImageClass}
                style={canvasTransformStyle}
              />
            )}
          </motion.div>
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
              {simpleExperience ? (
                <>
                  <span>Create · Edit · Fix region · Enhance</span>
                </>
              ) : (
                <>
                  <span>@model</span>
                  <span className="text-dfui-border/40">·</span>
                  <span>@style</span>
                  <span className="text-dfui-border/40">·</span>
                  <span>Dry run first</span>
                </>
              )}
            </div>
          </motion.div>
        )}
        {canCompare && (
          <div className="absolute right-4 top-4 z-10 flex rounded-lg border border-dfui-border/60 bg-dfui-panel/90 p-0.5 shadow-glass backdrop-blur-md">
            <button
              type="button"
              onClick={() => {
                onInpaintCanvasFocusChange?.(false);
                setCompareMode("before");
              }}
              className={`rounded-md px-2.5 py-1 text-[10px] font-medium transition ${
                compareMode === "before"
                  ? "bg-dfui-accent/20 text-dfui-accent"
                  : "text-dfui-muted hover:text-dfui-fg"
              }`}
            >
              Before
            </button>
            <button
              type="button"
              onClick={() => {
                onInpaintCanvasFocusChange?.(false);
                setCompareMode("after");
              }}
              className={`rounded-md px-2.5 py-1 text-[10px] font-medium transition ${
                compareMode === "after"
                  ? "bg-dfui-accent/20 text-dfui-accent"
                  : "text-dfui-muted hover:text-dfui-fg"
              }`}
            >
              After
            </button>
            <button
              type="button"
              onClick={() => {
                onInpaintCanvasFocusChange?.(false);
                setCompareMode("split");
              }}
              className={`inline-flex items-center gap-1 rounded-md px-2.5 py-1 text-[10px] font-medium transition ${
                compareMode === "split"
                  ? "bg-dfui-accent/20 text-dfui-accent"
                  : "text-dfui-muted hover:text-dfui-fg"
              }`}
            >
              <SplitSquareHorizontal size={12} />
              Split
            </button>
          </div>
        )}
        {showCompareCanvas && !generating && (
          <div className="absolute bottom-4 right-4 z-10 flex items-center gap-1 rounded-lg border border-dfui-border/60 bg-dfui-panel/90 p-1 text-[10px] font-medium text-dfui-fg shadow-glass backdrop-blur-md">
            <button
              type="button"
              onClick={resetCanvasView}
              className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-dfui-muted transition hover:bg-dfui-surface hover:text-dfui-fg"
              title="Fit image to canvas"
            >
              <RotateCcw size={12} />
              Fit
            </button>
            <button
              type="button"
              onClick={() => setZoomKeepingPan(1)}
              className="rounded-md px-2 py-1 text-dfui-muted transition hover:bg-dfui-surface hover:text-dfui-fg"
              title="Reset zoom to 100%"
            >
              100%
            </button>
            <button
              type="button"
              onClick={() => setZoomKeepingPan(canvasZoom / 1.25)}
              className="rounded-md p-1.5 text-dfui-muted transition hover:bg-dfui-surface hover:text-dfui-fg"
              title="Zoom out"
            >
              <ZoomOut size={13} />
            </button>
            <div className="min-w-10 text-center font-mono text-dfui-data">
              {Math.round(canvasZoom * 100)}%
            </div>
            <button
              type="button"
              onClick={() => setZoomKeepingPan(canvasZoom * 1.25)}
              className="rounded-md p-1.5 text-dfui-muted transition hover:bg-dfui-surface hover:text-dfui-fg"
              title="Zoom in"
            >
              <ZoomIn size={13} />
            </button>
            {canvasZoom > 1 && (
              <span
                className="hidden items-center gap-1 px-1.5 text-dfui-tertiary sm:inline-flex"
                title="Drag the image to pan while zoomed"
              >
                <Move size={12} />
                Drag
              </span>
            )}
          </div>
        )}
        {canCompare && studioMode === "inpaint" && compareMode !== "before" && inputImagePath && (
          <button
            type="button"
            onClick={() => {
              onInpaintCanvasFocusChange?.(true);
              setCompareMode("before");
            }}
            className="absolute bottom-4 left-1/2 z-10 inline-flex -translate-x-1/2 items-center gap-1.5 rounded-lg border border-dfui-border/60 bg-dfui-panel/90 px-3 py-1.5 text-[10px] font-medium text-dfui-fg shadow-glass backdrop-blur-md hover:border-dfui-accent/45"
          >
            <SplitSquareHorizontal size={13} className="text-dfui-accent" />
            Edit mask
          </button>
        )}
        {!simpleExperience && studioMode === "agent" && !generating && (
          <AgentTranscriptPanel
            messages={agentTranscript}
            runtimeLabel={agentRuntimeLabel}
            onClear={onClearAgentTranscript}
          />
        )}
        {!simpleExperience && agentPlan && !generating && (
          <WorkflowPlanPanel
            plan={agentPlan}
            studioMode={studioMode}
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
      </div>
      <StudioProgressStrip
        engineState={engineState}
        bootMessage={bootMessage}
        bootPhase={bootPhase}
        generating={generating}
        liveProgress={liveProgress}
        logSummary={logSummary}
        companionBootstrapBusy={companionBootstrapBusy}
        companionBootstrapLabel={companionBootstrapLabel}
        companionBootstrapMessage={companionBootstrapMessage}
        onOpenFullLog={onOpenFullLog}
      />
      <div className="shrink-0">
      <PromptBar
        settings={settings}
        studioMode={studioMode}
        agentPlannedMode={agentPlannedMode}
        onStudioModeChange={onStudioModeChange}
        onChange={onChange}
        mentions={mentions}
        generating={generating}
        onDryRun={onDryRun}
        onEnhancePrompt={onEnhancePrompt}
        enhancePromptBusy={enhancePromptBusy}
        onGenerate={onGenerate}
        onGenerateVariants={onGenerateVariants}
        imageNumberMax={imageNumberMax}
        onCancel={onCancel}
        onAttachReferenceImage={onAttachReferenceImage}
        onAttachExtraReferenceImage={onAttachExtraReferenceImage}
        onRemoveExtraReferenceImage={onRemoveExtraReferenceImage}
        onClearReferenceImage={onClearReferenceImage}
        onOpenInpaintMask={onOpenInpaintMask}
        workerReady={workerReady}
        canGenerate={canGenerate}
        companionBlockedOnly={companionBlockedOnly}
        generateBlockReason={generateBlockReason}
        needsCompanionDownload={needsCompanionDownload}
        missingCompanionCount={missingCompanionCount}
        companionDownloadBusy={companionDownloadBusy}
        onDownloadCompanions={onDownloadCompanions}
        activeModelLabel={activeModelLabel}
        referenceModelFamily={referenceModelFamily}
        experience={experience}
      />
      </div>
    </section>
  );
}
