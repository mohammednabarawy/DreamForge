import { useEffect, useState } from "react";
import type { GenerationSettings, ModelDependencyItem, ModelGalleryItem } from "../lib/tauri-api";
import { CustomToolImportModal } from "./CustomToolImportModal";
import type { CustomTool } from "../lib/customTools";
import { resolveCustomTool, upsertCustomTool } from "../lib/customTools";
import { useDreamForge } from "../hooks/useDreamForge";
import { EDIT_TASKS, type EditTask, patchForEditTask } from "../lib/inpaintIntent";
import { defaultPromptPatchForEditTask } from "../lib/editTaskPrompts";
import { selectInpaintModelForIntent } from "../lib/inpaintIntent";
import { buildPortraitMasterPrompt, PORTRAIT_EXPRESSIONS, PORTRAIT_LIGHTING, PORTRAIT_SHOTS } from "../lib/portraitMaster";
import { fetchCustomToolDependencies } from "../lib/studioBridge";
import { CustomToolModelOverrides } from "./CustomToolModelOverrides";

type Props = {
  settings: GenerationSettings;
  onChange: (patch: Partial<GenerationSettings>) => void;
  modelGallery?: ModelGalleryItem[];
  onInstallCompanionItems?: (items: ModelDependencyItem[]) => void;
};

