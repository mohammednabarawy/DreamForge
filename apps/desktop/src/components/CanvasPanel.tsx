import { motion } from "framer-motion";
import {
  RotateCcw,
  SplitSquareHorizontal,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import type { PointerEvent } from "react";
import { BRAND } from "../lib/brand";
import { studioPrepareFallbackLabel } from "../lib/loadingMessages";
import { summarizeGenerationLog } from "../lib/generationLogUi";
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
import { InpaintContextOverlay } from "./InpaintContextOverlay";
import { OutpaintPreviewOverlay } from "./OutpaintPreviewOverlay";
import { ResultTray } from "./ResultTray";

type Mention = { kind: "model" | "style"; label: string; value: string };
type CompareMode = "before" | "after" | "split";

const CANVAS_ZOOM_STEP = 1.25;

type CanvasLayout = {
  frameW: number;
  frameH: number;
  imgW: number;
  imgH: number;
  naturalW: number;
  naturalH: number;
};

function canvasPanLimits(layout: CanvasLayout, zoom: number) {
  const { frameW, frameH, imgW, imgH } = layout;
  if (frameW <= 0 || frameH <= 0 || imgW <= 0 || imgH <= 0) {
    return { maxX: 0, maxY: 0, canPan: false };
  }
  const scaledW = imgW * zoom;
  const scaledH = imgH * zoom;
  const maxX = Math.max(0, (scaledW - frameW) / 2);
  const maxY = Math.max(0, (scaledH - frameH) / 2);
  return { maxX, maxY, canPan: maxX > 0 || maxY > 0 };
}

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
  onDescribeImage?: () => void;
  describeImageBusy?: boolean;
  describeImagePath?: string;
  onImportImageMetadata?: (path: string) => void;
  onGenerate: () => void;
  onGenerateVariants?: (count: number) => void;
  imageNumberMax?: number;
  onCancel: () => void;
  onAttachReferenceImage: (path: string) => void;
  onAttachExtraReferenceImage?: (path: string) => void;
  onRemoveExtraReferenceImage?: (index: number) => void;
  onClearReferenceImage: () => void;
  onOpenInpaintMask?: () => void;
  onOpenInpaintMaskModal?: () => void;
  inpaintCanvasFocus?: boolean;
  onInpaintCanvasFocusChange?: (focused: boolean) => void;
  onInpaintMaskChange?: (path: string) => void;
  onInpaintMaskSyncingChange?: (syncing: boolean) => void;
  onOpenFullLog: () => void;
  activeModelLabel: string;
  referenceModelFamily?: string;
  experience?: UiExperience;
  onVaryImage?: (amount: "subtle" | "strong") => void;
  onAutoEnhance?: (target: "face" | "hands" | "eyes") => void;
  resultCandidates?: string[];
  activeCandidatePath?: string | null;
  onSelectResultCandidate?: (path: string) => void;
  onRetryGeneration?: () => void;
  onUseCandidateAsSource?: (path: string) => void;
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
  onDescribeImage,
  describeImageBusy,
  describeImagePath,
  onImportImageMetadata,
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
  onInpaintMaskSyncingChange,
  onOpenFullLog,
  activeModelLabel,
  referenceModelFamily,
  experience = "pro",
  onVaryImage,
  onAutoEnhance,
  resultCandidates = [],
  activeCandidatePath,
  onSelectResultCandidate,
  onRetryGeneration,
  onUseCandidateAsSource,
}: Props) {
  const simpleExperience = isSimpleExperience(experience);
  const [compareMode, setCompareMode] = useState<CompareMode>("after");
  const [compareSplit, setCompareSplit] = useState(50);
  const [canvasZoom, setCanvasZoom] = useState(1);
  const [canvasPan, setCanvasPan] = useState({ x: 0, y: 0 });
  const [isCanvasPanning, setIsCanvasPanning] = useState(false);
  const compareImageRef = useRef<HTMLDivElement | null>(null);
  const canvasShellRef = useRef<HTMLDivElement | null>(null);
  const canvasViewportRef = useRef<HTMLDivElement | null>(null);
  const canvasImageRef = useRef<HTMLImageElement | null>(null);
  const [canvasLayout, setCanvasLayout] = useState<CanvasLayout>({
    frameW: 0,
    frameH: 0,
    imgW: 0,
    imgH: 0,
    naturalW: 0,
    naturalH: 0,
  });
  const compareModeRef = useRef<CompareMode>(compareMode);
  compareModeRef.current = compareMode;
  const compareImageClass =
    "block max-h-full max-w-full select-none object-contain";
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
  const inpaintContext = agentPlan?.inpaint_context;
  const showInlineMask =
    studioMode === "inpaint" &&
    Boolean(inputImagePath) &&
    !generating &&
    Boolean(inpaintCanvasFocus);
  const showContextOverlay =
    studioMode === "inpaint" &&
    Boolean(inpaintContext?.crop?.enabled || inpaintContext?.mask_bbox) &&
    !generating &&
    (showInlineMask || compareMode === "before" || !previewUrl);
  const canvasPreviewUrl =
    canCompare && compareMode === "before" && sourceAssetUrl ? sourceAssetUrl : previewUrl;
  const showCompareSplit =
    canCompare && compareMode === "split" && Boolean(sourceAssetUrl) && Boolean(previewUrl);
  const showCompareCanvas = showCompareSplit || Boolean(canvasPreviewUrl);
  const showOutpaintPreview =
    !generating &&
    Boolean(compareSourcePath) &&
    (settings.edit_task === "extend" || settings.edit_type === "outpaint");
  const outpaintDirection = settings.outpaint_direction || "right";
  const outpaintDisplayAmount =
    outpaintDirection === "left" || outpaintDirection === "right"
      ? ((settings.outpaint_amount ?? 256) * canvasLayout.imgW) /
        Math.max(1, canvasLayout.naturalW)
      : ((settings.outpaint_amount ?? 256) * canvasLayout.imgH) /
        Math.max(1, canvasLayout.naturalH);

  useEffect(() => {
    if (previewUrl && compareSourcePath) {
      setCompareMode("after");
    }
  }, [previewUrl, compareSourcePath]);

  useEffect(() => {
    setCanvasZoom(1);
    setCanvasPan({ x: 0, y: 0 });
    setIsCanvasPanning(false);
    setCanvasLayout({ frameW: 0, frameH: 0, imgW: 0, imgH: 0, naturalW: 0, naturalH: 0 });
  }, [previewUrl, compareSourcePath]);

  const measureCanvasLayout = useCallback(() => {
    const frame = canvasViewportRef.current;
    const img = canvasImageRef.current;
    if (!frame || !img) return;
    setCanvasLayout({
      frameW: frame.clientWidth,
      frameH: frame.clientHeight,
      imgW: img.clientWidth,
      imgH: img.clientHeight,
      naturalW: img.naturalWidth,
      naturalH: img.naturalHeight,
    });
  }, []);

  useEffect(() => {
    const frame = canvasViewportRef.current;
    if (!frame || !showCompareCanvas || showInlineMask) return;
    const ro = new ResizeObserver(() => measureCanvasLayout());
    ro.observe(frame);
    const img = canvasImageRef.current;
    if (img) ro.observe(img);
    measureCanvasLayout();
    return () => ro.disconnect();
  }, [
    showCompareCanvas,
    showInlineMask,
    previewUrl,
    canvasPreviewUrl,
    compareMode,
    measureCanvasLayout,
  ]);

  const clampCanvasZoom = (value: number) => Math.max(0.25, Math.min(8, value));

  const clampCanvasPan = (
    pan: { x: number; y: number },
    zoom: number,
  ): { x: number; y: number } => {
    const { maxX, maxY, canPan } = canvasPanLimits(canvasLayout, zoom);
    if (!canPan) return { x: 0, y: 0 };
    return {
      x: Math.max(-maxX, Math.min(maxX, pan.x)),
      y: Math.max(-maxY, Math.min(maxY, pan.y)),
    };
  };

  const canvasCanPan = canvasPanLimits(canvasLayout, canvasZoom).canPan;

  useEffect(() => {
    const el = canvasShellRef.current;
    if (!el || !showCompareCanvas || showInlineMask) return;

    const onWheel = (event: WheelEvent) => {
      event.preventDefault();
      event.stopPropagation();

      const factor =
        event.deltaMode === WheelEvent.DOM_DELTA_PIXEL
          ? Math.exp(-event.deltaY * 0.002)
          : event.deltaY < 0
            ? CANVAS_ZOOM_STEP
            : 1 / CANVAS_ZOOM_STEP;

      setCanvasZoom((current) => {
        const zoom = clampCanvasZoom(current * factor);
        if (zoom <= 1) {
          setCanvasPan({ x: 0, y: 0 });
        } else {
          setCanvasPan((pan) => clampCanvasPan(pan, zoom));
        }
        return zoom;
      });
    };

    el.addEventListener("wheel", onWheel, { passive: false, capture: true });
    return () => el.removeEventListener("wheel", onWheel, { capture: true });
  }, [showCompareCanvas, showInlineMask]);

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
    if (!canvasCanPan) return;
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
      <div
        ref={canvasShellRef}
        className="relative flex min-h-0 flex-1 flex-col items-center justify-center overflow-hidden p-4"
      >
        <EngineBootOverlay
          engineState={engineState}
          bootMessage={bootMessage}
          companionBootstrapBusy={companionBootstrapBusy}
        />
        {showInlineMask ? (
          <CanvasMaskEditor
            imagePath={inputImagePath}
            initialMaskPath={inpaintMaskPath}
            inpaintContext={showContextOverlay ? inpaintContext : undefined}
            onMaskChange={onInpaintMaskChange}
            onMaskSyncingChange={onInpaintMaskSyncingChange}
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
            className={`relative flex h-full w-full min-h-0 min-w-0 max-h-full max-w-full items-center justify-center overflow-hidden rounded-xl border border-dfui-border/50 shadow-glass ${
              showCompareSplit
                ? "cursor-ew-resize"
                : canvasCanPan
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
            role="region"
            aria-label="Image canvas preview. Use plus and minus to zoom, zero to reset, and arrow keys to pan when zoomed."
            tabIndex={0}
            onKeyDown={(event) => {
              if (event.key === "+" || event.key === "=") {
                event.preventDefault();
                setZoomKeepingPan(canvasZoom * CANVAS_ZOOM_STEP);
              } else if (event.key === "-" || event.key === "_") {
                event.preventDefault();
                setZoomKeepingPan(canvasZoom / CANVAS_ZOOM_STEP);
              } else if (event.key === "0") {
                event.preventDefault();
                resetCanvasView();
              } else if (canvasZoom > 1 && event.key.startsWith("Arrow")) {
                event.preventDefault();
                const step = event.shiftKey ? 40 : 16;
                setCanvasPan((pan) =>
                  clampCanvasPan(
                    {
                      x:
                        pan.x +
                        (event.key === "ArrowLeft"
                          ? step
                          : event.key === "ArrowRight"
                            ? -step
                            : 0),
                      y:
                        pan.y +
                        (event.key === "ArrowUp"
                          ? step
                          : event.key === "ArrowDown"
                            ? -step
                            : 0),
                    },
                    canvasZoom,
                  ),
                );
              }
            }}
            title="Mouse wheel to zoom. Drag to pan when the image overflows the canvas."
          >
            {showCompareSplit ? (
              <div
                className="inline-flex items-center justify-center"
                style={canvasTransformStyle}
              >
                <div ref={compareImageRef} className="relative inline-block max-w-full">
                  <img
                    ref={canvasImageRef}
                    key={previewUrl ?? "after"}
                    src={previewUrl ?? undefined}
                    alt="After"
                    decoding="async"
                    draggable={false}
                    className={compareImageClass}
                    onLoad={measureCanvasLayout}
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
                      className={`${compareImageClass} h-full w-full`}
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
              </div>
            ) : (
              <div
                className="relative inline-flex items-center justify-center"
                style={canvasTransformStyle}
              >
                <img
                  ref={canvasImageRef}
                  key={canvasPreviewUrl ?? "preview"}
                  src={canvasPreviewUrl ?? undefined}
                  alt={generating ? "Live generation preview" : "Active generation"}
                  decoding="async"
                  draggable={false}
                  className={compareImageClass}
                  onLoad={measureCanvasLayout}
                />
                {showContextOverlay ? (
                  <InpaintContextOverlay context={inpaintContext} />
                ) : null}
                {showOutpaintPreview ? (
                  <OutpaintPreviewOverlay
                    direction={outpaintDirection}
                    amountDisplayPx={outpaintDisplayAmount}
                  />
                ) : null}
              </div>
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
        {previewUrl && !generating && onAutoEnhance && (
          <div className="absolute bottom-16 left-4 z-10 flex items-center gap-1 rounded-lg border border-dfui-border/60 bg-dfui-panel/90 p-1 text-[10px] font-medium text-dfui-fg shadow-glass backdrop-blur-md">
            <span className="px-1.5 text-dfui-muted">Fix</span>
            <button
              type="button"
              onClick={() => onAutoEnhance("face")}
              className="rounded-md px-2 py-1 text-dfui-muted transition hover:bg-dfui-surface hover:text-dfui-fg"
              title="Detect and repair faces"
            >
              Face
            </button>
            <button
              type="button"
              onClick={() => onAutoEnhance("hands")}
              className="rounded-md px-2 py-1 text-dfui-muted transition hover:bg-dfui-surface hover:text-dfui-fg"
              title="Detect and repair hands"
            >
              Hands
            </button>
            <button
              type="button"
              onClick={() => onAutoEnhance("eyes")}
              className="rounded-md px-2 py-1 text-dfui-muted transition hover:bg-dfui-surface hover:text-dfui-fg"
              title="Mask and refine eyes"
            >
              Eyes
            </button>
          </div>
        )}
        {resultCandidates.length > 1 && !generating && onSelectResultCandidate ? (
          <ResultTray
            images={resultCandidates}
            activePath={activeCandidatePath ?? undefined}
            sourcePath={compareSourcePath || undefined}
            onSelect={onSelectResultCandidate}
            onRetry={onRetryGeneration}
            onUseAsSource={onUseCandidateAsSource}
            retryBusy={generating}
          />
        ) : null}
        {previewUrl && !generating && onVaryImage && (
          <div className="absolute bottom-4 left-4 z-10 flex items-center gap-1 rounded-lg border border-dfui-border/60 bg-dfui-panel/90 p-1 text-[10px] font-medium text-dfui-fg shadow-glass backdrop-blur-md">
            <span className="px-1.5 text-dfui-muted">Vary</span>
            <button
              type="button"
              onClick={() => onVaryImage("subtle")}
              className="rounded-md px-2 py-1 text-dfui-muted transition hover:bg-dfui-surface hover:text-dfui-fg"
              title="Light img2img variation on this result"
            >
              Subtle
            </button>
            <button
              type="button"
              onClick={() => onVaryImage("strong")}
              className="rounded-md px-2 py-1 text-dfui-muted transition hover:bg-dfui-surface hover:text-dfui-fg"
              title="Stronger img2img variation on this result"
            >
              Strong
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
              onClick={() => setZoomKeepingPan(canvasZoom / CANVAS_ZOOM_STEP)}
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
              onClick={() => setZoomKeepingPan(canvasZoom * CANVAS_ZOOM_STEP)}
              className="rounded-md p-1.5 text-dfui-muted transition hover:bg-dfui-surface hover:text-dfui-fg"
              title="Zoom in"
            >
              <ZoomIn size={13} />
            </button>
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
        onDescribeImage={onDescribeImage}
        describeImageBusy={describeImageBusy}
        describeImagePath={describeImagePath}
        onImportImageMetadata={onImportImageMetadata}
        onGenerate={onGenerate}
        onGenerateVariants={onGenerateVariants}
        imageNumberMax={imageNumberMax}
        onCancel={onCancel}
        onAttachReferenceImage={onAttachReferenceImage}
        onAttachExtraReferenceImage={onAttachExtraReferenceImage}
        onRemoveExtraReferenceImage={onRemoveExtraReferenceImage}
        onClearReferenceImage={onClearReferenceImage}
        onOpenInpaintMask={onOpenInpaintMask}
        onInpaintCanvasFocusChange={onInpaintCanvasFocusChange}
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
