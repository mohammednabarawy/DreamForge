import { useEffect, useMemo, useState } from "react";
import type { CustomTool } from "../lib/customTools";
import {
  WORKFLOW_MODEL_DEFAULT,
  type CustomToolWorkflowModelSlot,
  type WorkflowModelLibraryOption,
  galleryModelFilename,
  galleryModelsForWorkflowSlot,
  workflowModelSlotLabel,
} from "../lib/customToolModels";
import { fetchCustomToolWorkflowModels } from "../lib/studioBridge";
import type { ModelGalleryItem } from "../lib/tauri-api";

type Props = {
  tool: CustomTool;
  modelGallery?: ModelGalleryItem[];
  onChangeOverrides: (toolId: string, overrides: Record<string, string>) => void;
};

function slotLibraryOptions(
  slot: CustomToolWorkflowModelSlot,
  modelGallery: ModelGalleryItem[],
): WorkflowModelLibraryOption[] {
  if (slot.library_options?.length) {
    return slot.library_options;
  }
  return galleryModelsForWorkflowSlot(slot, modelGallery).map((item) => ({
    category: item.category,
    relative_path: item.relative_path,
    filename: galleryModelFilename(item),
    caption: item.caption || galleryModelFilename(item),
  }));
}

function optionsWithSelection(
  options: WorkflowModelLibraryOption[],
  selected: string,
): WorkflowModelLibraryOption[] {
  if (
    selected === WORKFLOW_MODEL_DEFAULT ||
    options.some((item) => item.filename === selected)
  ) {
    return options;
  }
  return [
    {
      category: "",
      relative_path: selected,
      filename: selected,
      caption: selected,
    },
    ...options,
  ];
}

export function CustomToolModelOverrides({
  tool,
  modelGallery = [],
  onChangeOverrides,
}: Props) {
  const [slots, setSlots] = useState<CustomToolWorkflowModelSlot[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setBusy(true);
    setError(null);
    void (async () => {
      try {
        const payload = await fetchCustomToolWorkflowModels(tool.id);
        if (cancelled) return;
        setSlots((payload.models ?? []) as CustomToolWorkflowModelSlot[]);
      } catch (e) {
        if (!cancelled) {
          setSlots([]);
          setError(String(e));
        }
      } finally {
        if (!cancelled) setBusy(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [tool.id, tool.workflow_path, JSON.stringify(tool.model_overrides ?? {})]);

  const overrides = tool.model_overrides ?? {};

  const slotOptions = useMemo(() => {
    const map = new Map<string, WorkflowModelLibraryOption[]>();
    for (const slot of slots) {
      const selected = overrides[slot.ref_key] ?? WORKFLOW_MODEL_DEFAULT;
      map.set(
        slot.ref_key,
        optionsWithSelection(slotLibraryOptions(slot, modelGallery), selected),
      );
    }
    return map;
  }, [slots, modelGallery, overrides]);

  if (busy && slots.length === 0) {
    return <p className="text-[10px] text-[#aaaaaa]">Loading workflow models…</p>;
  }

  if (error) {
    return <p className="text-[10px] text-[#f48771]">{error}</p>;
  }

  if (slots.length === 0) {
    return null;
  }

  const setSelection = (refKey: string, value: string) => {
    const next = { ...overrides };
    if (!value || value === WORKFLOW_MODEL_DEFAULT) {
      delete next[refKey];
    } else {
      next[refKey] = value;
    }
    onChangeOverrides(tool.id, next);
  };

  return (
    <div className="mt-3 space-y-2 rounded border border-[#4a4a4a]/70 bg-[#2a2a2a]/50 p-2">
      <p className="text-[10px] font-medium text-[#aaaaaa]">Workflow models</p>
      <p className="text-[9px] leading-snug text-[#777777]">
        Map each loader to a file from your library, or keep Download to fetch the workflow&apos;s
        default weight.
      </p>
      {slots.map((slot) => {
        const options = slotOptions.get(slot.ref_key) ?? [];
        const selected = overrides[slot.ref_key] ?? WORKFLOW_MODEL_DEFAULT;
        return (
          <label key={slot.ref_key} className="block space-y-1">
            <span className="text-[9px] text-[#aaaaaa]">{workflowModelSlotLabel(slot)}</span>
            <select
              value={selected}
              onChange={(e) => setSelection(slot.ref_key, e.target.value)}
              className="w-full rounded border border-[#4a4a4a] bg-[#1e1e1e] px-2 py-1 text-[10px] text-[#cccccc]"
            >
              <option value={WORKFLOW_MODEL_DEFAULT}>
                Download: {slot.workflow_filename}
              </option>
              {options.map((item) => (
                <option
                  key={`${item.category}:${item.relative_path}:${item.filename}`}
                  value={item.filename}
                >
                  {item.caption || item.filename}
                </option>
              ))}
            </select>
          </label>
        );
      })}
    </div>
  );
}
