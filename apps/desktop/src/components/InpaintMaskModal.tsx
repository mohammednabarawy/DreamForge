import {
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

export function InpaintMaskModal({ imagePath, open, onClose, onSave }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [size, setSize] = useState({ w: 512, h: 512 });
  const [brush, setBrush] = useState(24);
  const [tool, setTool] = useState<SelectTool>("paint");
  const [mergeMode, setMergeMode] = useState<"add" | "replace">("add");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");
  const drawing = useRef(false);

  useEffect(() => {
    if (!open || !imagePath) return;
    let cancelled = false;
    setStatus("");
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
      ctx.globalCompositeOperation = tool === "erase" ? "destination-out" : "source-over";
      ctx.fillStyle = "#fff";
      ctx.beginPath();
      ctx.arc(x, y, brush, 0, Math.PI * 2);
      ctx.fill();
    },
    [brush, tool],
  );

  const clearMask = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.globalCompositeOperation = "source-over";
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    setStatus("Mask cleared");
  };

  const applyMaskImageData = useCallback(
    async (maskPath: string, mode: "add" | "replace") => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      const preview = await readImagePreviewQueued(maskPath);
      const img = new Image();
      await new Promise<void>((resolve, reject) => {
        img.onload = () => resolve();
        img.onerror = () => reject(new Error("mask_preview_failed"));
        img.src = preview.data_url;
      });
      const temp = document.createElement("canvas");
      temp.width = canvas.width;
      temp.height = canvas.height;
      const tctx = temp.getContext("2d");
      if (!tctx) return;
      tctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      const source = tctx.getImageData(0, 0, canvas.width, canvas.height);
      const target =
        mode === "replace"
          ? ctx.createImageData(canvas.width, canvas.height)
          : ctx.getImageData(0, 0, canvas.width, canvas.height);
      for (let i = 0; i < source.data.length; i += 4) {
        const bright = source.data[i] > 127;
        if (bright) {
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
    },
    [],
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

  const handleCanvasPointer = useCallback(
    (clientX: number, clientY: number) => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const rect = canvas.getBoundingClientRect();
      const x = ((clientX - rect.left) / rect.width) * canvas.width;
      const y = ((clientY - rect.top) / rect.height) * canvas.height;
      if (tool === "tap_object" || tool === "tap_background") {
        void runSelection(tool, {
          x: x / canvas.width,
          y: y / canvas.height,
        });
        return;
      }
      paint(clientX, clientY);
    },
    [paint, runSelection, tool],
  );

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
      <div className="flex max-h-[92vh] w-full max-w-3xl flex-col rounded-xl border border-dfui-border/60 bg-dfui-panel shadow-2xl">
        <div className="flex items-center justify-between border-b border-dfui-border/40 px-3 py-2">
          <div>
            <span className="text-sm font-medium text-dfui-fg">Inpaint mask</span>
            <p className="text-[10px] text-dfui-tertiary">
              Smart select like Gallery Object Eraser, then refine with brush
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
              disabled={busy}
              onClick={() => void runSelection(id)}
              className="flex items-center gap-1 rounded border border-dfui-border/50 px-2 py-1 text-[10px] text-dfui-secondary hover:border-dfui-accent/40 hover:text-dfui-accent disabled:opacity-50"
            >
              {Icon ? <Icon size={11} /> : <Sparkles size={11} />}
              {label}
            </button>
          ))}
        </div>

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
            className={`relative z-10 max-w-full touch-none ${
              tool === "tap_object" || tool === "tap_background"
                ? "cursor-pointer"
                : "cursor-crosshair"
            }`}
            style={{ width: size.w, height: size.h }}
            onPointerDown={(e) => {
              if (busy) return;
              drawing.current = tool === "paint" || tool === "erase";
              (e.target as HTMLCanvasElement).setPointerCapture(e.pointerId);
              handleCanvasPointer(e.clientX, e.clientY);
            }}
            onPointerMove={(e) => {
              if (!drawing.current || busy) return;
              if (tool !== "paint" && tool !== "erase") return;
              paint(e.clientX, e.clientY);
            }}
            onPointerUp={() => {
              drawing.current = false;
            }}
          />
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
              <option value="add">Add to mask</option>
              <option value="replace">Replace mask</option>
            </select>
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
              disabled={busy}
              onClick={() => void exportMask()}
              className="rounded-lg bg-dfui-accent px-3 py-1.5 text-xs font-medium text-dfui-bg hover:opacity-90 disabled:opacity-50"
            >
              Apply mask
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
