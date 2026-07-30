import { useEffect, useState } from "react";
import { ImagePlus, X } from "lucide-react";
import { readImagePreviewQueued } from "../lib/preview-queue";
import { basename } from "../lib/referenceImage";
import { PRO_GENERATE_REFERENCE_ROLES } from "../lib/referenceRole";
import type { ReferenceRole } from "../lib/referenceRole";
import type { GenerationSettings } from "../lib/tauri-api";
import {
  coerceReferenceSlots,
  DEFAULT_SLOT_STOP_AT,
  DEFAULT_SLOT_WEIGHT,
  MAX_REFERENCE_SLOTS,
  slotSupportsStopAt,
  slotSupportsWeightControls,
  type ReferenceSlot,
} from "../lib/referenceSlots";
import { pickImageFile } from "../lib/tauri-api";
import { analyzeIdentityFaces, type IdentityFaceAnalysis } from "../lib/studioBridge";
import type { StudioMode } from "../lib/model-selection";

type Props = {
  settings: GenerationSettings;
  studioMode?: StudioMode;
  disabled?: boolean;
  showRoles?: boolean;
  maxSlots?: number;
  onAddSlot: (slot: ReferenceSlot) => void;
  onUpdateSlot: (index: number, patch: Partial<ReferenceSlot>) => void;
  onRemoveSlot: (index: number) => void;
};

function SlotPreview({ path }: { path: string }) {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    let cancelled = false;
    void readImagePreviewQueued(path)
      .then((result) => {
        if (!cancelled) setUrl(result.data_url);
      })
      .catch(() => {
        if (!cancelled) setUrl(null);
      });
    return () => {
      cancelled = true;
    };
  }, [path]);
  if (!url) {
    return (
      <span className="flex h-full w-full items-center justify-center text-[8px] text-dfui-muted">
        IMG
      </span>
    );
  }
  return <img src={url} alt="" className="h-full w-full object-cover" />;
}

export function IdentitySlotControls({
  slot,
  disabled = false,
  onUpdate,
}: {
  slot: ReferenceSlot;
  disabled?: boolean;
  onUpdate: (patch: Partial<ReferenceSlot>) => void;
}) {
  const [analysis, setAnalysis] = useState<IdentityFaceAnalysis | null>(null);
  useEffect(() => {
    if (!slot.character_id) {
      setAnalysis(null);
      return;
    }
    let cancelled = false;
    void analyzeIdentityFaces(slot.path)
      .then((result) => {
        if (!cancelled) setAnalysis(result);
      })
      .catch(() => {
        if (!cancelled) setAnalysis(null);
      });
    return () => {
      cancelled = true;
    };
  }, [slot.character_id, slot.path]);

  return (
    <div className="mt-1.5 grid grid-cols-2 gap-1">
      <label className="text-[8px] text-dfui-muted">
        Character
        <select
          disabled={disabled}
          value={slot.character_id ?? ""}
          onChange={(event) =>
            onUpdate({
              character_id: event.target.value || undefined,
              character_region: event.target.value ? slot.character_region ?? "auto" : undefined,
              face_index: event.target.value ? slot.face_index : undefined,
            })
          }
          className="mt-0.5 w-full rounded border border-dfui-border/50 bg-dfui-bg px-1 py-0.5 text-[9px] text-dfui-fg"
        >
          <option value="">Not a character</option>
          {(["a", "b", "c", "d"] as const).map((id) => (
            <option key={id} value={`character_${id}`}>
              Character {id.toUpperCase()}
            </option>
          ))}
        </select>
      </label>
      <label className="text-[8px] text-dfui-muted">
        Position
        <select
          disabled={disabled || !slot.character_id}
          value={slot.character_region ?? "auto"}
          onChange={(event) =>
            onUpdate({
              character_region: event.target.value as ReferenceSlot["character_region"],
            })
          }
          className="mt-0.5 w-full rounded border border-dfui-border/50 bg-dfui-bg px-1 py-0.5 text-[9px] text-dfui-fg disabled:opacity-50"
        >
          <option value="auto">Auto</option>
          <option value="left">Left</option>
          <option value="center">Center</option>
          <option value="right">Right</option>
        </select>
      </label>
      {slot.character_id && analysis?.ok && analysis.count > 1 ? (
        <label className="col-span-2 text-[8px] text-dfui-muted">
          Face in this image
          <select
            disabled={disabled}
            value={slot.face_index ?? ""}
            onChange={(event) =>
              onUpdate({
                face_index: event.target.value === "" ? undefined : Number(event.target.value),
              })
            }
            className="mt-0.5 w-full rounded border border-dfui-border/50 bg-dfui-bg px-1 py-0.5 text-[9px] text-dfui-fg"
          >
            <option value="">Auto (largest face)</option>
            {analysis.faces.map((face) => (
              <option key={face.index} value={face.index}>
                Face {face.index + 1}{face.recommended ? " — recommended" : ""}
              </option>
            ))}
          </select>
        </label>
      ) : null}
      {slot.character_id && analysis?.ok && analysis.count === 0 ? (
        <p className="col-span-2 text-[8px] text-amber-300">No clear face detected; the full image will be used.</p>
      ) : null}
    </div>
  );
}

