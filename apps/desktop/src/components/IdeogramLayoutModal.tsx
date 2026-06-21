import { LayoutGrid, Plus, Trash2, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { GenerationSettings } from "../lib/tauri-api";
import {
  ideogramAspectLabel,
  layoutElementsFromCaption,
  layoutElementsToApi,
  normalizeHexPalette,
  parseIdeogramCaption,
  splitPaletteInput,
  uiRectToBbox,
  type IdeogramLayoutElement,
} from "../lib/ideogram4Ui";
import { buildIdeogram4CaptionFromLayout } from "../lib/studioBridge";

type Props = {
  open: boolean;
  settings: GenerationSettings;
  onClose: () => void;
  onApply: (caption: string) => void;
  presentation?: "modal" | "window";
};

const CANVAS_W = 480;
const CANVAS_H = 480;
const ART_MEDIUMS = new Set(["illustration", "3d_render", "painting", "graphic_design"]);

function newElement(index: number): IdeogramLayoutElement {
  const offset = (index % 4) * 0.08;
  return {
    id: `new-${Date.now()}-${index}`,
    type: "obj",
    x: 0.12 + offset,
    y: 0.12 + offset,
    w: 0.35,
    h: 0.28,
    desc: "",
    text: "",
    color_palette: [],
  };
}

function newTextElement(index: number): IdeogramLayoutElement {
  const el = newElement(index);
  return {
    ...el,
    type: "text",
    w: 0.42,
    h: 0.16,
    desc: "Readable text integrated into the composition",
  };
}

function styleText(record: Record<string, unknown> | null, key: string): string {
  const value = record?.[key];
  return typeof value === "string" ? value : "";
}

function stylePalette(record: Record<string, unknown> | null): string[] {
  const value = record?.color_palette;
  return Array.isArray(value) ? normalizeHexPalette(value.map(String), 16) : [];
}

export function IdeogramLayoutModal({ open, settings, onClose, onApply, presentation = "modal" }: Props) {
  const canvasRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<{
    id: string;
    mode: "move" | "resize";
    startX: number;
    startY: number;
    orig: IdeogramLayoutElement;
  } | null>(null);

  const [highLevel, setHighLevel] = useState("");
  const [background, setBackground] = useState("");
  const [styleDescription, setStyleDescription] = useState<Record<string, unknown> | null>(null);
  const [elements, setElements] = useState<IdeogramLayoutElement[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const aspectRatio = useMemo(() => ideogramAspectLabel(settings), [settings]);

  const canvasAspect = useMemo(() => {
    const [w, h] = aspectRatio.split(":").map((v) => Number(v) || 1);
    return w / h;
  }, [aspectRatio]);

  const viewSize = useMemo(() => {
    if (canvasAspect >= 1) {
      return { w: CANVAS_W, h: Math.round(CANVAS_W / canvasAspect) };
    }
    return { w: Math.round(CANVAS_H * canvasAspect), h: CANVAS_H };
  }, [canvasAspect]);

  useEffect(() => {
    if (!open) return;
    const caption = parseIdeogramCaption(settings.prompt ?? "");
    setHighLevel(caption?.high_level_description ?? settings.prompt ?? "");
    setBackground(caption?.compositional_deconstruction?.background ?? "");
    setStyleDescription(
      caption?.style_description && typeof caption.style_description === "object"
        ? (caption.style_description as Record<string, unknown>)
        : null,
    );
    const loaded = layoutElementsFromCaption(caption);
    setElements(loaded.length ? loaded : [newElement(0)]);
    setSelectedId(loaded[0]?.id ?? null);
    setError(null);
  }, [open, settings.prompt]);

  const selected = elements.find((el) => el.id === selectedId) ?? null;
  const selectedBbox = selected
    ? uiRectToBbox(selected.x, selected.y, selected.w, selected.h)
    : null;
  const styleMedium = styleText(styleDescription, "medium") || "photograph";
  const styleMode = ART_MEDIUMS.has(styleMedium) ? "art" : "photo";
  const canApply =
    Boolean(highLevel.trim()) &&
    Boolean(background.trim()) &&
    elements.every((el) =>
      el.type === "text"
        ? Boolean((el.text ?? "").trim() && (el.desc ?? "").trim())
        : Boolean((el.desc ?? "").trim()),
    );

  const updateElement = useCallback((id: string, patch: Partial<IdeogramLayoutElement>) => {
    setElements((prev) => prev.map((el) => (el.id === id ? { ...el, ...patch } : el)));
  }, []);

  const updateStyle = useCallback((patch: Record<string, unknown>) => {
    setStyleDescription((prev) => {
      const next = { ...(prev ?? {}), ...patch };
      Object.keys(next).forEach((key) => {
        const value = next[key];
        if (typeof value === "string" && !value.trim()) delete next[key];
        if (Array.isArray(value) && value.length === 0) delete next[key];
      });
      return Object.keys(next).length ? next : null;
    });
  }, []);

  const addElement = useCallback((type: "obj" | "text") => {
    const el = type === "text" ? newTextElement(elements.length) : newElement(elements.length);
    setElements((prev) => [...prev, el]);
    setSelectedId(el.id);
  }, [elements.length]);

  const onPointerDown = (
    e: React.PointerEvent,
    el: IdeogramLayoutElement,
    mode: "move" | "resize",
  ) => {
    e.stopPropagation();
    setSelectedId(el.id);
    dragRef.current = {
      id: el.id,
      mode,
      startX: e.clientX,
      startY: e.clientY,
      orig: { ...el },
    };
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
  };

  const onPointerMove = (e: React.PointerEvent) => {
    const drag = dragRef.current;
    if (!drag || !canvasRef.current) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const dx = (e.clientX - drag.startX) / rect.width;
    const dy = (e.clientY - drag.startY) / rect.height;
    const orig = drag.orig;
    if (drag.mode === "move") {
      updateElement(drag.id, {
        x: Math.max(0, Math.min(1 - orig.w, orig.x + dx)),
        y: Math.max(0, Math.min(1 - orig.h, orig.y + dy)),
      });
    } else {
      updateElement(drag.id, {
        w: Math.max(0.05, Math.min(1 - orig.x, orig.w + dx)),
        h: Math.max(0.05, Math.min(1 - orig.y, orig.h + dy)),
      });
    }
  };

  const onPointerUp = () => {
    dragRef.current = null;
  };

  const applyLayout = async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await buildIdeogram4CaptionFromLayout({
        aspect_ratio: aspectRatio,
        high_level_description: highLevel.trim(),
        background: background.trim(),
        elements: layoutElementsToApi(elements),
        style_description: styleDescription ?? undefined,
      });
      if (!res.ok || !res.normalized) {
        setError(res.errors?.join("; ") || "Could not build caption");
        return;
      }
      onApply(res.normalized);
      onClose();
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  };

  if (!open) return null;

  const isWindow = presentation === "window";

  return (
    <div
      className={
        isWindow
          ? "min-h-screen overflow-hidden bg-dfui-bg p-2 sm:p-4"
          : "fixed inset-0 z-50 overflow-y-auto bg-black/65 p-2 sm:p-4"
      }
    >
      <div
        className={
          isWindow
            ? "mx-auto flex h-[calc(100dvh-1rem)] min-h-0 w-full max-w-7xl flex-col overflow-hidden rounded-xl border border-dfui-border/60 bg-dfui-panel shadow-2xl sm:h-[calc(100dvh-2rem)]"
            : "mx-auto flex h-[calc(100dvh-1rem)] min-h-0 w-full max-w-5xl flex-col overflow-hidden rounded-xl border border-dfui-border/60 bg-dfui-panel shadow-2xl sm:h-[calc(100dvh-2rem)]"
        }
      >
        <div className="flex shrink-0 items-center gap-2 border-b border-dfui-border/50 px-3 py-2">
          <LayoutGrid size={16} className="text-dfui-accent" />
          <p className="text-sm font-medium text-dfui-fg">Ideogram layout builder</p>
          <p className="text-[10px] text-dfui-muted">Aspect {aspectRatio}</p>
          <button
            type="button"
            onClick={onClose}
            className="ml-auto rounded p-1 text-dfui-muted hover:bg-dfui-surface hover:text-dfui-fg"
            aria-label="Close"
          >
            <X size={16} />
          </button>
        </div>

        <div className="grid min-h-0 flex-1 grid-cols-1 gap-3 overflow-auto p-2 sm:p-3 md:grid-cols-[minmax(0,1fr)_360px] md:overflow-hidden">
          <div className="min-h-0 overflow-auto rounded-lg border border-dfui-border/25 bg-dfui-bg/15 p-2">
            <div className="flex min-w-fit flex-col items-center gap-2">
            <div
              ref={canvasRef}
              className="relative max-w-full shrink-0 overflow-hidden rounded-lg border border-dfui-border/50 bg-dfui-bg/40"
              style={{ width: viewSize.w, height: viewSize.h }}
              onPointerMove={onPointerMove}
              onPointerUp={onPointerUp}
              onPointerLeave={onPointerUp}
            >
              <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(45deg,rgba(255,255,255,0.03)_25%,transparent_25%,transparent_50%,rgba(255,255,255,0.03)_50%,rgba(255,255,255,0.03)_75%,transparent_75%,transparent)] bg-[length:16px_16px]" />
              {elements.map((el, index) => (
                <div
                  key={el.id}
                  role="presentation"
                  className={`absolute border-2 ${
                    selectedId === el.id
                      ? "border-dfui-accent bg-dfui-accent/10"
                      : "border-df-blue/70 bg-df-blue/5"
                  }`}
                  style={{
                    left: `${el.x * 100}%`,
                    top: `${el.y * 100}%`,
                    width: `${el.w * 100}%`,
                    height: `${el.h * 100}%`,
                  }}
                  onPointerDown={(e) => onPointerDown(e, el, "move")}
                >
                  <span className="pointer-events-none absolute left-0 top-0 bg-dfui-panel/90 px-1 text-[8px] text-dfui-fg">
                    {el.type === "text" ? "text" : "obj"} {index + 1}
                  </span>
                  <div
                    className="absolute bottom-0 right-0 h-3 w-3 cursor-se-resize bg-dfui-accent/80"
                    onPointerDown={(e) => onPointerDown(e, el, "resize")}
                  />
                </div>
              ))}
            </div>
            <div className="flex flex-wrap justify-center gap-2">
              <button
                type="button"
                className="inline-flex items-center gap-1 rounded border border-dfui-border/50 px-2 py-1 text-[10px] hover:border-dfui-accent/40"
                onClick={() => addElement("obj")}
              >
                <Plus size={12} />
                Object box
              </button>
              <button
                type="button"
                className="inline-flex items-center gap-1 rounded border border-dfui-border/50 px-2 py-1 text-[10px] hover:border-dfui-accent/40"
                onClick={() => addElement("text")}
              >
                <Plus size={12} />
                Text box
              </button>
            </div>
            <p className="text-[10px] text-dfui-muted">
              Bboxes use Ideogram coordinates [y1,x1,y2,x2] on a 0-1000 grid.
            </p>
            </div>
          </div>

          <div className="min-h-0 space-y-2 overflow-auto pr-1 text-xs">
            <label className="block">
              <span className="text-[10px] uppercase tracking-wide text-dfui-muted">Scene</span>
              <textarea
                value={highLevel}
                onChange={(e) => setHighLevel(e.target.value)}
                rows={2}
                className="df-input mt-1 w-full px-2 py-1.5 text-[11px]"
                placeholder="High-level description"
              />
            </label>
            <label className="block">
              <span className="text-[10px] uppercase tracking-wide text-dfui-muted">Background</span>
              <input
                value={background}
                onChange={(e) => setBackground(e.target.value)}
                className="df-input mt-1 w-full px-2 py-1.5 text-[11px]"
                placeholder="Scene shell / transparent background"
              />
            </label>

            <details className="rounded-lg border border-dfui-border/45 p-2" open>
              <summary className="cursor-pointer text-[10px] font-medium uppercase tracking-wide text-dfui-muted">
                Style and palette
              </summary>
              <div className="mt-2 grid grid-cols-2 gap-2">
                <label className="block">
                  <span className="text-[10px] text-dfui-muted">Medium</span>
                  <select
                    value={styleMedium}
                    onChange={(e) => {
                      const medium = e.target.value;
                      updateStyle(
                        ART_MEDIUMS.has(medium)
                          ? { medium, photo: "", art_style: styleText(styleDescription, "art_style") || "layout-aware visual style" }
                          : { medium, art_style: "", photo: styleText(styleDescription, "photo") || "natural photograph" },
                      );
                    }}
                    className="df-select mt-0.5 w-full px-2 py-1 text-[11px]"
                  >
                    <option value="photograph">Photograph</option>
                    <option value="graphic_design">Graphic design</option>
                    <option value="illustration">Illustration</option>
                    <option value="painting">Painting</option>
                    <option value="3d_render">3D render</option>
                  </select>
                </label>
                <label className="block">
                  <span className="text-[10px] text-dfui-muted">
                    {styleMode === "photo" ? "Photo" : "Art style"}
                  </span>
                  <input
                    value={styleMode === "photo" ? styleText(styleDescription, "photo") : styleText(styleDescription, "art_style")}
                    onChange={(e) =>
                      updateStyle(
                        styleMode === "photo"
                          ? { photo: e.target.value, art_style: "" }
                          : { art_style: e.target.value, photo: "" },
                      )
                    }
                    className="df-input mt-0.5 w-full px-2 py-1 text-[11px]"
                    placeholder={styleMode === "photo" ? "eye-level sports photograph" : "flat vector poster"}
                  />
                </label>
              </div>
              <label className="mt-2 block">
                <span className="text-[10px] text-dfui-muted">Aesthetics</span>
                <input
                  value={styleText(styleDescription, "aesthetics")}
                  onChange={(e) => updateStyle({ aesthetics: e.target.value })}
                  className="df-input mt-0.5 w-full px-2 py-1 text-[11px]"
                  placeholder="realistic, clean, energetic"
                />
              </label>
              <label className="mt-2 block">
                <span className="text-[10px] text-dfui-muted">Lighting</span>
                <input
                  value={styleText(styleDescription, "lighting")}
                  onChange={(e) => updateStyle({ lighting: e.target.value })}
                  className="df-input mt-0.5 w-full px-2 py-1 text-[11px]"
                  placeholder="neutral daylight, soft shadows"
                />
              </label>
              <label className="mt-2 block">
                <span className="text-[10px] text-dfui-muted">Palette (#RRGGBB, max 16)</span>
                <input
                  value={
                    Array.isArray(styleDescription?.color_palette)
                      ? (styleDescription.color_palette as string[]).join(", ")
                      : stylePalette(styleDescription).join(", ")
                  }
                  onChange={(e) => updateStyle({ color_palette: splitPaletteInput(e.target.value).slice(0, 16) })}
                  className="df-input mt-0.5 w-full px-2 py-1 font-mono text-[10px]"
                  placeholder="#E8C98A, #FFFFFF"
                />
              </label>
            </details>

            {selected ? (
              <div className="rounded-lg border border-dfui-border/45 p-2">
                <div className="mb-2 flex items-center justify-between">
                  <p className="text-[10px] font-medium text-dfui-fg">Selected element</p>
                  <button
                    type="button"
                    className="text-dfui-muted hover:text-red-300"
                    onClick={() => {
                      setElements((prev) => prev.filter((el) => el.id !== selected.id));
                      setSelectedId(null);
                    }}
                    aria-label="Delete element"
                  >
                    <Trash2 size={12} />
                  </button>
                </div>
                <label className="block">
                  <span className="text-[10px] text-dfui-muted">Type</span>
                  <select
                    value={selected.type}
                    onChange={(e) =>
                      updateElement(selected.id, {
                        type: e.target.value as "obj" | "text",
                      })
                    }
                    className="df-select mt-0.5 w-full px-2 py-1 text-[11px]"
                  >
                    <option value="obj">Object</option>
                    <option value="text">Text</option>
                  </select>
                </label>
                {selectedBbox ? (
                  <div className="mt-2 rounded border border-dfui-border/35 bg-dfui-bg/35 px-2 py-1 font-mono text-[10px] text-dfui-muted">
                    bbox [{selectedBbox.join(", ")}]
                  </div>
                ) : null}
                <div className="mt-2 grid grid-cols-4 gap-1">
                  {(["x", "y", "w", "h"] as const).map((key) => (
                    <label key={key} className="block">
                      <span className="text-[10px] text-dfui-muted">{key.toUpperCase()}</span>
                      <input
                        type="number"
                        min={0}
                        max={100}
                        step={1}
                        value={Math.round(selected[key] * 100)}
                        onChange={(e) => {
                          const value = Math.max(0, Math.min(100, Number(e.target.value) || 0)) / 100;
                          const patch: Partial<IdeogramLayoutElement> = { [key]: value };
                          if (key === "x") patch.x = Math.min(value, 1 - selected.w);
                          if (key === "y") patch.y = Math.min(value, 1 - selected.h);
                          if (key === "w") patch.w = Math.max(0.05, Math.min(value, 1 - selected.x));
                          if (key === "h") patch.h = Math.max(0.05, Math.min(value, 1 - selected.y));
                          updateElement(selected.id, patch);
                        }}
                        className="df-input mt-0.5 w-full px-1 py-1 text-[10px]"
                      />
                    </label>
                  ))}
                </div>
                {selected.type === "text" ? (
                  <label className="mt-2 block">
                    <span className="text-[10px] text-dfui-muted">Literal text</span>
                    <input
                      value={selected.text ?? ""}
                      onChange={(e) => updateElement(selected.id, { text: e.target.value })}
                      className="df-input mt-0.5 w-full px-2 py-1 text-[11px]"
                    />
                  </label>
                ) : null}
                <label className="mt-2 block">
                  <span className="text-[10px] text-dfui-muted">Description</span>
                  <textarea
                    value={selected.desc ?? ""}
                    onChange={(e) => updateElement(selected.id, { desc: e.target.value })}
                    rows={2}
                    className="df-input mt-0.5 w-full px-2 py-1 text-[11px]"
                  />
                </label>
                <label className="mt-2 block">
                  <span className="text-[10px] text-dfui-muted">Colors (#RRGGBB, comma-separated)</span>
                  <input
                    value={(selected.color_palette ?? []).join(", ")}
                    onChange={(e) =>
                      updateElement(selected.id, {
                        color_palette: splitPaletteInput(e.target.value).slice(0, 5),
                      })
                    }
                    className="df-input mt-0.5 w-full px-2 py-1 font-mono text-[10px]"
                    placeholder="#FF0000, #00AAFF"
                  />
                </label>
              </div>
            ) : (
              <p className="text-[10px] text-dfui-muted">Select a box on the canvas to edit.</p>
            )}
          </div>
        </div>

        {error ? <p className="shrink-0 px-3 pb-1 text-[10px] text-red-300">{error}</p> : null}

        <div className="flex shrink-0 justify-end gap-2 border-t border-dfui-border/50 px-3 py-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded border border-dfui-border/50 px-3 py-1.5 text-xs text-dfui-muted"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={busy || !canApply}
            onClick={() => void applyLayout()}
            className="rounded border border-dfui-accent/50 bg-dfui-accent/15 px-3 py-1.5 text-xs font-medium text-dfui-accent disabled:opacity-50"
          >
            {busy ? "Building…" : "Apply to prompt"}
          </button>
        </div>
      </div>
    </div>
  );
}
