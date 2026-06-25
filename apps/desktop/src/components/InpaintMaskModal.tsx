import {
  ChevronDown,
  ChevronUp,
  Eraser,
  MousePointer2,
  Paintbrush,
  ScanFace,
  Shirt,
  Sparkles,
  User,
  X,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  clampMorphPixels,
  morphMaskBinary,
  readMaskBinary,
  writeMaskImageData,
} from "../lib/inpaintMaskMorph";
import { readImagePreviewQueued } from "../lib/preview-queue";
import {
  MASK_PUBLISH_DEBOUNCE_MS,
  maskHasSelection,
  useMaskPublisher,
} from "../lib/useMaskPublisher";
import {
  generateInpaintSelectionMask,
  type InpaintSelectionKind,
} from "../lib/studioBridge";

type Props = {
  imagePath: string;
  /** Restore the last committed mask when reopening the editor. */
  initialMaskPath?: string;
  open: boolean;
  onClose: () => void;
  onSave: (maskPath: string) => void;
  /** Live sync to app settings (debounced while painting). */
  onMaskChange?: (maskPath: string) => void;
};

type SelectTool = "paint" | "erase" | "tap_object" | "tap_background";

const QUICK_SELECTS: { id: InpaintSelectionKind; label: string; icon?: typeof User }[] = [
  { id: "subject", label: "Subject", icon: User },
  { id: "background", label: "Background" },
  { id: "clothes", label: "Clothes", icon: Shirt },
  { id: "face", label: "Face", icon: ScanFace },
  { id: "eyes", label: "Eyes" },
  { id: "hands", label: "Hands" },
  { id: "legs", label: "Legs" },
  { id: "feet", label: "Feet" },
];

/** Photoshop-style quick-mask tint (not exported). */
const OVERLAY_R = 255;
const OVERLAY_G = 96;
const OVERLAY_B = 96;
const OVERLAY_A = 97;

function isMaskPixelSelected(data: Uint8ClampedArray, offset: number): boolean {
  return (data[offset] + data[offset + 1] + data[offset + 2]) / 3 > 127;
}

function getOffscreenMask(w: number, h: number, maskRef: React.MutableRefObject<HTMLCanvasElement | null>) {
  if (!maskRef.current) {
    maskRef.current = document.createElement("canvas");
  }
  const mask = maskRef.current;
  if (mask.width !== w || mask.height !== h) {
    mask.width = w;
    mask.height = h;
    const ctx = mask.getContext("2d");
    if (ctx) {
      ctx.fillStyle = "#000";
      ctx.fillRect(0, 0, w, h);
    }
  }
  return mask;
}

