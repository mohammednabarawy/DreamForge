import { Eraser, Paintbrush, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { readImagePreviewQueued } from "../lib/preview-queue";
import { writeTempPng } from "../lib/studioBridge";

type Props = {
  imagePath: string;
  open: boolean;
  onClose: () => void;
  onSave: (maskPath: string) => void;
};

export function InpaintMaskModal({ imagePath, open, onClose, onSave }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [size, setSize] = useState({ w: 512, h: 512 });
  const [brush, setBrush] = useState(24);
  const [eraser, setEraser] = useState(false);
  const drawing = useRef(false);

  useEffect(() => {
    if (!open || !imagePath) return;
    let cancelled = false;
    void readImagePreviewQueued(imagePath).then((r) => {
      if (cancelled) return;
      setPreviewUrl(r.data_url);
      const img = new Image();
      img.onload = () => {
        const max = 768;
        let w = img.naturalWidth;
        let h = img.naturalHeight;
        const scale = Math.min(1, max / Math.max(w, h));
        w = Math.round(w * scale);
        h = Math.round(h * scale);
        setSize({ w, h });
        const canvas = canvasRef.current;
        if (!canvas) return;
        canvas.width = w;
        canvas.height = h;
        const ctx = canvas.getContext("2d");
        if (!ctx) return;
        ctx.fillStyle = "#000";
        ctx.fillRect(0, 0, w, h);
      };
      img.src = r.data_url;
    });
    return () => {
      cancelled = true;
    };
  }, [open, imagePath]);

  const paint = useCallback(
    (clientX: number, clientY: number) => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const rect = canvas.getBoundingClientRect();
      const x = ((clientX - rect.left) / rect.width) * canvas.width;
      const y = ((clientY - rect.top) / rect.height) * canvas.height;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      ctx.globalCompositeOperation = eraser ? "destination-out" : "source-over";
      ctx.fillStyle = "#fff";
      ctx.beginPath();
      ctx.arc(x, y, brush, 0, Math.PI * 2);
      ctx.fill();
    },
    [brush, eraser],
  );

  const clearMask = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.globalCompositeOperation = "source-over";
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
  };

  const exportMask = async () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const dataUrl = canvas.toDataURL("image/png");
    const path = await writeTempPng(dataUrl);
    onSave(path);
    onClose();
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
      <div className="flex max-h-[90vh] w-full max-w-2xl flex-col rounded-xl border border-dfui-border/60 bg-dfui-panel shadow-2xl">
        <div className="flex items-center justify-between border-b border-dfui-border/40 px-3 py-2">
          <span className="text-sm font-medium text-dfui-fg">Inpaint mask</span>
          <button type="button" onClick={onClose} className="text-dfui-muted hover:text-dfui-fg">
            <X size={18} />
          </button>
        </div>
        <p className="px-3 py-1.5 text-[10px] text-dfui-tertiary">
          Paint white where you want the model to change. Black stays untouched.
        </p>
        <div className="relative mx-auto overflow-hidden rounded-lg border border-dfui-border/50">
          {previewUrl && (
            <img
              src={previewUrl}
              alt=""
              className="pointer-events-none absolute inset-0 h-full w-full object-contain opacity-40"
              style={{ width: size.w, height: size.h }}
            />
          )}
          <canvas
            ref={canvasRef}
            width={size.w}
            height={size.h}
            className="relative z-10 max-w-full cursor-crosshair touch-none"
            style={{ width: size.w, height: size.h }}
            onPointerDown={(e) => {
              drawing.current = true;
              (e.target as HTMLCanvasElement).setPointerCapture(e.pointerId);
              paint(e.clientX, e.clientY);
            }}
            onPointerMove={(e) => {
              if (!drawing.current) return;
              paint(e.clientX, e.clientY);
            }}
            onPointerUp={() => {
              drawing.current = false;
            }}
          />
        </div>
        <div className="flex flex-wrap items-center gap-3 border-t border-dfui-border/40 px-3 py-2">
          <label className="flex items-center gap-2 text-[10px] text-dfui-muted">
            Brush
            <input
              type="range"
              min={4}
              max={96}
              value={brush}
              onChange={(e) => setBrush(Number(e.target.value))}
              className="w-24 accent-dfui-accent"
            />
          </label>
          <button
            type="button"
            onClick={() => setEraser(false)}
            className={`flex items-center gap-1 rounded px-2 py-1 text-[10px] ${
              !eraser ? "bg-dfui-accent/20 text-dfui-accent" : "text-dfui-muted"
            }`}
          >
            <Paintbrush size={12} /> Paint
          </button>
          <button
            type="button"
            onClick={() => setEraser(true)}
            className={`flex items-center gap-1 rounded px-2 py-1 text-[10px] ${
              eraser ? "bg-dfui-accent/20 text-dfui-accent" : "text-dfui-muted"
            }`}
          >
            <Eraser size={12} /> Erase
          </button>
          <button
            type="button"
            onClick={clearMask}
            className="text-[10px] text-dfui-tertiary hover:text-dfui-fg"
          >
            Clear mask
          </button>
          <div className="flex-1" />
          <button
            type="button"
            onClick={() => void exportMask()}
            className="rounded-lg bg-dfui-accent px-3 py-1.5 text-xs font-medium text-dfui-bg hover:opacity-90"
          >
            Apply mask
          </button>
        </div>
      </div>
    </div>
  );
}