export function ReferenceSlotsEditor({
  settings,
  studioMode = "generate",
  disabled = false,
  showRoles = false,
  maxSlots = MAX_REFERENCE_SLOTS,
  onAddSlot,
  onUpdateSlot,
  onRemoveSlot,
}: Props) {
  const slots = coerceReferenceSlots(settings, studioMode, maxSlots);
  const extraSlots = slots.slice(1);
  const canAdd = slots.length < maxSlots;

  const chooseExtraSlot = async (role: ReferenceRole = "image_prompt") => {
    try {
      const path = await pickImageFile();
      if (!path) return;
      onAddSlot({
        path,
        role,
        weight: DEFAULT_SLOT_WEIGHT,
        stop_at: DEFAULT_SLOT_STOP_AT,
        structure_type: role === "structure" ? "canny" : undefined,
      });
    } catch {
      /* picker unavailable */
    }
  };

  if (!extraSlots.length && !canAdd) return null;

  return (
    <div className="border-t border-dfui-border/40 px-2.5 py-2">
      <div className="mb-1.5 flex items-center justify-between gap-2">
        <p className="text-[9px] font-semibold uppercase tracking-wide text-dfui-muted">
          Reference images ({slots.length}/{maxSlots})
        </p>
        {canAdd ? (
          <button
            type="button"
            disabled={disabled}
            onClick={() => void chooseExtraSlot("image_prompt")}
            className="inline-flex items-center gap-1 rounded border border-dashed border-dfui-border/70 px-1.5 py-0.5 text-[9px] text-df-blue hover:border-df-blue/50 disabled:opacity-50"
          >
            <ImagePlus size={10} />
            Add image
          </button>
        ) : null}
      </div>


      <div className="space-y-2">
        {extraSlots.map((slot, offset) => {
          const index = offset + 1;
          const prompt = (settings.prompt ?? "").toLowerCase();
          const isMentioned = prompt.includes(`image ${index + 1}`);
          return (
            <div
              key={`${slot.path}-${index}`}
              className="rounded-md border border-dfui-border/50 bg-dfui-bg/40 p-1.5"
            >
              <div className="flex gap-2">
                <div className={`relative h-10 w-10 shrink-0 overflow-hidden rounded border transition-all bg-dfui-bg ${
                  isMentioned
                    ? "border-df-blue ring-1 ring-df-blue"
                    : "border-dfui-border/50"
                }`}>
                  <SlotPreview path={slot.path} />
                  <span className="absolute left-0 top-0 rounded-br bg-df-blue/80 px-1 text-[8px] font-bold text-white">
                    {index + 1}
                  </span>
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-start justify-between gap-1">
                    <div className="min-w-0">
                      <p className="text-[9px] font-semibold text-df-blue/90">
                        Image {index + 1}
                      </p>
                      <p className="truncate font-mono text-[9px] text-dfui-muted" title={slot.path}>
                        {basename(slot.path)}
                      </p>
                    </div>
                    <button
                      type="button"
                      disabled={disabled}
                      onClick={() => onRemoveSlot(index)}
                      className="shrink-0 rounded p-0.5 text-dfui-muted hover:text-red-300 disabled:opacity-50"
                      title="Remove image"
                    >
                      <X size={11} />
                    </button>
                  </div>
                  {showRoles ? (
                    <div className="mt-1 flex flex-wrap gap-0.5">
                      {PRO_GENERATE_REFERENCE_ROLES.map((item) => {
                        const active = slot.role === item.id;
                        return (
                          <button
                            key={item.id}
                            type="button"
                            disabled={disabled}
                            title={item.label}
                            onClick={() =>
                              onUpdateSlot(index, {
                                role: item.id,
                                structure_type: item.id === "structure" ? "canny" : undefined,
                              })
                            }
                            className={`rounded px-1 py-0.5 text-[8px] font-medium ${
                              active
                                ? "bg-df-blue/20 text-df-blue"
                                : "text-dfui-muted hover:bg-dfui-surface-hover"
                            }`}
                          >
                            {item.short}
                          </button>
                        );
                      })}
                    </div>
                  ) : null}
                </div>
              </div>
              {showRoles ? (
                <IdentitySlotControls
                  slot={slot}
                  disabled={disabled}
                  onUpdate={(patch) => onUpdateSlot(index, patch)}
                />
              ) : null}
              {showRoles && slotSupportsWeightControls(slot.role) ? (
                <label className="mt-1.5 flex items-center gap-2 text-[8px] text-dfui-muted">
                  <span className="w-10">Weight</span>
                  <input
                    type="range"
                    min={0}
                    max={2}
                    step={0.05}
                    disabled={disabled}
                    value={slot.weight ?? DEFAULT_SLOT_WEIGHT}
                    onChange={(e) =>
                      onUpdateSlot(index, { weight: Number(e.target.value) })
                    }
                    className="h-1 min-w-0 flex-1 accent-df-blue"
                  />
                  <span className="w-8 text-right font-mono">
                    {(slot.weight ?? DEFAULT_SLOT_WEIGHT).toFixed(2)}
                  </span>
                </label>
              ) : null}
              {showRoles && slotSupportsStopAt(slot.role) ? (
                <label className="mt-1 flex items-center gap-2 text-[8px] text-dfui-muted">
                  <span className="w-10">Stop at</span>
                  <input
                    type="range"
                    min={0}
                    max={1}
                    step={0.05}
                    disabled={disabled}
                    value={slot.stop_at ?? DEFAULT_SLOT_STOP_AT}
                    onChange={(e) =>
                      onUpdateSlot(index, { stop_at: Number(e.target.value) })
                    }
                    className="h-1 min-w-0 flex-1 accent-df-blue"
                  />
                  <span className="w-8 text-right font-mono">
                    {Math.round((slot.stop_at ?? DEFAULT_SLOT_STOP_AT) * 100)}%
                  </span>
                </label>
              ) : null}
            </div>
          );
        })}
      </div>

      {slots.length === 1 && canAdd ? (
        <p className="mt-1 text-[8px] leading-snug text-dfui-tertiary">
          Add more images to compose them together — the prompt decides how
          (keep a face, swap an outfit, merge a scene). Up to {maxSlots}.
        </p>
      ) : null}
    </div>
  );
}