export function InpaintMaskModal({
  imagePath,
  initialMaskPath,
  open,
  onClose,
  onSave,
  onMaskChange,
}: Props) {
  /** Visible: photo + pale red selection preview. */
  const viewCanvasRef = useRef<HTMLCanvasElement>(null);
  /** Hidden: grayscale mask for inpaint export only. */
  const maskRef = useRef<HTMLCanvasElement | null>(null);
  /** Builds red tint from mask without touching unselected pixels. */
  const overlayHelperRef = useRef<HTMLCanvasElement | null>(null);
  const baseImageRef = useRef<HTMLImageElement | null>(null);
  const dimsRef = useRef({ w: 512, h: 512 });
  const [applying, setApplying] = useState(false);

  const [viewSize, setViewSize] = useState({ w: 512, h: 512 });
  const [brush, setBrush] = useState(24);
  const [tool, setTool] = useState<SelectTool>("paint");
  const [mergeMode, setMergeMode] = useState<"add" | "replace">("add");
  const [morphPixels, setMorphPixels] = useState(1);
  const [morphPixelsInput, setMorphPixelsInput] = useState("1");
  const [detecting, setDetecting] = useState(false);
  const [morphBusy, setMorphBusy] = useState(false);
  const [status, setStatus] = useState("");
  const [ready, setReady] = useState(false);
  const drawing = useRef(false);
  const getMaskCanvas = useCallback(() => maskRef.current, []);
  const { publishMask, exportMaskNow, syncing: maskSyncing, cancelScheduled } = useMaskPublisher(
    getMaskCanvas,
    onMaskChange,
    MASK_PUBLISH_DEBOUNCE_MS,
  );
  const busy = detecting || morphBusy || maskSyncing || applying;
  const activeToolLabel = (typeof tool === "string" ? tool : "paint").replace(/_/g, " ");

  const redrawView = useCallback(() => {
    const view = viewCanvasRef.current;
    const baseImage = baseImageRef.current;
    const mask = maskRef.current;
    if (!view || !baseImage || !mask) return;

    const w = view.width;
    const h = view.height;
    const ctx = view.getContext("2d");
    if (!ctx || w <= 0 || h <= 0) return;

    ctx.clearRect(0, 0, w, h);
    ctx.globalCompositeOperation = "source-over";
    ctx.globalAlpha = 1;
    ctx.drawImage(baseImage, 0, 0, w, h);

    const maskCtx = mask.getContext("2d");
    if (!maskCtx) return;
    const maskData = maskCtx.getImageData(0, 0, w, h);

    // Grayscale mask pixels are opaque black/white — use luminance, not alpha, for selection.
    if (!overlayHelperRef.current) {
      overlayHelperRef.current = document.createElement("canvas");
    }
    const overlay = overlayHelperRef.current;
    if (overlay.width !== w || overlay.height !== h) {
      overlay.width = w;
      overlay.height = h;
    }
    const octx = overlay.getContext("2d");
    if (!octx) return;

    const overlayData = octx.createImageData(w, h);
    for (let i = 0; i < maskData.data.length; i += 4) {
      if (isMaskPixelSelected(maskData.data, i)) {
        overlayData.data[i] = OVERLAY_R;
        overlayData.data[i + 1] = OVERLAY_G;
        overlayData.data[i + 2] = OVERLAY_B;
        overlayData.data[i + 3] = OVERLAY_A;
      }
    }
    octx.putImageData(overlayData, 0, 0);

    ctx.globalCompositeOperation = "source-over";
    ctx.globalAlpha = 1;
    ctx.drawImage(overlay, 0, 0, w, h);
  }, []);

  const resolveMorphPixels = useCallback(() => {
    const parsed = Number.parseInt(morphPixelsInput, 10);
    const pixels = clampMorphPixels(
      Number.isFinite(parsed) ? parsed : morphPixels,
      morphPixels,
    );
    setMorphPixels(pixels);
    setMorphPixelsInput(String(pixels));
    return pixels;
  }, [morphPixels, morphPixelsInput]);

  const morphMask = useCallback(
    (grow: boolean) => {
      const mask = maskRef.current;
      if (!mask) return;
      const ctx = mask.getContext("2d");
      if (!ctx) return;

      const pixels = resolveMorphPixels();
      setMorphBusy(true);
      window.requestAnimationFrame(() => {
        try {
          const image = ctx.getImageData(0, 0, mask.width, mask.height);
          const binary = readMaskBinary(image.data, mask.width, mask.height);
          const morphed = morphMaskBinary(binary, mask.width, mask.height, pixels, grow);
          writeMaskImageData(image, morphed, mask.width, mask.height);
          ctx.putImageData(image, 0, 0);
          redrawView();
          void publishMask({ immediate: true });
          setStatus(grow ? `Grew selection by ${pixels}px` : `Shrunk selection by ${pixels}px`);
        } finally {
          setMorphBusy(false);
        }
      });
    },
    [publishMask, redrawView, resolveMorphPixels],
  );

  const commitMorphPixelsInput = useCallback(() => {
    const parsed = Number.parseInt(morphPixelsInput, 10);
    if (!Number.isFinite(parsed)) {
      setMorphPixelsInput(String(morphPixels));
      return;
    }
    const clamped = clampMorphPixels(parsed, morphPixels);
    setMorphPixels(clamped);
    setMorphPixelsInput(String(clamped));
  }, [morphPixels, morphPixelsInput]);

  const setupSession = useCallback(
    (w: number, h: number, image: HTMLImageElement, attempt = 0) => {
      baseImageRef.current = image;
      dimsRef.current = { w, h };
      setViewSize({ w, h });

      const view = viewCanvasRef.current;
      if (!view) {
        if (attempt < 8) {
          requestAnimationFrame(() => setupSession(w, h, image, attempt + 1));
        }
        return;
      }

      view.width = w;
      view.height = h;
      getOffscreenMask(w, h, maskRef);
      setReady(true);
      redrawView();
    },
    [redrawView],
  );

  useEffect(() => {
    if (!open || !imagePath) return;
    let cancelled = false;
    setReady(false);
    setStatus("");
    baseImageRef.current = null;
    if (maskRef.current) {
      const ctx = maskRef.current.getContext("2d");
      if (ctx) {
        ctx.fillStyle = "#000";
        ctx.fillRect(0, 0, maskRef.current.width, maskRef.current.height);
      }
    }

    void readImagePreviewQueued(imagePath).then((r) => {
      if (cancelled) return;
      const img = new Image();
      img.onload = () => {
        if (cancelled) return;
        if (img.naturalWidth <= 0 || img.naturalHeight <= 0) {
          setStatus("Could not load image preview");
          return;
        }
        const max = 768;
        let w = img.naturalWidth;
        let h = img.naturalHeight;
        const scale = Math.min(1, max / Math.max(w, h));
        w = Math.round(w * scale);
        h = Math.round(h * scale);
        requestAnimationFrame(() => {
          if (cancelled) return;
          setupSession(w, h, img);
        });
      };
      img.onerror = () => {
        if (!cancelled) setStatus("Could not load image preview");
      };
      img.src = r.data_url;
    });

    return () => {
      cancelled = true;
      cancelScheduled();
    };
  }, [cancelScheduled, open, imagePath, setupSession]);

  const pointerToMaskCoords = (clientX: number, clientY: number) => {
    const view = viewCanvasRef.current;
    if (!view) return null;
    const rect = view.getBoundingClientRect();
    const x = ((clientX - rect.left) / rect.width) * view.width;
    const y = ((clientY - rect.top) / rect.height) * view.height;
    return { x, y, view };
  };

  const paintMask = useCallback(
    (clientX: number, clientY: number) => {
      const coords = pointerToMaskCoords(clientX, clientY);
      if (!coords) return;
      const mask = getOffscreenMask(dimsRef.current.w, dimsRef.current.h, maskRef);
      const ctx = mask.getContext("2d");
      if (!ctx) return;

      ctx.globalCompositeOperation = "source-over";
      ctx.fillStyle = tool === "erase" ? "#000" : "#fff";
      ctx.beginPath();
      ctx.arc(coords.x, coords.y, brush, 0, Math.PI * 2);
      ctx.fill();
      redrawView();
    },
    [brush, redrawView, tool],
  );

  const endStroke = useCallback(() => {
    drawing.current = false;
    void publishMask({ immediate: true });
  }, [publishMask]);

  const clearMask = useCallback(() => {
    const mask = maskRef.current;
    if (!mask) return;
    const ctx = mask.getContext("2d");
    if (!ctx) return;
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, mask.width, mask.height);
    redrawView();
    void publishMask({ immediate: true });
    setStatus("Selection cleared");
  }, [publishMask, redrawView]);

  const applyMaskImageData = useCallback(
    async (maskPath: string, mode: "add" | "replace", publish = true) => {
      const mask = getOffscreenMask(dimsRef.current.w, dimsRef.current.h, maskRef);
      const ctx = mask.getContext("2d");
      if (!ctx) return;

      const preview = await readImagePreviewQueued(maskPath);
      const img = new Image();
      await new Promise<void>((resolve, reject) => {
        img.onload = () => resolve();
        img.onerror = () => reject(new Error("mask_preview_failed"));
        img.src = preview.data_url;
      });

      const temp = document.createElement("canvas");
      temp.width = mask.width;
      temp.height = mask.height;
      const tctx = temp.getContext("2d");
      if (!tctx) return;
      tctx.drawImage(img, 0, 0, mask.width, mask.height);

      const source = tctx.getImageData(0, 0, mask.width, mask.height);
      const target =
        mode === "replace"
          ? ctx.createImageData(mask.width, mask.height)
          : ctx.getImageData(0, 0, mask.width, mask.height);

      for (let i = 0; i < source.data.length; i += 4) {
        if (isMaskPixelSelected(source.data, i)) {
          target.data[i] = 255;
          target.data[i + 1] = 255;
          target.data[i + 2] = 255;
          target.data[i + 3] = 255;
        } else if (mode === "replace") {
          target.data[i] = 0;
          target.data[i + 1] = 0;
          target.data[i + 2] = 0;
          target.data[i + 3] = 255;
        }
      }
      ctx.putImageData(target, 0, 0);
      redrawView();
      if (publish) {
        await publishMask({ immediate: true });
      }
    },
    [publishMask, redrawView],
  );

  const restoredMaskKeyRef = useRef<string | null>(null);
  useEffect(() => {
    if (!open) {
      restoredMaskKeyRef.current = null;
      return;
    }
    const path = initialMaskPath?.trim();
    if (!ready || !path) return;
    const key = `${imagePath}:${path}`;
    if (restoredMaskKeyRef.current === key) return;
    restoredMaskKeyRef.current = key;
    let cancelled = false;
    void (async () => {
      try {
        await applyMaskImageData(path, "replace", false);
        if (!cancelled) setStatus("Restored previous mask");
      } catch {
        if (!cancelled) setStatus("Could not restore previous mask");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [applyMaskImageData, imagePath, initialMaskPath, open, ready]);

  const runSelection = useCallback(
    async (selection: InpaintSelectionKind, tap?: { x: number; y: number }) => {
      if (!imagePath) return;
      setDetecting(true);
      setStatus("Detecting selection…");
      try {
        const result = await generateInpaintSelectionMask({
          imagePath,
          selection,
          tapX: tap?.x,
          tapY: tap?.y,
        });
        if (!result.ok || !result.mask_path) {
          setStatus(result.error ?? "Selection failed");
          return;
        }
        await applyMaskImageData(result.mask_path, mergeMode);
        const selectionLabel = (typeof selection === "string" ? selection : "selection").replace(
          /_/g,
          " ",
        );
        setStatus(
          `${selectionLabel} · ${result.method ?? "ready"}${
            result.coverage != null ? ` · ${Math.round(result.coverage * 100)}%` : ""
          }`,
        );
      } catch (err) {
        setStatus(err instanceof Error ? err.message : "Selection failed");
      } finally {
        setDetecting(false);
      }
    },
    [applyMaskImageData, imagePath, mergeMode],
  );

  const handlePointer = useCallback(
    (clientX: number, clientY: number) => {
      const coords = pointerToMaskCoords(clientX, clientY);
      if (!coords) return;
      if (tool === "tap_object" || tool === "tap_background") {
        void runSelection(tool, {
          x: coords.x / coords.view.width,
          y: coords.y / coords.view.height,
        });
        return;
      }
      paintMask(clientX, clientY);
    },
    [paintMask, runSelection, tool],
  );

  const exportMask = async () => {
    if (applying) return;
    const { w, h } = dimsRef.current;
    if (!ready || w <= 0 || h <= 0) {
      setStatus("Image is still loading — wait a moment and try again.");
      return;
    }
    getOffscreenMask(w, h, maskRef);
    const mask = maskRef.current;
    if (!mask || !maskHasSelection(mask)) {
      setStatus("Paint or select a region before applying.");
      return;
    }
    setApplying(true);
    setStatus("Saving mask…");
    try {
      const path = await exportMaskNow();
      if (!path) {
        setStatus("Could not save the mask. Try again or restart the GPU engine.");
        return;
      }
      onSave(path);
      onClose();
    } catch (error) {
      setStatus(`Could not save mask: ${String(error)}`);
    } finally {
      setApplying(false);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/72 p-4 backdrop-blur-sm">
      <div className="flex h-[92vh] w-full max-w-6xl flex-col overflow-hidden rounded-xl border border-dfui-border/70 bg-dfui-panel shadow-2xl">
        <div className="flex shrink-0 items-start justify-between gap-4 border-b border-dfui-border/50 px-4 py-3">
          <div>
            <div className="flex items-center gap-2">
              <span className="rounded border border-dfui-accent/40 bg-dfui-accent/10 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-dfui-accent">
                Mask tools
              </span>
              <span className="text-sm font-medium text-dfui-fg">Inpaint selection</span>
            </div>
            <p className="mt-1 text-[10px] text-dfui-tertiary">
              Red tint is the selected edit area. The grayscale mask stays internal for the inpaint pipeline.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md p-1 text-dfui-muted transition hover:bg-dfui-surface-hover hover:text-dfui-fg"
          >
            <X size={18} />
          </button>
        </div>

        <div className="grid min-h-0 flex-1 grid-cols-[10rem_minmax(0,1fr)_17rem]">
          <aside className="border-r border-dfui-border/45 bg-dfui-bg/25 p-3">
            <p className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-dfui-muted">
              Tools
            </p>
            <div className="space-y-1">
              {[
                { id: "paint" as const, label: "Brush", icon: Paintbrush },
                { id: "erase" as const, label: "Erase", icon: Eraser },
                { id: "tap_object" as const, label: "Tap object", icon: MousePointer2 },
                { id: "tap_background" as const, label: "Tap background", icon: MousePointer2 },
              ].map(({ id, label, icon: Icon }) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => setTool(id)}
                  className={`flex w-full items-center gap-2 rounded-md border px-2 py-2 text-left text-[11px] transition ${
                    tool === id
                      ? "border-dfui-accent/45 bg-dfui-accent/15 text-dfui-accent"
                      : "border-transparent text-dfui-secondary hover:border-dfui-border/60 hover:bg-dfui-surface-hover hover:text-dfui-fg"
                  }`}
                >
                  <Icon size={14} />
                  {label}
                </button>
              ))}
            </div>
            <div className="mt-4 border-t border-dfui-border/35 pt-3">
              <div className="mb-1 flex items-center justify-between text-[10px] text-dfui-muted">
                <span>Brush size</span>
                <span className="font-mono text-dfui-secondary">{brush}px</span>
              </div>
              <input
                type="range"
                min={4}
                max={96}
                value={brush}
                onChange={(e) => setBrush(Number(e.target.value))}
                className="w-full accent-dfui-accent"
              />
            </div>
            <div className="mt-4 border-t border-dfui-border/35 pt-3">
              <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wide text-dfui-muted">
                Merge mode
              </p>
              <div className="grid grid-cols-2 overflow-hidden rounded-md border border-dfui-border/55 bg-dfui-bg/40">
                <button
                  type="button"
                  onClick={() => setMergeMode("add")}
                  className={`px-2 py-1.5 text-[10px] ${
                    mergeMode === "add"
                      ? "bg-dfui-accent/20 text-dfui-accent"
                      : "text-dfui-muted hover:text-dfui-fg"
                  }`}
                >
                  Add
                </button>
                <button
                  type="button"
                  onClick={() => setMergeMode("replace")}
                  className={`border-l border-dfui-border/55 px-2 py-1.5 text-[10px] ${
                    mergeMode === "replace"
                      ? "bg-dfui-accent/20 text-dfui-accent"
                      : "text-dfui-muted hover:text-dfui-fg"
                  }`}
                >
                  Replace
                </button>
              </div>
            </div>
          </aside>

          <main className="min-h-0 overflow-auto bg-dfui-bg/35 p-4">
            <div className="mb-2 flex items-center justify-between rounded-md border border-dfui-border/35 bg-dfui-panel/55 px-3 py-1.5">
              <span className="text-[10px] text-dfui-muted">
                Active tool: <span className="font-medium text-dfui-secondary">{activeToolLabel}</span>
              </span>
              <span className="text-[10px] text-dfui-tertiary">
                {ready ? `${viewSize.w} x ${viewSize.h}` : "Loading"}
              </span>
            </div>
            <div
              className="relative mx-auto overflow-hidden rounded-lg border border-dfui-border/55 bg-dfui-bg shadow-glass"
              style={{ width: viewSize.w, height: viewSize.h }}
            >
              <canvas
                ref={viewCanvasRef}
                className={`block max-w-full touch-none ${
                  tool === "tap_object" || tool === "tap_background"
                    ? "cursor-pointer"
                    : "cursor-crosshair"
                }`}
                style={{ width: viewSize.w, height: viewSize.h }}
                onPointerDown={(e) => {
                  if (busy || !ready) return;
                  drawing.current = tool === "paint" || tool === "erase";
                  (e.target as HTMLCanvasElement).setPointerCapture(e.pointerId);
                  handlePointer(e.clientX, e.clientY);
                }}
                onPointerMove={(e) => {
                  if (!drawing.current || busy || !ready) return;
                  if (tool !== "paint" && tool !== "erase") return;
                  paintMask(e.clientX, e.clientY);
                }}
                onPointerUp={endStroke}
                onPointerCancel={endStroke}
              />
              {!ready && (
                <div className="absolute inset-0 flex items-center justify-center bg-dfui-bg/80 text-[10px] text-dfui-muted">
                  Loading image...
                </div>
              )}
            </div>
          </main>

          <aside className="flex min-h-0 flex-col border-l border-dfui-border/45 bg-dfui-bg/25">
            <div className="border-b border-dfui-border/35 p-3">
              <p className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-dfui-muted">
                Quick select
              </p>
              <div className="grid grid-cols-2 gap-1.5">
                {QUICK_SELECTS.map(({ id, label, icon: Icon }) => (
                  <button
                    key={id}
                    type="button"
                    disabled={busy || !ready}
                    onClick={() => void runSelection(id)}
                    className="flex min-h-10 flex-col items-center justify-center gap-0.5 rounded-md border border-dfui-border/50 bg-dfui-panel/45 px-2 py-1 text-[10px] text-dfui-secondary transition hover:border-dfui-accent/50 hover:bg-dfui-accent/10 hover:text-dfui-accent disabled:opacity-50"
                  >
                    {Icon ? <Icon size={14} /> : <Sparkles size={14} />}
                    {label}
                  </button>
                ))}
              </div>
            </div>
            <div className="border-b border-dfui-border/35 p-3">
              <p className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-dfui-muted">
                Mask edge
              </p>
              <div className="flex items-center gap-1.5">
                <button
                  type="button"
                  disabled={busy || !ready}
                  aria-label="Grow mask"
                  onClick={() => morphMask(true)}
                  className="rounded border border-dfui-border/50 p-1.5 text-dfui-secondary hover:border-dfui-accent/40 hover:text-dfui-accent disabled:opacity-50"
                >
                  <ChevronUp size={14} />
                </button>
                <input
                  type="text"
                  inputMode="numeric"
                  pattern="[0-9]*"
                  value={morphPixelsInput}
                  disabled={busy || !ready}
                  onChange={(e) => setMorphPixelsInput(e.target.value.replace(/[^\d]/g, ""))}
                  onBlur={commitMorphPixelsInput}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      commitMorphPixelsInput();
                      (e.target as HTMLInputElement).blur();
                    }
                  }}
                  className="df-input w-14 px-1 py-1 text-center font-mono text-[10px]"
                  aria-label="Mask grow or shrink pixels"
                />
                <button
                  type="button"
                  disabled={busy || !ready}
                  aria-label="Decrease mask"
                  onClick={() => morphMask(false)}
                  className="rounded border border-dfui-border/50 p-1.5 text-dfui-secondary hover:border-dfui-accent/40 hover:text-dfui-accent disabled:opacity-50"
                >
                  <ChevronDown size={14} />
                </button>
              </div>
              <p className="mt-1.5 text-[9px] text-dfui-tertiary">
                Pixels per step — ↑ grow, ↓ shrink. Changes sync live to inpaint.
              </p>
            </div>
            <div className="mt-auto space-y-2 p-3">
              <button
                type="button"
                onClick={clearMask}
                className="w-full rounded-md border border-dfui-border/55 px-3 py-2 text-[10px] text-dfui-secondary hover:border-red-300/40 hover:text-red-300"
              >
                Clear mask
              </button>
              <button
                type="button"
                disabled={busy || !ready}
                onClick={() => void exportMask()}
                className="w-full rounded-lg bg-dfui-accent px-4 py-2.5 text-xs font-semibold text-dfui-bg hover:opacity-90 disabled:opacity-50"
              >
                Apply selection
              </button>
            </div>
          </aside>
        </div>

        <div className="flex shrink-0 items-center justify-between gap-3 border-t border-dfui-border/45 bg-dfui-bg/35 px-4 py-2 text-[10px] text-dfui-tertiary">
          <span>{status || "Choose a quick selection, tap an object, or paint directly."}</span>
          {detecting && <span className="font-medium text-dfui-accent">Detecting…</span>}
          {!detecting && maskSyncing && (
            <span className="font-medium text-dfui-accent">Syncing mask…</span>
          )}
        </div>
      </div>
    </div>
  );
}