export function CreativeToolboxPanel({
  settings,
  onChange,
  modelGallery = [],
  onInstallCompanionItems,
}: Props) {
  const { appConfig, saveAppConfig } = useDreamForge();

  const [isImportModalOpen, setIsImportModalOpen] = useState(false);
  const [customToolMissing, setCustomToolMissing] = useState<ModelDependencyItem[]>([]);
  const [customToolDepsReady, setCustomToolDepsReady] = useState<boolean | null>(null);
  const [customToolDepsBusy, setCustomToolDepsBusy] = useState(false);
  const activeTask = settings.edit_task;
  const activeCustomToolId = settings.custom_tool_id;
  const nativeTasks = EDIT_TASKS.filter((item) => item.toolboxOnly);
  const customTools = appConfig?.custom_tools || [];
  const activeTool = resolveCustomTool(customTools, activeCustomToolId);

  const persistCustomToolSelection = async (toolId: string | undefined) => {
    await saveAppConfig({
      ui: {
        selected_custom_tool_id: toolId,
      },
    });
  };

  const handleSaveCustomTool = async (tool: CustomTool) => {
    const nextTools = upsertCustomTool(customTools, tool);
    const savedTool = resolveCustomTool(nextTools, tool.id) ?? tool;
    await saveAppConfig({
      custom_tools: nextTools,
      ...(appConfig?.ui?.studio_mode !== "toolbox"
        ? { ui: { studio_mode: "toolbox", selected_custom_tool_id: savedTool.id } }
        : { ui: { selected_custom_tool_id: savedTool.id } }),
    });
    onChange({
      custom_tool_id: savedTool.id,
      edit_task: undefined,
      inpaint_intent: undefined,
    });
    setIsImportModalOpen(false);
  };

  const handleRemoveCustomTool = async (toolId: string) => {
    const nextTools = customTools.filter((tool) => tool.id !== toolId);
    await saveAppConfig({
      custom_tools: nextTools,
      ui: {
        selected_custom_tool_id:
          activeCustomToolId === toolId ? undefined : appConfig?.ui?.selected_custom_tool_id,
      },
    });
    if (activeCustomToolId === toolId) {
      onChange({ custom_tool_id: undefined });
    }
  };

  const handleModelOverridesChange = (toolId: string, overrides: Record<string, string>) => {
    saveAppConfig({
      custom_tools: customTools.map((tool) =>
        tool.id === toolId ? { ...tool, model_overrides: overrides } : tool,
      ),
    });
  };

  const applyTask = (task: EditTask) => {
    const item = EDIT_TASKS.find((entry) => entry.id === task);
    const patch = patchForEditTask(task, modelGallery, {
      hasMask: Boolean(settings.inpaint_mask_path),
    });
    onChange({
      ...patch,
      custom_tool_id: undefined,
      ...(defaultPromptPatchForEditTask(task, settings) ?? {}),
      ...(item?.inpaintIntent
        ? {
            model: selectInpaintModelForIntent(
              modelGallery,
              item.inpaintIntent,
              settings.model,
            ),
          }
        : {}),
    });
  };

  const applyCustomTool = (tool: CustomTool) => {
    onChange({
      custom_tool_id: tool.id,
      edit_task: undefined,
      inpaint_intent: undefined,
    });
    void persistCustomToolSelection(tool.id);
  };

  useEffect(() => {
    const toolId = resolveCustomTool(customTools, activeCustomToolId)?.id?.trim();
    if (!toolId) {
      setCustomToolMissing([]);
      setCustomToolDepsReady(null);
      return;
    }
    let cancelled = false;
    setCustomToolDepsBusy(true);
    void (async () => {
      try {
        const payload = await fetchCustomToolDependencies(toolId, true);
        if (cancelled) return;
        const missing = (payload.missing ?? []) as ModelDependencyItem[];
        setCustomToolMissing(missing);
        setCustomToolDepsReady(Boolean(payload.ready));
      } catch {
        if (!cancelled) {
          setCustomToolMissing([]);
          setCustomToolDepsReady(null);
        }
      } finally {
        if (!cancelled) setCustomToolDepsBusy(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [activeCustomToolId, JSON.stringify(activeTool?.model_overrides ?? {})]);

  const outfitRegions = settings.outfit_transfer_regions ?? [];
  const toggleOutfitRegion = (
    region: NonNullable<GenerationSettings["outfit_transfer_regions"]>[number],
  ) => {
    const next = outfitRegions.includes(region)
      ? outfitRegions.filter((item) => item !== region)
      : [...outfitRegions, region];
    onChange({ outfit_transfer_regions: next.length ? next : undefined });
  };

  const updatePortrait = (patch: Partial<GenerationSettings>) => {
    const merged = { ...settings, ...patch };
    onChange({
      ...patch,
      prompt: buildPortraitMasterPrompt(merged),
    });
  };

  return (
    <div className="space-y-4 font-mono text-[#cccccc]">
      <div className="overflow-hidden rounded-md border border-[#4a4a4a] bg-[#353535] shadow-[0_2px_8px_rgba(0,0,0,0.35)]">
        <div className="flex items-center justify-between border-b border-[#4a4a4a] bg-[#232629] px-2.5 py-1.5">
          <span className="text-[12px] font-semibold text-[#cccccc]">
            Native Tools
          </span>
        </div>
        <div className="space-y-3 px-2.5 py-2.5">
          <p className="mb-1.5 text-[10px] font-medium text-[#aaaaaa]">
            Select a specialized creative tool
          </p>
          <div className="grid grid-cols-3 gap-1 rounded-md border border-[#4a4a4a]/70 bg-[#2a2a2a]/60 p-0.5">
            {nativeTasks.map((item) => {
              const active = activeTask === item.id && !activeCustomToolId;
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => applyTask(item.id)}
                  title={item.hint}
                  aria-pressed={active}
                  className={`min-h-8 rounded px-1 py-1 text-[9px] font-medium transition ${
                    active
                      ? "bg-[#6a9955]/25 text-[#a8d08d]"
                      : "text-[#888888] hover:bg-[#353535] hover:text-[#cccccc]"
                  }`}
                >
                  {item.short}
                </button>
              );
            })}
          </div>
          <p className="mt-1.5 text-[9px] leading-snug text-[#777777]">
            {nativeTasks.find((item) => item.id === activeTask && !activeCustomToolId)?.hint ??
              "Choose a tool to activate its specific workflow and settings."}
          </p>

          {activeTask === "outfit_transfer" && !activeCustomToolId && (
            <div className="space-y-1.5 rounded-md border border-[#4a4a4a]/70 bg-[#2a2a2a]/50 p-2">
              <p className="text-[10px] font-medium text-[#aaaaaa]">Outfit transfer</p>
              <p className="text-[9px] leading-snug text-[#777777]">
                Attach the person as the primary image and the outfit photo as a reference. Add a mask to fall back to Flux Fill.
              </p>
              <div className="flex flex-wrap gap-1.5">
                {(["upper_body", "lower_body", "full_outfit", "shoes_accessories"] as const).map((r) => {
                  const active = outfitRegions.includes(r);
                  return (
                    <button
                      key={r}
                      type="button"
                      onClick={() => toggleOutfitRegion(r)}
                      className={`rounded px-2 py-0.5 text-[9px] uppercase tracking-wider ${
                        active
                          ? "bg-[#6a9955] text-white"
                          : "bg-[#444444] text-[#aaaaaa] hover:bg-[#555555]"
                      }`}
                    >
                      {r.replace("_", " ")}
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {activeTask === "cutout_compose" && !activeCustomToolId && (
            <div className="space-y-1.5 rounded-md border border-[#4a4a4a]/70 bg-[#2a2a2a]/50 p-2">
              <p className="text-[10px] font-medium text-[#aaaaaa]">Cutout compose</p>
              <p className="text-[9px] leading-snug text-[#777777]">
                Attach the subject as the primary image and the background scene as a second reference. Harmonization keeps the composite layout.
              </p>
            </div>
          )}

          {activeTask === "portrait_master" && !activeCustomToolId && (
            <div className="space-y-2 rounded-md border border-[#4a4a4a]/70 bg-[#2a2a2a]/50 p-2">
              <p className="text-[10px] font-medium text-[#aaaaaa]">Portrait Master</p>
              <p className="text-[9px] leading-snug text-[#777777]">
                Attach a portrait reference. Sliders build the prompt; OpenPose and depth ControlNet preserve pose and layout.
              </p>
              <label className="block text-[9px] text-[#aaaaaa]">
                Shot
                <select
                  value={settings.portrait_shot ?? "portrait"}
                  onChange={(e) =>
                    updatePortrait({
                      portrait_shot: e.target.value as GenerationSettings["portrait_shot"],
                    })
                  }
                  className="mt-1 w-full rounded border border-[#4a4a4a] bg-[#353535] px-2 py-1 text-[10px]"
                >
                  {PORTRAIT_SHOTS.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block text-[9px] text-[#aaaaaa]">
                Age — {settings.portrait_age ?? 30}
                <input
                  type="range"
                  min={8}
                  max={90}
                  step={1}
                  value={settings.portrait_age ?? 30}
                  onChange={(e) => updatePortrait({ portrait_age: Number(e.target.value) })}
                  className="mt-1 w-full"
                />
              </label>
              <div className="grid grid-cols-2 gap-2">
                <label className="block text-[9px] text-[#aaaaaa]">
                  Expression
                  <select
                    value={settings.portrait_expression ?? "neutral"}
                    onChange={(e) =>
                      updatePortrait({
                        portrait_expression: e.target.value as GenerationSettings["portrait_expression"],
                      })
                    }
                    className="mt-1 w-full rounded border border-[#4a4a4a] bg-[#353535] px-2 py-1 text-[10px]"
                  >
                    {PORTRAIT_EXPRESSIONS.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block text-[9px] text-[#aaaaaa]">
                  Lighting
                  <select
                    value={settings.portrait_lighting ?? "studio"}
                    onChange={(e) =>
                      updatePortrait({
                        portrait_lighting: e.target.value as GenerationSettings["portrait_lighting"],
                      })
                    }
                    className="mt-1 w-full rounded border border-[#4a4a4a] bg-[#353535] px-2 py-1 text-[10px]"
                  >
                    {PORTRAIT_LIGHTING.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <label className="block text-[9px] text-[#aaaaaa]">
                Skin detail — {(settings.portrait_skin_detail ?? 0.5).toFixed(2)}
                <input
                  type="range"
                  min={0}
                  max={1}
                  step={0.01}
                  value={settings.portrait_skin_detail ?? 0.5}
                  onChange={(e) => updatePortrait({ portrait_skin_detail: Number(e.target.value) })}
                  className="mt-1 w-full"
                />
              </label>
              <label className="block text-[9px] text-[#aaaaaa]">
                Eye detail — {(settings.portrait_eye_detail ?? 0.5).toFixed(2)}
                <input
                  type="range"
                  min={0}
                  max={1}
                  step={0.01}
                  value={settings.portrait_eye_detail ?? 0.5}
                  onChange={(e) => updatePortrait({ portrait_eye_detail: Number(e.target.value) })}
                  className="mt-1 w-full"
                />
              </label>
              <label className="block text-[9px] text-[#aaaaaa]">
                Pose strength — {(settings.portrait_pose_strength ?? 0.65).toFixed(2)}
                <input
                  type="range"
                  min={0}
                  max={1}
                  step={0.01}
                  value={settings.portrait_pose_strength ?? 0.65}
                  onChange={(e) => onChange({ portrait_pose_strength: Number(e.target.value) })}
                  className="mt-1 w-full"
                />
              </label>
              <label className="block text-[9px] text-[#aaaaaa]">
                Depth strength — {(settings.portrait_depth_strength ?? 0.55).toFixed(2)}
                <input
                  type="range"
                  min={0}
                  max={1}
                  step={0.01}
                  value={settings.portrait_depth_strength ?? 0.55}
                  onChange={(e) => onChange({ portrait_depth_strength: Number(e.target.value) })}
                  className="mt-1 w-full"
                />
              </label>
            </div>
          )}
        </div>
      </div>

      <div className="overflow-hidden rounded-md border border-[#4a4a4a] bg-[#353535] shadow-[0_2px_8px_rgba(0,0,0,0.35)]">
        <div className="flex flex-col p-3">
          <div className="flex items-center justify-between border-b border-[#4a4a4a] pb-2 mb-2">
            <h2 className="text-[12px] font-semibold text-[#cccccc] uppercase tracking-wider">
              Custom Tools
            </h2>
            <button
              type="button"
              onClick={() => setIsImportModalOpen(true)}
              className="rounded bg-[#3c3c3c] px-2 py-1 text-[10px] text-[#cccccc] hover:bg-[#4a4a4a]"
            >
              + Import Tool...
            </button>
          </div>

          <p className="text-[10px] text-[#aaaaaa] mb-3">
            Import ComfyUI API-format workflows and bind inputs to DreamForge prompts and images.
          </p>

          {activeCustomToolId && (
            <div className="mb-3 rounded border border-[#4a4a4a]/70 bg-[#2a2a2a]/70 px-2.5 py-2">
              {customToolDepsBusy ? (
                <p className="text-[10px] text-[#aaaaaa]">Checking ComfyUI requirements…</p>
              ) : customToolDepsReady ? (
                <p className="text-[10px] text-[#6a9955]">ComfyUI nodes for this tool are ready.</p>
              ) : customToolMissing.length > 0 ? (
                <div className="flex items-start justify-between gap-2">
                  <p className="text-[10px] text-[#d7ba7d]">
                    Missing {customToolMissing.length} requirement(s) for the selected tool.
                  </p>
                  {onInstallCompanionItems && (
                    <button
                      type="button"
                      onClick={() => onInstallCompanionItems(customToolMissing)}
                      className="shrink-0 rounded bg-[#0e639c] px-2 py-1 text-[10px] text-white hover:bg-[#1177bb]"
                    >
                      Install
                    </button>
                  )}
                </div>
              ) : null}
            </div>
          )}

          {customTools.length === 0 ? (
            <div className="rounded border border-dashed border-[#3c3c3c] p-4 text-center">
              <p className="text-xs text-[#888888]">No custom tools imported yet.</p>
            </div>
          ) : (
            <div className="space-y-2">
              {customTools.map((tool) => {
                const active =
                  activeCustomToolId === tool.id ||
                  (activeTool?.id === tool.id && !customTools.some((item) => item.id === activeCustomToolId));
                return (
                  <div
                    key={tool.id}
                    className={`rounded border bg-[#252526] p-2 ${
                      active ? "border-[#6a9955]" : "border-[#3c3c3c] hover:border-[#555555]"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <h3 className="text-[11px] font-semibold text-[#cccccc]">{tool.name}</h3>
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={() => applyCustomTool(tool)}
                          className="text-[10px] text-[#0e639c] hover:text-[#1177bb]"
                        >
                          {active ? "Selected" : "Use Tool"}
                        </button>
                        <button
                          type="button"
                          onClick={() => handleRemoveCustomTool(tool.id)}
                          className="text-[10px] text-[#888888] hover:text-[#cccccc]"
                        >
                          Remove
                        </button>
                      </div>
                    </div>
                    {tool.description && (
                      <p className="text-[10px] text-[#aaaaaa] mt-1">{tool.description}</p>
                    )}
                    {active && customToolMissing.length > 0 && !customToolDepsBusy && (
                      <p className="mt-1 text-[10px] text-[#d7ba7d]">
                        Needs {customToolMissing.length} ComfyUI pack(s) or model(s).
                      </p>
                    )}
                    {active && (
                      <CustomToolModelOverrides
                        tool={tool}
                        modelGallery={modelGallery}
                        onChangeOverrides={handleModelOverridesChange}
                      />
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {isImportModalOpen && (
        <CustomToolImportModal
          onClose={() => setIsImportModalOpen(false)}
          onSave={handleSaveCustomTool}
        />
      )}
    </div>
  );
}
