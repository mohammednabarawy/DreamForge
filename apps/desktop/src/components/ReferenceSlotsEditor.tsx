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
import type { StudioMode } from "../lib/model-selection";

type Props = {
  settings: GenerationSettings;
  studioMode?: StudioMode;
  disabled?: boolean;
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

export function ReferenceSlotsEditor({
  settings,
  studioMode = "generate",
  disabled = false,
  onAddSlot,
  onUpdateSlot,
  onRemoveSlot,
}: Props) {
  const slots = coerceReferenceSlots(settings, studioMode);
  const extraSlots = slots.slice(1);
  const canAdd = slots.length < MAX_REFERENCE_SLOTS;

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
          Extra slots ({slots.length}/{MAX_REFERENCE_SLOTS})
        </p>
        {canAdd ? (
          <button
            type="button"
            disabled={disabled}
            onClick={() => void chooseExtraSlot("image_prompt")}
            className="inline-flex items-center gap-1 rounded border border-dashed border-dfui-border/70 px-1.5 py-0.5 text-[9px] text-df-blue hover:border-df-blue/50 disabled:opacity-50"
          >
            <ImagePlus size={10} />
            Add slot
          </button>
        ) : null}
      </div>

      <div className="space-y-2">
        {extraSlots.map((slot, offset) => {
          const index = offset + 1;
          return (
            <div
              key={`${slot.path}-${index}`}
              className="rounded-md border border-dfui-border/50 bg-dfui-bg/40 p-1.5"
            >
              <div className="flex gap-2">
                <div className="h-10 w-10 shrink-0 overflow-hidden rounded border border-dfui-border/50 bg-dfui-bg">
                  <SlotPreview path={slot.path} />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-start justify-between gap-1">
                    <p className="truncate font-mono text-[9px] text-dfui-fg" title={slot.path}>
                      {basename(slot.path)}
                    </p>
                    <button
                      type="button"
                      disabled={disabled}
                      onClick={() => onRemoveSlot(index)}
                      className="shrink-0 rounded p-0.5 text-dfui-muted hover:text-red-300 disabled:opacity-50"
                      title="Remove slot"
                    >
                      <X size={11} />
                    </button>
                  </div>
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
                </div>
              </div>
              {slotSupportsWeightControls(slot.role) ? (
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
              {slotSupportsStopAt(slot.role) ? (
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
          Add image-prompt or structure slots to combine style + composition (SDXL + IP-Adapter).
        </p>
      ) : null}
    </div>
  );
}
