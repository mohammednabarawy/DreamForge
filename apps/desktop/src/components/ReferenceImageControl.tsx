import { ImagePlus, Paintbrush, SlidersHorizontal, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { readImagePreviewQueued } from "../lib/preview-queue";
import { routeBadgeLabel } from "../lib/routeResolution";
import {
  inferReferenceRole,
  proReferenceRolesForStudio,
  type ReferenceRole,
} from "../lib/referenceRole";
import {
  buildReferenceRolePatch,
  activeReferencePath,
  basename,
  defaultReferenceEditStrength,
  effectiveReferenceEditStrength,
  handleImagePathDragOver,
  readImagePathFromDrop,
  referenceAttachedLabel,
  referenceModeForStudio,
  referencePanelSubtitle,
  referencePanelTitle,
} from "../lib/referenceImage";
import type { GenerationSettings } from "../lib/tauri-api";
import { pickImageFile } from "../lib/tauri-api";
import type { StudioMode } from "../lib/model-selection";
import { ReferenceSlotsEditor } from "./ReferenceSlotsEditor";
import {
  appendReferenceSlot,
  coerceReferenceSlots,
  DEFAULT_SLOT_STOP_AT,
  removeReferenceSlotAt,
  syncLegacyFromPrimarySlot,
  updateReferenceSlotAt,
} from "../lib/referenceSlots";
import { maxReferenceImagesForFamily } from "../lib/multiImageCompose";
import {
  isIdentityPreservationActive,
  patchForKeepFace,
} from "../lib/identityPreserve";

type Props = {
  settings: GenerationSettings;
  modelFamily?: string;
  studioMode?: StudioMode;
  /** Simple UI: fewer role chips and slot controls; routing still follows studio tab + model. */
  simpleExperience?: boolean;
  onAttach: (path: string) => void;
  onAttachExtra?: (path: string) => void;
  onRemoveExtra?: (index: number) => void;
  onClear: () => void;
  onOpenInpaintMask?: () => void;
  onEditStrengthChange?: (value: number) => void;
  onPatchSettings?: (patch: Partial<GenerationSettings>) => void;
  disabled?: boolean;
  compact?: boolean;
};

export function ReferenceImageControl({
  settings,
  modelFamily,
  studioMode = "generate",
  simpleExperience = false,
  onAttach,
  onAttachExtra,
  onRemoveExtra,
  onClear,
  onOpenInpaintMask,
  onEditStrengthChange,
  onPatchSettings,
  disabled = false,
  compact = false,
}: Props) {
  const [dragOver, setDragOver] = useState(false);
  const [showRoles, setShowRoles] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const prompt = (settings.prompt ?? "").toLowerCase();
  const isImage1Mentioned = prompt.includes("image 1");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const extraInputRef = useRef<HTMLInputElement>(null);

  const attachedPath = activeReferencePath(settings, studioMode);
  const attachMode = referenceModeForStudio(studioMode);
  const extraReferences = (settings.reference_images ?? []).filter(
    (path) => path.trim() && path.trim() !== attachedPath,
  );
  const showEditStrength =
    Boolean(attachedPath) &&
    attachMode !== "upscale" &&
    Boolean(onEditStrengthChange);
  const editStrength = effectiveReferenceEditStrength(settings, modelFamily);
  const editStrengthDefault = defaultReferenceEditStrength(settings, modelFamily);
  const routeBadge = routeBadgeLabel(settings, studioMode, modelFamily);
  const activeReferenceRole = inferReferenceRole(settings, studioMode);
  const proReferenceRoles = proReferenceRolesForStudio(studioMode);
  const canShowProReferenceRoles =
    !simpleExperience &&
    Boolean(attachedPath) &&
    Boolean(onPatchSettings) &&
    proReferenceRoles.length > 1;
  const showProReferenceRoles = canShowProReferenceRoles && showRoles;

  const supportsMultiReferences =
    studioMode === "generate" || studioMode === "edit" || studioMode === "agent";
  const showMultiSlots =
    !simpleExperience &&
    supportsMultiReferences &&
    Boolean(onPatchSettings) &&
    Boolean(attachedPath);
  const maxSlots = maxReferenceImagesForFamily(modelFamily ?? "");

  const referenceSlots = coerceReferenceSlots(settings, studioMode, maxSlots);
  const atReferenceCap =
    (attachedPath ? 1 : 0) + extraReferences.length >= maxSlots;

  const showExtraRefs =
    simpleExperience &&
    supportsMultiReferences &&
    Boolean(attachedPath) &&
    Boolean(onAttachExtra) &&
    !showMultiSlots;

  // With 2+ images the app auto-composes (Qwen/Kontext multi-image), so the
  // manual keep-face toggle is only useful for a single source image.
  const showKeepFace =
    !simpleExperience &&
    studioMode === "generate" &&
    Boolean(attachedPath) &&
    Boolean(onPatchSettings) &&
    referenceSlots.length <= 1;
  const keepFaceActive = isIdentityPreservationActive(settings);

  const applyReferenceRole = (role: ReferenceRole) => {
    if (!attachedPath || !onPatchSettings) return;
    const patch = buildReferenceRolePatch(
      role,
      attachedPath,
      () => settings.output ?? "",
      {
        studioMode,
        modelFamily,
        currentModel: settings.model,
      },
    );
    const merged = { ...settings, ...patch };
    const slots = [...coerceReferenceSlots(merged, studioMode)];
    if (slots.length) {
      slots[0] = { ...slots[0], role };
      onPatchSettings(syncLegacyFromPrimarySlot(merged, slots));
    } else {
      onPatchSettings(patch);
    }
  };

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

  const attachPath = (path: string) => {
    onAttach(path);
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

  const dropActionLabel =
    studioMode === "inpaint"
      ? "inpaint source"
      : studioMode === "upscale"
        ? "enhance source"
        : studioMode === "edit"
          ? "edit source"
          : "reference";

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
      title="Attach reference images — routing follows the active studio tab and model"
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
              {referencePanelTitle(studioMode, compact)}
            </p>
            <p className={`${compact ? "hidden" : "block"} text-[9px] text-dfui-tertiary`}>
              {referencePanelSubtitle(studioMode)}
            </p>
            {routeBadge ? (
              <p className="mt-0.5 text-[9px] font-medium text-df-blue/90">{routeBadge}</p>
            ) : null}
          </div>
          {attachedPath ? (
            <div className="flex items-center gap-1">
              {canShowProReferenceRoles ? (
                <button
                  type="button"
                  disabled={disabled}
                  onClick={() => setShowRoles((value) => !value)}
                  className={`inline-flex items-center gap-1 rounded-md border px-2 py-1 text-[10px] font-medium transition ${
                    showRoles
                      ? "border-df-blue/50 bg-df-blue/10 text-df-blue"
                      : "border-dfui-border/60 bg-dfui-panel text-dfui-secondary hover:border-df-blue/40 hover:text-dfui-fg"
                  } disabled:opacity-50`}
                  title="Advanced: set a role per image (image prompt / restyle / structure) and weights"
                >
                  <SlidersHorizontal size={12} />
                  Roles
                </button>
              ) : null}
              <button
                type="button"
                disabled={disabled}
                onClick={() => void onChooseFile()}
                className="inline-flex items-center gap-1 rounded-md border border-dfui-border/60 bg-dfui-panel px-2 py-1 text-[10px] font-medium text-dfui-secondary hover:border-df-blue/40 hover:text-dfui-fg disabled:opacity-50"
                title="Replace attached image"
              >
                <ImagePlus size={12} className="text-df-blue" />
                Replace
              </button>
            </div>
          ) : null}
        </div>

        {showProReferenceRoles ? (
          <div
            className={`grid gap-1 rounded-md border border-dfui-border/45 bg-dfui-bg/40 p-0.5 ${
              proReferenceRoles.length >= 3
                ? "grid-cols-3"
                : proReferenceRoles.length > 1
                  ? "grid-cols-2"
                  : "grid-cols-1"
            }`}
          >
            {proReferenceRoles.map((item) => {
              const active = activeReferenceRole === item.id;
              return (
                <button
                  key={item.id}
                  type="button"
                  disabled={disabled}
                  onClick={() => applyReferenceRole(item.id)}
                  title={item.label}
                  className={`min-h-7 rounded px-1.5 text-[9px] font-medium transition ${
                    active
                      ? "bg-df-blue/20 text-df-blue"
                      : "text-dfui-muted hover:bg-dfui-surface-hover hover:text-dfui-fg"
                  }`}
                >
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
            <div className={`${compact ? "h-11 w-11" : "h-16 w-16"} relative shrink-0 overflow-hidden rounded-md border bg-dfui-bg transition-all ${
              isImage1Mentioned
                ? "border-df-blue ring-2 ring-df-blue"
                : "border-dfui-border/60"
            }`}>
              {previewUrl ? (
                <img src={previewUrl} alt="" className="h-full w-full object-cover" />
              ) : (
                <span className="flex h-full w-full items-center justify-center text-[9px] text-dfui-muted">
                  IMG
                </span>
              )}
              {referenceSlots.length > 1 ? (
                <span className="absolute left-0 top-0 rounded-br bg-df-blue/80 px-1 text-[8px] font-bold text-white">
                  1
                </span>
              ) : null}
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex min-w-0 items-start justify-between gap-2">
                <div className="min-w-0">
                  {referenceSlots.length > 1 ? (
                    <p className="text-[9px] font-semibold text-df-blue/90">Image 1</p>
                  ) : null}
                  <p className="truncate font-mono text-[10px] text-dfui-fg" title={attachedPath}>
                    {basename(attachedPath)}
                  </p>
                  <p className="mt-0.5 text-[9px] text-dfui-muted">
                    {referenceAttachedLabel(studioMode, settings)}
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
                {attachMode !== "upscale" && (
                  <span className="inline-flex rounded border border-dfui-border/50 bg-dfui-bg/60 px-1.5 py-0.5 text-[9px] text-dfui-secondary">
                    Strength {Math.round(editStrength * 100)}%
                  </span>
                )}
                {studioMode === "inpaint" && (
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
                {(extraReferences.length > 0 || referenceSlots.length > 1) && (
                  <span className="rounded border border-df-blue/30 bg-df-blue/10 px-1.5 py-0.5 text-[9px] text-df-blue">
                    +{Math.max(extraReferences.length, referenceSlots.length - 1)} ref
                  </span>
                )}
              </div>
              {studioMode === "inpaint" && onOpenInpaintMask && (
                <button
                  type="button"
                  disabled={disabled}
                  onClick={onOpenInpaintMask}
                  className={`${compact ? "mt-1 h-6 px-2" : "mt-2 px-2 py-1.5"} inline-flex w-full items-center justify-center gap-1.5 rounded-md border border-dfui-accent/50 bg-dfui-accent/10 text-[10px] font-semibold text-dfui-accent transition hover:border-dfui-accent/80 hover:bg-dfui-accent/15 disabled:opacity-50`}
                  title="Open full-screen mask editor (brush, tap selection, grow/shrink)"
                >
                  <Paintbrush size={12} />
                  {simpleExperience ? "Paint mask" : "Full-screen mask"}
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
              {dragOver ? `Drop as ${dropActionLabel}` : "Attach image"}
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
      {showKeepFace && (
        <label
          className="mx-2.5 mb-2 flex items-center justify-between gap-2 rounded-md border border-dfui-border/35 bg-dfui-bg/35 px-2 py-1.5"
          title="Route to Kontext or Qwen Edit to keep the same face/character in a new scene"
        >
          <span className="text-[10px] text-dfui-muted">Keep face / character</span>
          <input
            type="checkbox"
            disabled={disabled}
            checked={keepFaceActive}
            onChange={(e) => onPatchSettings?.(patchForKeepFace(e.target.checked, settings))}
            className="h-3.5 w-3.5 accent-df-blue"
          />
        </label>
      )}
      {showMultiSlots && activeReferenceRole === "image_prompt" && onPatchSettings && (
        <label
          className="mx-2.5 mb-2 flex items-center gap-2 rounded-md border border-dfui-border/35 bg-dfui-bg/35 px-2 py-1.5"
          title="IP-Adapter stop-at (sampling step fraction)"
        >
          <span className="min-w-[58px] text-[9px] text-dfui-muted">Stop at</span>
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            disabled={disabled}
            value={referenceSlots[0]?.stop_at ?? DEFAULT_SLOT_STOP_AT}
            onChange={(e) => {
              const patch = updateReferenceSlotAt(
                settings,
                0,
                { stop_at: Number(e.target.value) },
                studioMode,
              );
              if (patch) onPatchSettings(patch);
            }}
            className="h-1.5 min-w-0 flex-1 accent-df-blue"
          />
          <span className="w-8 text-right font-mono text-[9px] text-dfui-secondary">
            {Math.round((referenceSlots[0]?.stop_at ?? DEFAULT_SLOT_STOP_AT) * 100)}%
          </span>
        </label>
      )}
      {showMultiSlots && (
        <ReferenceSlotsEditor
          settings={settings}
          studioMode={studioMode}
          disabled={disabled}
          showRoles={showRoles}
          maxSlots={maxSlots}
          onAddSlot={(slot) => {
            const patch = appendReferenceSlot(settings, slot, studioMode, maxSlots);
            if (patch) onPatchSettings?.(patch);
          }}
          onUpdateSlot={(index, slotPatch) => {
            const patch = updateReferenceSlotAt(settings, index, slotPatch, studioMode, maxSlots);
            if (patch) onPatchSettings?.(patch);
          }}
          onRemoveSlot={(index) => onPatchSettings?.(removeReferenceSlotAt(settings, index, studioMode, maxSlots))}
        />
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
                  title="Remove reference"
                >
                  <X size={10} />
                </button>
              )}
            </span>
          ))}
          {atReferenceCap ? (
            <span
              className="rounded border border-dfui-border/50 px-1.5 py-0.5 text-[9px] text-dfui-muted"
              title={
                modelFamily === "qwen_image_edit"
                  ? `Qwen Edit supports up to ${maxSlots} images`
                  : `Up to ${maxSlots} reference images`
              }
            >
              Max {maxSlots} images
            </span>
          ) : (
            <button
              type="button"
              disabled={disabled}
              onClick={() => void onChooseExtraFile()}
              className="rounded border border-dashed border-dfui-border/70 px-1.5 py-0.5 text-[9px] text-dfui-accent hover:border-dfui-accent/50 disabled:opacity-50"
              title="Add another reference image"
            >
              + reference
            </button>
          )}
        </div>
      )}
    </motion.div>
  );
}
