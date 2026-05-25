import { ImagePlus, Maximize2, Paintbrush, Wand2, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { readImagePreviewQueued } from "../lib/preview-queue";
import {
  REFERENCE_IMAGE_MODES,
  activeReferenceMode,
  activeReferencePath,
  basename,
  readImagePathFromDrop,
  type ReferenceImageMode,
} from "../lib/referenceImage";
import type { GenerationSettings } from "../lib/tauri-api";
import { pickImageFile } from "../lib/tauri-api";

type Props = {
  settings: GenerationSettings;
  onAttach: (path: string, mode: ReferenceImageMode) => void;
  onClear: () => void;
  onOpenInpaintMask?: () => void;
  disabled?: boolean;
};

export function ReferenceImageControl({
  settings,
  onAttach,
  onClear,
  onOpenInpaintMask,
  disabled = false,
}: Props) {
  const [open, setOpen] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [mode, setMode] = useState<ReferenceImageMode>(() =>
    activeReferenceMode(settings),
  );
  const rootRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const attachedPath = activeReferencePath(settings);
  const attachedMode = activeReferenceMode(settings);

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

  useEffect(() => {
    if (!open) return;
    const onDocClick = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [open]);

  const selectMode = (nextMode: ReferenceImageMode) => {
    setMode(nextMode);
    setOpen(false);
  };

  const attachPath = (path: string, nextMode = mode) => {
    onAttach(path, nextMode);
    setMode(nextMode);
    setOpen(false);
    setDragOver(false);
  };

  const onDrop = (event: React.DragEvent) => {
    event.preventDefault();
    setDragOver(false);
    const path = readImagePathFromDrop(event.dataTransfer);
    if (path) attachPath(path);
  };

  const onChooseFile = async () => {
    try {
      const path = await pickImageFile();
      if (path) attachPath(path);
    } catch {
      fileInputRef.current?.click();
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

  const modeIcon = (id: ReferenceImageMode) => {
    if (id === "upscale") return Maximize2;
    if (id === "inpaint") return Paintbrush;
    return Wand2;
  };

  return (
    <motion.div
      ref={rootRef}
      onDragEnter={(event) => {
        event.preventDefault();
        if (!disabled) setDragOver(true);
      }}
      onDragOver={(event) => {
        event.preventDefault();
        if (!disabled) setDragOver(true);
      }}
      onDragLeave={(event) => {
        if (!rootRef.current?.contains(event.relatedTarget as Node)) {
          setDragOver(false);
        }
      }}
      onDrop={onDrop}
      className={`relative flex items-center gap-2 rounded-lg border px-2 py-1.5 transition-colors ${
        dragOver
          ? "border-df-blue/70 bg-df-blue/10 ring-1 ring-df-blue/30"
          : attachedPath
            ? "border-dfui-accent/40 bg-dfui-bg/50"
            : "border-dfui-border/50 bg-dfui-bg/30"
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

      {attachedPath ? (
        <>
          <div className="h-10 w-10 shrink-0 overflow-hidden rounded-md border border-dfui-border/60 bg-dfui-bg">
            {previewUrl ? (
              <img
                src={previewUrl}
                alt=""
                className="h-full w-full object-cover"
              />
            ) : (
              <span className="flex h-full w-full items-center justify-center text-[9px] text-dfui-muted">
                IMG
              </span>
            )}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate font-mono text-[10px] text-dfui-fg">
              {basename(attachedPath)}
            </p>
            <p className="text-[9px] text-dfui-muted">
              {
                REFERENCE_IMAGE_MODES.find((item) => item.id === attachedMode)
                  ?.label
              }
              {settings.inpaint_mask_path ? " · mask set" : ""}
            </p>
          </div>
          {attachedMode === "inpaint" && onOpenInpaintMask && (
            <button
              type="button"
              disabled={disabled}
              onClick={onOpenInpaintMask}
              className="rounded border border-dfui-border/50 px-1.5 py-0.5 text-[9px] text-dfui-accent hover:border-dfui-accent/50"
              title="Paint inpaint mask"
            >
              Mask
            </button>
          )}
          <button
            type="button"
            disabled={disabled}
            onClick={onClear}
            className="rounded p-1 text-dfui-muted hover:bg-dfui-surface-hover hover:text-red-300 disabled:opacity-50"
            title="Remove attached image"
          >
            <X size={14} />
          </button>
        </>
      ) : (
        <p className="min-w-0 flex-1 truncate text-[10px] text-dfui-muted">
          {dragOver
            ? "Drop image here"
            : "Attach reference · drag from history"}
        </p>
      )}

      <div className="relative shrink-0">
        <button
          type="button"
          disabled={disabled}
          onClick={() => setOpen((value) => !value)}
          className="inline-flex items-center gap-1 rounded-md border border-dfui-border/70 bg-dfui-panel px-2 py-1.5 text-[11px] font-medium text-dfui-fg hover:border-df-blue/40 disabled:opacity-50"
          title="Choose or attach input image"
        >
          <ImagePlus size={14} className="text-df-blue" />
          Image
        </button>

        <AnimatePresence>
          {open && (
            <motion.div
              initial={{ opacity: 0, y: 6, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 6, scale: 0.98 }}
              transition={{ duration: 0.15 }}
              className="absolute bottom-full right-0 z-50 mb-2 w-56 rounded-lg border border-dfui-border bg-dfui-panel p-2 shadow-glass"
            >
              <p className="px-1 pb-1 text-[10px] font-semibold uppercase tracking-wide text-dfui-muted">
                Input image mode
              </p>
              <div className="space-y-1">
                {REFERENCE_IMAGE_MODES.map((item) => {
                  const Icon = modeIcon(item.id);
                  const active = mode === item.id;
                  return (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => selectMode(item.id)}
                      className={`flex w-full items-start gap-2 rounded-md px-2 py-1.5 text-left text-[11px] transition ${
                        active
                          ? "border border-df-blue/40 bg-df-blue/10 text-dfui-fg"
                          : "border border-transparent text-dfui-secondary hover:bg-dfui-surface-hover"
                      }`}
                    >
                      <Icon size={13} className="mt-0.5 shrink-0 text-df-blue" />
                      <span>
                        <span className="block font-medium">{item.label}</span>
                        <span className="block text-[10px] text-dfui-muted">
                          {item.description}
                        </span>
                      </span>
                    </button>
                  );
                })}
              </div>
              <button
                type="button"
                onClick={() => void onChooseFile()}
                className="mt-2 flex w-full items-center justify-center gap-1.5 rounded-md border border-dfui-border/70 bg-dfui-bg/60 px-2 py-1.5 text-[11px] font-medium text-dfui-fg hover:border-df-blue/40"
              >
                <ImagePlus size={13} />
                Choose file…
              </button>
              {attachedPath && (
                <button
                  type="button"
                  onClick={() => attachPath(attachedPath, mode)}
                  className="mt-1 flex w-full items-center justify-center rounded-md border border-dfui-accent/40 px-2 py-1.5 text-[11px] text-dfui-accent hover:bg-dfui-accent/10"
                >
                  Apply {REFERENCE_IMAGE_MODES.find((m) => m.id === mode)?.short}{" "}
                  mode
                </button>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}
