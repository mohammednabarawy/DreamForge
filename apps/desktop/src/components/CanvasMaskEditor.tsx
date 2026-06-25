import { useCallback, useEffect, useRef, useState } from "react";
import {
  drawMaskOverlayView,
  getOffscreenMask,
  isMaskPixelSelected,
  scaleImageDimensions,
} from "../lib/inpaintMaskOverlay";
import { readImagePreviewQueued } from "../lib/preview-queue";
import { generateInpaintSelectionMask, type InpaintSelectionKind } from "../lib/studioBridge";
import { useMaskPublisher } from "../lib/useMaskPublisher";
import { CanvasToolRail, type CanvasMaskTool } from "./CanvasToolRail";

type Props = {
  imagePath: string;
  initialMaskPath?: string;
  onMaskChange?: (path: string) => void;
  disabled?: boolean;
  maxDimension?: number;
  /** Pro: open full-screen mask modal with brush, tap selection, and morphology tools. */
  onOpenExpanded?: () => void;
};

export function CanvasMaskEditor({
  imagePath,
  initialMaskPath,
  onMaskChange,
  disabled = false,
  maxDimension = 768,
  onOpenExpanded,
}: Props) {
  const viewCanvasRef = useRef<HTMLCanvasElement>(null);
  const maskRef = useRef<HTMLCanvasElement | null>(null);
  const overlayHelperRef = useRef<HTMLCanvasElement | null>(null);
  const baseImageRef = useRef<HTMLImageElement | null>(null);
  const dimsRef = useRef({ w: 512, h: 512 });
  const drawing = useRef(false);
  const restoredMaskKeyRef = useRef<string | null>(null);

  const [viewSize, setViewSize] = useState({ w: 512, h: 512 });
  const [brush, setBrush] = useState(24);
  const [tool, setTool] = useState<CanvasMaskTool>("paint");
  const [detecting, setDetecting] = useState(false);
  const [ready, setReady] = useState(false);

  const getMaskCanvas = useCallback(() => maskRef.current, []);
  const { publishMask, syncing, cancelScheduled } = useMaskPublisher(
    getMaskCanvas,
    onMaskChange,
  );
  const busy = detecting || syncing || disabled;

  const redrawView = useCallback(() => {
    const view = viewCanvasRef.current;
    const baseImage = baseImageRef.current;
    const mask = maskRef.current;
    if (!view || !baseImage || !mask) return;
    drawMaskOverlayView(view, baseImage, mask, overlayHelperRef);
  }, []);

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
    if (!imagePath) return;
    let cancelled = false;
    setReady(false);
    baseImageRef.current = null;
    restoredMaskKeyRef.current = null;
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
        if (cancelled || img.naturalWidth <= 0 || img.naturalHeight <= 0) return;
        const { w, h } = scaleImageDimensions(
          img.naturalWidth,
          img.naturalHeight,
          maxDimension,
        );
        requestAnimationFrame(() => {
          if (!cancelled) setupSession(w, h, img);
        });
      };
      img.src = r.data_url;
    });

    return () => {
      cancelled = true;
      cancelScheduled();
    };
  }, [cancelScheduled, imagePath, maxDimension, setupSession]);

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

  const applyMaskImageData = useCallback(
    async (maskPath: string, publish = true) => {
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
      const target = ctx.createImageData(mask.width, mask.height);

      for (let i = 0; i < source.data.length; i += 4) {
        if (isMaskPixelSelected(source.data, i)) {
          target.data[i] = 255;
          target.data[i + 1] = 255;
          target.data[i + 2] = 255;
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

  useEffect(() => {
    const path = initialMaskPath?.trim();
    if (!ready || !path) return;
    const key = `${imagePath}:${path}`;
    if (restoredMaskKeyRef.current === key) return;
    restoredMaskKeyRef.current = key;
    let cancelled = false;
    void applyMaskImageData(path, false).catch(() => {
      if (!cancelled) restoredMaskKeyRef.current = null;
    });
    return () => {
      cancelled = true;
    };
  }, [applyMaskImageData, imagePath, initialMaskPath, ready]);

  const runSelection = useCallback(
    async (selection: "subject" | "background", tap?: { x: number; y: number }) => {
      if (!imagePath) return;
      const kind: InpaintSelectionKind =
        selection === "subject"
          ? tap
            ? "tap_object"
            : "subject"
          : tap
            ? "tap_background"
            : "background";
      setDetecting(true);
      try {
        const result = await generateInpaintSelectionMask({
          imagePath,
          selection: kind,
          tapX: tap?.x,
          tapY: tap?.y,
        });
        if (!result.ok || !result.mask_path) return;
        await applyMaskImageData(result.mask_path);
      } finally {
        setDetecting(false);
      }
    },
    [applyMaskImageData, imagePath],
  );

  const handlePointer = useCallback(
    (clientX: number, clientY: number) => {
      const coords = pointerToMaskCoords(clientX, clientY);
      if (!coords) return;
      if (tool === "subject" || tool === "background") {
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
  }, [publishMask, redrawView]);

  const cursorClass =
    tool === "subject" || tool === "background" ? "cursor-pointer" : "cursor-crosshair";

  return (
    <div className="relative flex max-h-full max-w-full flex-col items-center gap-3">
      <div
        className="relative overflow-hidden rounded-xl border border-dfui-border/50 shadow-glass"
        style={{ width: viewSize.w, height: viewSize.h, maxWidth: "100%", maxHeight: "100%" }}
      >
        <canvas
          ref={viewCanvasRef}
          className={`block max-h-full max-w-full touch-none ${cursorClass}`}
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
          <div className="absolute inset-0 flex items-center justify-center bg-dfui-bg/80 text-[11px] text-dfui-muted">
            Loading image…
          </div>
        )}
      </div>
      <CanvasToolRail
        tool={tool}
        onToolChange={setTool}
        brush={brush}
        onBrushChange={setBrush}
        onClear={clearMask}
        busy={busy}
        disabled={disabled}
      />
      {onOpenExpanded ? (
        <button
          type="button"
          onClick={onOpenExpanded}
          disabled={disabled || busy}
          className="text-[10px] text-dfui-tertiary transition hover:text-dfui-accent disabled:opacity-45"
        >
          More mask tools (full-screen)…
        </button>
      ) : null}
    </div>
  );
}
