import { ImagePlus, Maximize2, Paintbrush, SlidersHorizontal, Wand2, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { readImagePreviewQueued } from "../lib/preview-queue";
import {
  REFERENCE_IMAGE_MODES,
  activeReferenceMode,
  activeReferencePath,
  basename,
  defaultReferenceEditStrength,
  effectiveReferenceEditStrength,
  handleImagePathDragOver,
  readImagePathFromDrop,
  upscaleMethodLabel,
  type ReferenceImageMode,
} from "../lib/referenceImage";
import type { GenerationSettings } from "../lib/tauri-api";
import { pickImageFile } from "../lib/tauri-api";
import type { StudioMode } from "../lib/model-selection";

type Props = {
  settings: GenerationSettings;
  modelFamily?: string;
  studioMode?: StudioMode;
  simpleAttach?: boolean;
  onAttach: (path: string, mode: ReferenceImageMode) => void;
  onAttachExtra?: (path: string) => void;
  onRemoveExtra?: (index: number) => void;
  onClear: () => void;
  onOpenInpaintMask?: () => void;
  onEditStrengthChange?: (value: number) => void;
  disabled?: boolean;
  compact?: boolean;
};

export function ReferenceImageControl({
  settings,
  modelFamily,
  studioMode = "generate",
  simpleAttach = false,
  onAttach,
  onAttachExtra,
  onRemoveExtra,
  onClear,
  onOpenInpaintMask,
  onEditStrengthChange,
  disabled = false,
  compact = false,
}: Props) {
  const [dragOver, setDragOver] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [mode, setMode] = useState<ReferenceImageMode>(() =>
    activeReferenceMode(settings),
  );
  const fileInputRef = useRef<HTMLInputElement>(null);
  const extraInputRef = useRef<HTMLInputElement>(null);

  const attachedPath = activeReferencePath(settings);
  const attachedMode = activeReferenceMode(settings);
  const extraReferences = (settings.reference_images ?? []).filter(
    (path) => path.trim() && path.trim() !== attachedPath,
  );
  const showExtraRefs =
    !simpleAttach &&
    Boolean(attachedPath) &&
    attachedMode === "reference" &&
    Boolean(onAttachExtra);
  const showEditStrength =
    Boolean(attachedPath) &&
    attachedMode !== "upscale" &&
    Boolean(onEditStrengthChange);
  const editStrength = effectiveReferenceEditStrength(settings, modelFamily);
  const editStrengthDefault = defaultReferenceEditStrength(settings, modelFamily);

  useEffect(() => {
    if (attachedPath) {
      setMode(attachedMode);
    }
  }, [attachedPath, attachedMode]);

  useEffect(() => {
    if (!attachedPath) {
      setPreviewUrl(null);
      return;
    }
    let cancelled = false;
    void readImagePreviewQueued(attachedPath)
      .then((result) => {
        if (!cancelled) setPreviewUrl(result.data_url);
      })
      .catch(() => {
        if (!cancelled) setPreviewUrl(null);
      });
    return () => {
      cancelled = true;
    };
  }, [attachedPath]);

  const taskReferenceMode = (): ReferenceImageMode => {
    if (studioMode === "inpaint") return "inpaint";
    if (studioMode === "upscale") return "upscale";
    return "reference";
  };

  const attachPath = (path: string, nextMode = simpleAttach ? taskReferenceMode() : mode) => {
    onAttach(path, nextMode);
    setMode(nextMode);
    setDragOver(false);
  };

  const onDrop = (event: React.DragEvent) => {
    event.preventDefault();
    event.stopPropagation();
    setDragOver(false);
    if (disabled) return;
    const path = readImagePathFromDrop(event.dataTransfer);
    if (path) attachPath(path);
  };

  const dropModeLabel =
    REFERENCE_IMAGE_MODES.find((item) => item.id === mode)?.short ?? "Ref";

  const onChooseFile = async () => {
    try {
      const path = await pickImageFile();
      if (path) attachPath(path);
    } catch {
      fileInputRef.current?.click();
    }
  };

  const onChooseExtraFile = async () => {
    try {
      const path = await pickImageFile();
      if (path) onAttachExtra?.(path);
    } catch {
      extraInputRef.current?.click();
    }
  };

  const onFileInput = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    const tauriPath = (file as File & { path?: string }).path;
    if (tauriPath) {
      attachPath(tauriPath);
    }
  };

  const onExtraFileInput = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    const tauriPath = (file as File & { path?: string }).path;
    if (tauriPath) {
      onAttachExtra?.(tauriPath);
    }
  };

  const modeIcon = (id: ReferenceImageMode) => {
    if (id === "upscale") return Maximize2;
    if (id === "inpaint") return Paintbrush;
    return Wand2;
  };

  const simpleAttachLabel =
    studioMode === "inpaint"
      ? "Fix region source"
      : studioMode === "upscale"
        ? "Enhance source"
        : studioMode === "edit"
          ? "Edit source"
          : "Reference image";

  return (
    <motion.div
      onDragEnterCapture={(event) => {
        if (handleImagePathDragOver(event, disabled)) setDragOver(true);
      }}
      onDragOverCapture={(event) => {
        if (handleImagePathDragOver(event, disabled)) setDragOver(true);
      }}
      onDragEnter={(event) => {
        if (handleImagePathDragOver(event, disabled)) setDragOver(true);
      }}
      onDragOver={(event) => {
        if (handleImagePathDragOver(event, disabled)) setDragOver(true);
      }}
      onDragLeave={(event) => {
        event.stopPropagation();
        if (!(event.currentTarget as HTMLElement).contains(event.relatedTarget as Node)) {
          setDragOver(false);
        }
      }}
      onDrop={onDrop}
      className={`relative flex flex-col overflow-hidden rounded-lg border transition-colors ${
        dragOver
          ? "border-df-blue/70 bg-df-blue/10 ring-1 ring-df-blue/30"
          : attachedPath
            ? "border-dfui-accent/35 bg-dfui-bg/55"
            : "border-dfui-border/50 bg-dfui-bg/25"
      }`}
      title="Attach a reference, inpaint, or upscale source image"
    >
      <input
        ref={fileInputRef}
        type="file"
        accept="image/png,image/jpeg,image/webp,image/bmp,image/gif,image/tiff"
        className="hidden"
        onChange={onFileInput}
      />
      <input
        ref={extraInputRef}
        type="file"
        accept="image/png,image/jpeg,image/webp,image/bmp,image/gif,image/tiff"
        className="hidden"
        onChange={onExtraFileInput}
      />

      <div className={`${compact ? "px-2 py-1" : "border-b border-dfui-border/35 px-2.5 py-2"}`}>
        <div className={`${compact ? "mb-1" : "mb-2"} flex items-center justify-between gap-2`}>
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-wide text-dfui-muted">
              {compact ? (simpleAttach ? "Image" : "References") : simpleAttach ? simpleAttachLabel : "Input image"}
            </p>
            <p className={`${compact ? "hidden" : "block"} text-[9px] text-dfui-tertiary`}>
              {simpleAttach
                ? "Drop or pick the image for this task"
                : "Reference, inpaint source, or upscale target"}
            </p>
          </div>
          {attachedPath ? (
            <button
              type="button"
              disabled={disabled}
              onClick={() => void onChooseFile()}
              className="inline-flex items-center gap-1 rounded-md border border-dfui-border/60 bg-dfui-panel px-2 py-1 text-[10px] font-medium text-dfui-secondary hover:border-df-blue/40 hover:text-dfui-fg disabled:opacity-50"
              title="Replace input image"
            >
              <ImagePlus size={12} className="text-df-blue" />
              Replace
            </button>
          ) : null}
        </div>

        {!simpleAttach ? (
        <div className="grid grid-cols-3 gap-1 rounded-md border border-dfui-border/45 bg-dfui-bg/40 p-0.5">
          {REFERENCE_IMAGE_MODES.map((item) => {
            const Icon = modeIcon(item.id);
            const active = (attachedPath ? attachedMode : mode) === item.id;
            return (
              <button
                key={item.id}
                type="button"
                disabled={disabled}
                onClick={() => {
                  setMode(item.id);
                  if (attachedPath) attachPath(attachedPath, item.id);
                }}
                title={item.description}
                className={`flex min-h-7 items-center justify-center gap-1 rounded px-1.5 text-[9px] font-medium transition ${
                  active
                    ? "bg-dfui-accent/20 text-dfui-accent"
                    : "text-dfui-muted hover:bg-dfui-surface-hover hover:text-dfui-fg"
                }`}
              >
                <Icon size={11} />
                {item.short}
              </button>
            );
          })}
        </div>
        ) : null}
      </div>

      <div className={compact ? "px-2 pb-1" : "p-2.5"}>
        {attachedPath ? (
          <div className="flex gap-2">
            <div className={`${compact ? "h-11 w-11" : "h-16 w-16"} relative shrink-0 overflow-hidden rounded-md border border-dfui-border/60 bg-dfui-bg`}>
              {previewUrl ? (
                <img src={previewUrl} alt="" className="h-full w-full object-cover" />
              ) : (
                <span className="flex h-full w-full items-center justify-center text-[9px] text-dfui-muted">
                  IMG
                </span>
              )}
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex min-w-0 items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="truncate font-mono text-[10px] text-dfui-fg" title={attachedPath}>
                    {basename(attachedPath)}
                  </p>
                  <p className="mt-0.5 text-[9px] text-dfui-muted">
                    {REFERENCE_IMAGE_MODES.find((item) => item.id === attachedMode)?.label}
                    {attachedMode === "upscale"
                      ? ` - ${upscaleMethodLabel(settings.upscale_method)}`
                      : ""}
                  </p>
                </div>
                <button
                  type="button"
                  disabled={disabled}
                  onClick={onClear}
                  className="shrink-0 rounded p-1 text-dfui-muted hover:bg-dfui-surface-hover hover:text-red-300 disabled:opacity-50"
                  title="Remove attached image"
                >
                  <X size={14} />
                </button>
              </div>
              <div className={`${compact ? "mt-1" : "mt-2"} flex flex-wrap items-center gap-1`}>
                {attachedMode !== "upscale" && (
                  <span className="inline-flex rounded border border-dfui-border/50 bg-dfui-bg/60 px-1.5 py-0.5 text-[9px] text-dfui-secondary">
                    Strength {Math.round(editStrength * 100)}%
                  </span>
                )}
              {attachedMode === "inpaint" && !simpleAttach && (
                  <span
                    className={`rounded border px-1.5 py-0.5 text-[9px] ${
                      settings.inpaint_mask_path
                        ? "border-dfui-accent/40 bg-dfui-accent/10 text-dfui-accent"
                        : "border-amber-400/30 bg-amber-400/10 text-amber-200"
                    }`}
                  >
                    {settings.inpaint_mask_path ? "Mask ready" : "Mask needed"}
                  </span>
                )}
                {extraReferences.length > 0 && (
                  <span className="rounded border border-df-blue/30 bg-df-blue/10 px-1.5 py-0.5 text-[9px] text-df-blue">
                    +{extraReferences.length} control
                  </span>
                )}
              </div>
              {attachedMode === "inpaint" && onOpenInpaintMask && !simpleAttach && (
                <button
                  type="button"
                  disabled={disabled}
                  onClick={onOpenInpaintMask}
                  className={`${compact ? "mt-1 h-6 px-2" : "mt-2 px-2 py-1.5"} inline-flex w-full items-center justify-center gap-1.5 rounded-md border border-dfui-accent/50 bg-dfui-accent/10 text-[10px] font-semibold text-dfui-accent transition hover:border-dfui-accent/80 hover:bg-dfui-accent/15 disabled:opacity-50`}
                  title="Open full-screen mask editor (brush, tap selection, grow/shrink)"
                >
                  <Paintbrush size={12} />
                  Full-screen mask
                </button>
              )}
            </div>
          </div>
        ) : (
          <button
            type="button"
            disabled={disabled}
            onClick={() => void onChooseFile()}
            className={`flex ${compact ? "min-h-9 flex-row gap-2 py-1.5" : "min-h-20 flex-col py-3"} w-full items-center justify-center rounded-md border border-dashed px-3 text-center transition ${
              dragOver
                ? "border-df-blue/70 bg-df-blue/10 text-df-blue"
                : "border-dfui-border/60 bg-dfui-bg/35 text-dfui-muted hover:border-df-blue/40 hover:text-dfui-fg"
            } disabled:opacity-50`}
          >
            <ImagePlus size={compact ? 14 : 18} className={`${compact ? "" : "mb-1"} text-df-blue`} />
            <span className="text-[11px] font-medium">
              {dragOver ? `Drop as ${dropModeLabel}` : "Attach image"}
            </span>
            <span className={`${compact ? "hidden" : "mt-0.5"} text-[9px] text-dfui-tertiary`}>
              Drag from session history, or click to browse
            </span>
          </button>
        )}
      </div>

      {showEditStrength && !compact && (
        <label
          className="mx-2.5 mb-2 flex items-center gap-2 rounded-md border border-dfui-border/35 bg-dfui-bg/35 px-2 py-1.5"
          title={`Edit strength (denoise). Default ${Math.round(editStrengthDefault * 100)}% for this model.`}
        >
          <span className="inline-flex min-w-[58px] items-center gap-1 text-[9px] text-dfui-muted">
            <SlidersHorizontal size={10} />
            Strength
          </span>
          <input
            type="range"
            min={0.2}
            max={1}
            step={0.01}
            disabled={disabled}
            value={editStrength}
            onChange={(e) => onEditStrengthChange?.(Number(e.target.value))}
            className="h-1.5 min-w-0 flex-1 accent-dfui-accent"
          />
          <span className="w-8 text-right font-mono text-[9px] text-dfui-secondary">
            {Math.round(editStrength * 100)}%
          </span>
        </label>
      )}
      {showExtraRefs && (
        <div className={`${compact ? "px-2 pb-1.5 pt-1" : "pt-1.5"} flex flex-wrap items-center gap-1 border-t border-dfui-border/40`}>
          {extraReferences.map((path, index) => (
            <span
              key={`${path}-${index}`}
              className="inline-flex max-w-[140px] items-center gap-1 rounded border border-dfui-border/60 bg-dfui-bg/60 px-1.5 py-0.5 font-mono text-[9px] text-dfui-secondary"
              title={path}
            >
              <span className="truncate">{basename(path)}</span>
              {onRemoveExtra && (
                <button
                  type="button"
                  disabled={disabled}
                  onClick={() => onRemoveExtra(index)}
                  className="shrink-0 text-dfui-muted hover:text-red-300 disabled:opacity-50"
                  title="Remove control reference"
                >
                  <X size={10} />
                </button>
              )}
            </span>
          ))}
          <button
            type="button"
            disabled={disabled}
            onClick={() => void onChooseExtraFile()}
            className="rounded border border-dashed border-dfui-border/70 px-1.5 py-0.5 text-[9px] text-dfui-accent hover:border-dfui-accent/50 disabled:opacity-50"
            title="Add Kontext control reference (stitched with main image)"
          >
            + control ref
          </button>
        </div>
      )}
    </motion.div>
  );
}
