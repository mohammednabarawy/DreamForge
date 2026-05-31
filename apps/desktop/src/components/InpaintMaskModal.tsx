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
import { readImagePreviewQueued } from "../lib/preview-queue";
import {
  generateInpaintSelectionMask,
  type InpaintSelectionKind,
  writeTempPng,
} from "../lib/studioBridge";

type Props = {
  imagePath: string;
  open: boolean;
  onClose: () => void;
  onSave: (maskPath: string) => void;
  /** Called whenever the mask bitmap changes (grow/shrink, paint, etc.). */
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

function readMaskBinary(data: Uint8ClampedArray, width: number, height: number): Uint8Array {
  const binary = new Uint8Array(width * height);
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const i = (y * width + x) * 4;
      binary[y * width + x] = isMaskPixelSelected(data, i) ? 1 : 0;
    }
  }
  return binary;
}

function writeMaskImageData(
  target: ImageData,
  binary: Uint8Array,
  width: number,
  height: number,
) {
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const idx = y * width + x;
      const i = idx * 4;
      const v = binary[idx] ? 255 : 0;
      target.data[i] = v;
      target.data[i + 1] = v;
      target.data[i + 2] = v;
      target.data[i + 3] = 255;
    }
  }
}

/** Morphological grow (dilate) or shrink (erode) by N pixels on an 8-connected grid. */
function morphMaskBinary(
  binary: Uint8Array,
  width: number,
  height: number,
  pixels: number,
  grow: boolean,
): Uint8Array {
  const steps = Math.max(0, Math.floor(pixels));
  if (steps === 0) return binary;

  let current = binary;
  for (let step = 0; step < steps; step++) {
    const next = new Uint8Array(width * height);
    for (let y = 0; y < height; y++) {
      for (let x = 0; x < width; x++) {
        const idx = y * width + x;
        if (grow) {
          let selected = current[idx] === 1;
          if (!selected) {
            for (let dy = -1; dy <= 1 && !selected; dy++) {
              for (let dx = -1; dx <= 1 && !selected; dx++) {
                const nx = x + dx;
                const ny = y + dy;
                if (nx < 0 || nx >= width || ny < 0 || ny >= height) continue;
                if (current[ny * width + nx] === 1) selected = true;
              }
            }
          }
          next[idx] = selected ? 1 : 0;
        } else {
          let selected = current[idx] === 1;
          if (selected) {
            for (let dy = -1; dy <= 1 && selected; dy++) {
              for (let dx = -1; dx <= 1 && selected; dx++) {
                const nx = x + dx;
                const ny = y + dy;
                if (nx < 0 || nx >= width || ny < 0 || ny >= height) {
                  selected = false;
                  break;
                }
                if (current[ny * width + nx] !== 1) selected = false;
              }
            }
          }
          next[idx] = selected ? 1 : 0;
        }
      }
    }
    current = next;
  }
  return current;
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

export function InpaintMaskModal({ imagePath, open, onClose, onSave, onMaskChange }: Props) {
  /** Visible: photo + pale red selection preview. */
  const viewCanvasRef = useRef<HTMLCanvasElement>(null);
  /** Hidden: grayscale mask for inpaint export only. */
  const maskRef = useRef<HTMLCanvasElement | null>(null);
  /** Builds red tint from mask without touching unselected pixels. */
  const overlayHelperRef = useRef<HTMLCanvasElement | null>(null);
  const baseImageRef = useRef<HTMLImageElement | null>(null);
  const dimsRef = useRef({ w: 512, h: 512 });

  const [viewSize, setViewSize] = useState({ w: 512, h: 512 });
  const [brush, setBrush] = useState(24);
  const [tool, setTool] = useState<SelectTool>("paint");
  const [mergeMode, setMergeMode] = useState<"add" | "replace">("add");
  const [morphPixels, setMorphPixels] = useState(1);
  const [morphPixelsInput, setMorphPixelsInput] = useState("1");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");
  const [ready, setReady] = useState(false);
  const drawing = useRef(false);

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

  const publishMask = useCallback(async () => {
    const mask = maskRef.current;
    if (!mask) return;
    const dataUrl = mask.toDataURL("image/png");
    const path = await writeTempPng(dataUrl);
    onMaskChange?.(path);
    return path;
  }, [onMaskChange]);

  const morphMask = useCallback(
    (grow: boolean) => {
      const mask = maskRef.current;
      if (!mask) return;
      const ctx = mask.getContext("2d");
      if (!ctx) return;

      const parsed = Number.parseInt(morphPixelsInput, 10);
      const pixels = Number.isFinite(parsed)
        ? Math.max(1, Math.min(64, parsed))
        : Math.max(1, Math.min(64, morphPixels));
      setMorphPixels(pixels);
      setMorphPixelsInput(String(pixels));

      const image = ctx.getImageData(0, 0, mask.width, mask.height);
      const binary = readMaskBinary(image.data, mask.width, mask.height);
      const morphed = morphMaskBinary(binary, mask.width, mask.height, pixels, grow);
      writeMaskImageData(image, morphed, mask.width, mask.height);
      ctx.putImageData(image, 0, 0);
      redrawView();
      void publishMask();
      setStatus(grow ? `Grew selection by ${pixels}px` : `Shrunk selection by ${pixels}px`);
    },
    [morphPixels, morphPixelsInput, publishMask, redrawView],
  );

  const commitMorphPixelsInput = useCallback(() => {
    const parsed = Number.parseInt(morphPixelsInput, 10);
    if (!Number.isFinite(parsed)) {
      setMorphPixelsInput(String(morphPixels));
      return;
    }
    const clamped = Math.max(1, Math.min(64, parsed));
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
    };
  }, [open, imagePath, setupSession]);

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

  const clearMask = () => {
    const mask = maskRef.current;
    if (!mask) return;
    const ctx = mask.getContext("2d");
    if (!ctx) return;
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, mask.width, mask.height);
    redrawView();
    setStatus("Selection cleared");
  };

  const applyMaskImageData = useCallback(
    async (maskPath: string, mode: "add" | "replace") => {
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
    },
    [redrawView],
  );

  const runSelection = useCallback(
    async (selection: InpaintSelectionKind, tap?: { x: number; y: number }) => {
      if (!imagePath) return;
      setBusy(true);
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
        setStatus(
          `${selection.replace(/_/g, " ")} · ${result.method ?? "ready"}${
            result.coverage != null ? ` · ${Math.round(result.coverage * 100)}%` : ""
          }`,
        );
      } catch (err) {
        setStatus(err instanceof Error ? err.message : "Selection failed");
      } finally {
        setBusy(false);
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
    const path = await publishMask();
    if (!path) return;
    onSave(path);
    onClose();
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
      <div className="flex max-h-[92vh] w-full max-w-3xl flex-col rounded-xl border border-dfui-border/60 bg-dfui-panel shadow-2xl">
        <div className="flex items-center justify-between border-b border-dfui-border/40 px-3 py-2">
          <div>
            <span className="text-sm font-medium text-dfui-fg">Inpaint selection</span>
            <p className="text-[10px] text-dfui-tertiary">
              Your image with a pale red tint on the selected area — the B&amp;W mask is only used internally
            </p>
          </div>
          <button type="button" onClick={onClose} className="text-dfui-muted hover:text-dfui-fg">
            <X size={18} />
          </button>
        </div>

        <div className="flex flex-wrap gap-1.5 border-b border-dfui-border/30 px-3 py-2">
          {QUICK_SELECTS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              type="button"
              disabled={busy || !ready}
              onClick={() => void runSelection(id)}
              className="flex items-center gap-1 rounded border border-dfui-border/50 px-2 py-1 text-[10px] text-dfui-secondary hover:border-dfui-accent/40 hover:text-dfui-accent disabled:opacity-50"
            >
              {Icon ? <Icon size={11} /> : <Sparkles size={11} />}
              {label}
            </button>
          ))}
        </div>

        <div
          className="relative mx-auto overflow-hidden rounded-lg border border-dfui-border/50 bg-dfui-bg"
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
            onPointerUp={() => {
              drawing.current = false;
            }}
          />
          {!ready && (
            <div className="absolute inset-0 flex items-center justify-center bg-dfui-bg/80 text-[10px] text-dfui-muted">
              Loading image…
            </div>
          )}
        </div>

        <div className="space-y-2 border-t border-dfui-border/40 px-3 py-2">
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => setTool("paint")}
              className={`flex items-center gap-1 rounded px-2 py-1 text-[10px] ${
                tool === "paint" ? "bg-dfui-accent/20 text-dfui-accent" : "text-dfui-muted"
              }`}
            >
              <Paintbrush size={12} /> Brush
            </button>
            <button
              type="button"
              onClick={() => setTool("erase")}
              className={`flex items-center gap-1 rounded px-2 py-1 text-[10px] ${
                tool === "erase" ? "bg-dfui-accent/20 text-dfui-accent" : "text-dfui-muted"
              }`}
            >
              <Eraser size={12} /> Erase
            </button>
            <button
              type="button"
              onClick={() => setTool("tap_object")}
              className={`flex items-center gap-1 rounded px-2 py-1 text-[10px] ${
                tool === "tap_object" ? "bg-dfui-accent/20 text-dfui-accent" : "text-dfui-muted"
              }`}
            >
              <MousePointer2 size={12} /> Tap object
            </button>
            <button
              type="button"
              onClick={() => setTool("tap_background")}
              className={`flex items-center gap-1 rounded px-2 py-1 text-[10px] ${
                tool === "tap_background" ? "bg-dfui-accent/20 text-dfui-accent" : "text-dfui-muted"
              }`}
            >
              <MousePointer2 size={12} /> Tap background
            </button>
            <label className="flex items-center gap-1 text-[10px] text-dfui-muted">
              Brush
              <input
                type="range"
                min={4}
                max={96}
                value={brush}
                onChange={(e) => setBrush(Number(e.target.value))}
                className="w-20 accent-dfui-accent"
              />
            </label>
            <select
              value={mergeMode}
              onChange={(e) => setMergeMode(e.target.value as "add" | "replace")}
              className="df-select px-2 py-1 text-[10px]"
            >
              <option value="add">Add to selection</option>
              <option value="replace">Replace selection</option>
            </select>
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] text-dfui-muted">Grow/decrease mask</span>
              <button
                type="button"
                disabled={busy || !ready}
                aria-label="Grow mask"
                onClick={() => morphMask(true)}
                className="rounded border border-dfui-border/50 p-1 text-dfui-secondary hover:border-dfui-accent/40 hover:text-dfui-accent disabled:opacity-50"
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
                className="df-input w-12 px-1 py-0.5 text-center font-mono text-[10px]"
                aria-label="Mask grow or shrink pixels"
              />
              <button
                type="button"
                disabled={busy || !ready}
                aria-label="Decrease mask"
                onClick={() => morphMask(false)}
                className="rounded border border-dfui-border/50 p-1 text-dfui-secondary hover:border-dfui-accent/40 hover:text-dfui-accent disabled:opacity-50"
              >
                <ChevronDown size={14} />
              </button>
            </div>
            <button
              type="button"
              onClick={clearMask}
              className="text-[10px] text-dfui-tertiary hover:text-dfui-fg"
            >
              Clear
            </button>
          </div>
          {status && <p className="text-[10px] text-dfui-tertiary">{status}</p>}
          <div className="flex justify-end">
            <button
              type="button"
              disabled={busy || !ready}
              onClick={() => void exportMask()}
              className="rounded-lg bg-dfui-accent px-3 py-1.5 text-xs font-medium text-dfui-bg hover:opacity-90 disabled:opacity-50"
            >
              Apply selection
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
