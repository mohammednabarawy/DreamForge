import type { GenerationSettings, ModelGalleryItem } from "../lib/tauri-api";
import { MODE_AUTO_SUMMARY } from "../lib/generationTabVisibility";
import { isFluxKontextEditModel, isQwenEditModel } from "../lib/editModel";
import {
  EDIT_TASKS,
  type EditTask,
  INPAINT_INTENTS,
  normalizeEditTask,
  normalizeInpaintIntent,
  patchForEditTask,
  patchForInpaintIntent,
  selectInpaintModelForIntent,
  showInpaintAdditionalPrompt,
} from "../lib/inpaintIntent";
import { defaultPromptPatchForEditTask } from "../lib/editTaskPrompts";

type Props = {
  settings: GenerationSettings;
  onChange: (patch: Partial<GenerationSettings>) => void;
  isInpaint: boolean;
  routedModelLabel: string;
  editRouteSubtitle?: string;
  showEditStrength: boolean;
  advancedMode?: boolean;
  modelGallery?: ModelGalleryItem[];
};

function FieldLabel({
  children,
  hint,
}: {
  children: React.ReactNode;
  hint?: string;
}) {
  return (
    <span className="block">
      <span className="text-xs text-dfui-muted">{children}</span>
      {hint && (
        <span className="mt-0.5 block text-[10px] leading-snug text-dfui-tertiary">{hint}</span>
      )}
    </span>
  );
}

function editPanelTitle(
  settings: GenerationSettings,
  modelGallery: ModelGalleryItem[],
  isInpaint: boolean,
): string {
  if (isInpaint) return "Flux Fill inpaint";
  if (modelGallery.some((item) => item.engine_name === settings.model && item.family === "krea2")) {
    return "Krea 2 Identity Edit";
  }
  const editType = (settings.edit_type ?? "").toLowerCase();
  if (editType === "qwen_edit") return "Qwen Image Edit";
  if (editType === "kontext") return "Flux Kontext edit";
  const model = modelGallery.find((item) => item.engine_name === settings.model);
  if (model) {
    if (isQwenEditModel(model)) return "Qwen Image Edit";
    if (isFluxKontextEditModel(model)) return "Flux Kontext edit";
  }
  return "Image edit";
}

/** Edit / inpaint controls only — routing and sampling stay on DreamForge defaults. */
export function EditFamilySettingsPanel({
  settings,
  onChange,
  isInpaint,
  routedModelLabel,
  editRouteSubtitle,
  showEditStrength,
  advancedMode = false,
  modelGallery = [],
}: Props) {
  const autoSummary = isInpaint ? MODE_AUTO_SUMMARY.inpaint : MODE_AUTO_SUMMARY.edit;
  const inpaintIntent = normalizeInpaintIntent(settings.inpaint_intent);
  const activeIntent = INPAINT_INTENTS.find((item) => item.id === inpaintIntent);
  const activeTask = normalizeEditTask(settings.edit_task);
  const visibleEditTasks = EDIT_TASKS.filter((item) => {
    if (item.toolboxOnly) return false;
    return isInpaint ? item.id !== "global_edit" : !item.inpaintOnly;
  });

  const applyInpaintIntent = (intent: typeof inpaintIntent) => {
    onChange({
      ...patchForInpaintIntent(intent),
      edit_task: undefined,
      model: selectInpaintModelForIntent(modelGallery, intent, settings.model),
    });
  };

  const applyEditTask = (task: EditTask) => {
    const item = EDIT_TASKS.find((entry) => entry.id === task);
    const patch = patchForEditTask(task, modelGallery, {
      isInpaint,
      hasMask: Boolean(settings.inpaint_mask_path),
    });
    onChange({
      ...patch,
      ...(defaultPromptPatchForEditTask(task, settings) ?? {}),
      ...(isInpaint && item?.inpaintIntent
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

  const panelTitle = editPanelTitle(settings, modelGallery, isInpaint);
  const isKreaEdit = panelTitle === "Krea 2 Identity Edit";
  const hardMask = Boolean(settings.inpaint_hard_mask);
  const editStrengthLabel =
    settings.edit_strength == null
      ? "auto"
      : `${Math.round(settings.edit_strength * 100)}%`;
  const outfitRegions = settings.outfit_transfer_regions ?? [];
  const toggleOutfitRegion = (
    region: NonNullable<GenerationSettings["outfit_transfer_regions"]>[number],
  ) => {
    const next = outfitRegions.includes(region)
      ? outfitRegions.filter((item) => item !== region)
      : [...outfitRegions, region];
    onChange({ outfit_transfer_regions: next.length ? next : undefined });
  };

  return (
    <div className="overflow-hidden rounded-md border border-[#4a4a4a] bg-[#353535] font-mono shadow-[0_2px_8px_rgba(0,0,0,0.35)]">
      <div className="flex items-center justify-between border-b border-[#4a4a4a] bg-[#232629] px-2.5 py-1.5">
        <span className="text-[12px] font-semibold text-[#cccccc]">
          {panelTitle}
        </span>
        <span className="text-[9px] uppercase tracking-wide text-[#777777]">
          {isInpaint ? "image/inpaint" : "image/edit"}
        </span>
      </div>

      <div className="border-b border-[#4a4a4a]/70 px-2.5 py-1.5">
        <p className="text-[9px] leading-snug text-[#777777]">{autoSummary}</p>
        <p className="mt-1 truncate text-[10px] text-[#a8d08d]">
          {editRouteSubtitle ?? routedModelLabel}
        </p>
      </div>

      <div className="space-y-3 px-2.5 py-2.5">
        {isKreaEdit && (
          <p className="text-[10px] leading-relaxed text-dfui-muted">
            Identity Edit v1.2 is applied automatically at 0.75 strength; adjust it in LoRAs.
            Attach the source/scene first and an optional subject second.
            Uses full denoise and an empty negative prompt. Turbo: try 8 steps, CFG 1, Euler/simple.
          </p>
        )}
        {showEditStrength && !isKreaEdit && (
          <label className="block">
            <FieldLabel hint="How strongly the edit changes the source image.">
              denoise / edit strength — {editStrengthLabel}
            </FieldLabel>
            <input
              type="range"
              min={0.1}
              max={1}
              step={0.01}
              value={settings.edit_strength ?? 1}
              onChange={(e) => onChange({ edit_strength: Number(e.target.value) })}
              className="mt-1 w-full accent-[#6a9955]"
            />
          </label>
        )}

        {visibleEditTasks.length > 0 && (
          <div>
            <p className="mb-1.5 text-[10px] font-medium text-[#aaaaaa]">
              {isInpaint ? "Edit task" : "Edit mode"}
            </p>
            <div className="grid grid-cols-4 gap-1 rounded-md border border-[#4a4a4a]/70 bg-[#2a2a2a]/60 p-0.5">
              {visibleEditTasks.map((item) => {
                const active =
                  activeTask === item.id ||
                  (!activeTask && !isInpaint && item.id === "global_edit");
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => applyEditTask(item.id)}
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
              {EDIT_TASKS.find((item) => item.id === activeTask)?.hint ??
                "Dry-run resolves the final route, strength, mask defaults, and model instruction."}
            </p>
          </div>
        )}

        {activeTask === "outfit_transfer" && (
          <div className="space-y-1.5 rounded-md border border-[#4a4a4a]/70 bg-[#2a2a2a]/50 p-2">
            <p className="text-[10px] font-medium text-[#aaaaaa]">Outfit transfer</p>
            <p className="text-[9px] leading-snug text-[#777777]">
              Add the outfit photo as a reference image. Edit mode uses Qwen multi-image
              compose; Fix region with a mask uses Flux Fill for constrained clothing edits.
            </p>
            <div className="grid grid-cols-2 gap-1 text-[9px] text-[#999999]">
              {(
                [
                  ["upper_body", "Upper body"],
                  ["lower_body", "Lower body"],
                  ["full_outfit", "Full outfit"],
                  ["shoes_accessories", "Shoes/accessories"],
                ] as const
              ).map(([id, label]) => (
                <label
                  key={id}
                  className="inline-flex items-center gap-1 rounded border border-[#4a4a4a]/60 px-1.5 py-1"
                >
                  <input
                    type="checkbox"
                    checked={outfitRegions.includes(id)}
                    onChange={() => toggleOutfitRegion(id)}
                    className="h-3 w-3 accent-[#6a9955]"
                  />
                  {label}
                </label>
              ))}
            </div>
          </div>
        )}

        {activeTask === "cutout_compose" && (
          <div className="space-y-1.5 rounded-md border border-[#4a4a4a]/70 bg-[#2a2a2a]/50 p-2">
            <p className="text-[10px] font-medium text-[#aaaaaa]">Cutout compose</p>
            <p className="text-[9px] leading-snug text-[#777777]">
              Image 1 is the subject (background removed). Add the background scene as a second reference.
            </p>
            <label className="block mt-1.5">
              <span className="mb-0.5 block text-[10px] text-[#aaaaaa]">Placement</span>
              <select
                className="w-full rounded border border-[#444444] bg-[#2d2d2d] px-1 py-1 text-[10px] text-[#cccccc] focus:border-[#007fd4] focus:outline-none"
                value={settings.cutout_placement || "center"}
                onChange={(e) =>
                  onChange({
                    cutout_placement: e.target.value as NonNullable<GenerationSettings["cutout_placement"]>,
                  })
                }
              >
                <option value="center">Center</option>
                <option value="left">Left</option>
                <option value="right">Right</option>
                <option value="foreground">Foreground</option>
                <option value="background">Background</option>
              </select>
            </label>
          </div>
        )}

        {!isInpaint && activeTask === "photo_restore" && (
          <div className="space-y-2 rounded-md border border-[#4a4a4a]/70 bg-[#2a2a2a]/50 p-2">
            <p className="text-[10px] font-medium text-[#aaaaaa]">Photo restore</p>
            <label className="block">
              <FieldLabel hint="Depth structure guidance (keep low for faithful restore).">
                Depth strength — {(settings.depth_strength ?? 0.15).toFixed(2)}
              </FieldLabel>
              <input
                type="range"
                min={0.05}
                max={0.5}
                step={0.01}
                value={settings.depth_strength ?? 0.15}
                onChange={(e) => onChange({ depth_strength: Number(e.target.value) })}
                className="mt-1 w-full accent-[#6a9955]"
              />
            </label>
            <label className="block">
              <FieldLabel hint="Lineart edge guidance for scratches and detail.">
                Lineart strength — {(settings.lineart_strength ?? 0.35).toFixed(2)}
              </FieldLabel>
              <input
                type="range"
                min={0.1}
                max={0.8}
                step={0.01}
                value={settings.lineart_strength ?? 0.35}
                onChange={(e) => onChange({ lineart_strength: Number(e.target.value) })}
                className="mt-1 w-full accent-[#6a9955]"
              />
            </label>
            <label className="inline-flex items-center gap-1.5 text-[10px] text-[#aaaaaa]">
              <input
                type="checkbox"
                checked={Boolean(settings.face_preservation ?? true)}
                onChange={(e) => onChange({ face_preservation: e.target.checked })}
                className="h-3.5 w-3.5 accent-[#6a9955]"
              />
              Face detail pass (Impact Pack)
            </label>
            <label className="inline-flex items-center gap-1.5 text-[10px] text-[#aaaaaa]">
              <input
                type="checkbox"
                checked={Boolean(settings.post_upscale_enabled)}
                onChange={(e) =>
                  onChange({
                    post_upscale_enabled: e.target.checked,
                    post_upscale: e.target.checked
                      ? settings.post_upscale ?? "ultimate_sd_upscale"
                      : undefined,
                  })
                }
                className="h-3.5 w-3.5 accent-[#6a9955]"
              />
              Upscale after restore
            </label>
            <p className="text-[9px] leading-snug text-[#777777]">
              Routes through SDXL + ControlNet Union (depth + lineart). Install depth/lineart
              preprocessors and an SDXL checkpoint for best results.
            </p>
          </div>
        )}

        {!isInpaint && activeTask !== "photo_restore" && (
          <>
            <div>
              <p className="mb-1.5 text-[10px] leading-snug text-[#777777]">
                Preservation hints — what to keep from the source image during edit.
              </p>
              <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
                {(
                  [
                    ["preserve_style", "Style"],
                    ["preserve_text", "Text"],
                  ] as const
                ).map(([key, label]) => (
                  <label
                    key={key}
                    className="inline-flex items-center gap-1.5 text-[10px] text-[#aaaaaa]"
                  >
                    <input
                      type="checkbox"
                      checked={Boolean(settings[key])}
                      onChange={(e) => onChange({ [key]: e.target.checked })}
                      className="h-3.5 w-3.5 accent-[#6a9955]"
                    />
                    {label}
                  </label>
                ))}
              </div>
            </div>
          </>
        )}

        {isInpaint && (
          <>
            {advancedMode ? (
            <div>
              <p className="mb-1.5 text-[10px] font-medium text-[#aaaaaa]">Inpaint behavior</p>
              <div className="grid grid-cols-3 gap-1 rounded-md border border-[#4a4a4a]/70 bg-[#2a2a2a]/60 p-0.5">
                {INPAINT_INTENTS.map((item) => {
                  const active = inpaintIntent === item.id;
                  return (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => applyInpaintIntent(item.id)}
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
              {activeIntent ? (
                <p className="mt-1.5 text-[9px] leading-snug text-[#777777]">
                  {activeIntent.hint}
                </p>
              ) : null}
            </div>
            ) : null}

            {showInpaintAdditionalPrompt(inpaintIntent) ? (
              <label className="block">
                <FieldLabel hint="Optional extra guidance for the masked region only.">
                  Additional inpaint prompt
                </FieldLabel>
                <input
                  type="text"
                  value={settings.inpaint_additional_prompt ?? ""}
                  onChange={(e) =>
                    onChange({ inpaint_additional_prompt: e.target.value || undefined })
                  }
                  placeholder="e.g. sharper eyes, cleaner skin texture"
                  className="mt-1 w-full rounded border border-[#555555] bg-[#2a2a2a] px-2 py-1.5 font-mono text-[11px] text-[#e8e8e8] focus:border-[#6a9955] focus:outline-none"
                />
              </label>
            ) : null}

            <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
              <label className="block">
                <FieldLabel>Mask grow — {settings.inpaint_grow ?? 4}px</FieldLabel>
                <input
                  type="range"
                  min={0}
                  max={24}
                  value={settings.inpaint_grow ?? 4}
                  onChange={(e) => onChange({ inpaint_grow: Number(e.target.value) })}
                  className="mt-1 w-full accent-[#6a9955]"
                />
              </label>
              <label className="block">
                <FieldLabel
                  hint={
                    hardMask
                      ? "Feather is off while hard mask is enabled."
                      : undefined
                  }
                >
                  Feather — {settings.inpaint_feather ?? 4}px
                </FieldLabel>
                <input
                  type="range"
                  min={0}
                  max={24}
                  value={settings.inpaint_feather ?? 4}
                  disabled={hardMask}
                  onChange={(e) => onChange({ inpaint_feather: Number(e.target.value) })}
                  className="mt-1 w-full accent-[#6a9955] disabled:cursor-not-allowed disabled:opacity-40"
                />
              </label>
              <label className="block">
                <FieldLabel
                  hint="Padding sent to the inpaint workflow so the model sees surrounding context."
                >
                  Context padding — {settings.inpaint_mask_grow_by ?? 20}px
                </FieldLabel>
                <input
                  type="range"
                  min={0}
                  max={64}
                  value={settings.inpaint_mask_grow_by ?? 20}
                  onChange={(e) => onChange({ inpaint_mask_grow_by: Number(e.target.value) })}
                  className="mt-1 w-full accent-[#6a9955]"
                />
              </label>
            </div>
            {advancedMode ? (
              <label className="inline-flex items-center gap-1.5 text-[10px] text-[#aaaaaa]">
                <input
                  type="checkbox"
                  checked={Boolean(settings.inpaint_hard_mask)}
                  onChange={(e) =>
                    onChange({ inpaint_hard_mask: e.target.checked || undefined })
                  }
                  className="h-3.5 w-3.5 accent-[#6a9955]"
                />
                Hard mask (no feather)
              </label>
            ) : null}

            {activeTask === "extend" && (
              <div className="space-y-2 rounded-md border border-[#4a4a4a]/70 bg-[#2a2a2a]/50 p-2">
                <p className="text-[10px] font-medium text-[#aaaaaa]">Canvas extend</p>
                <div className="grid grid-cols-4 gap-1">
                  {(["left", "right", "top", "bottom"] as const).map((direction) => {
                    const active = (settings.outpaint_direction ?? "right") === direction;
                    return (
                      <button
                        key={direction}
                        type="button"
                        onClick={() => onChange({ outpaint_direction: direction })}
                        className={`min-h-7 rounded px-1 py-1 text-[9px] font-medium capitalize transition ${
                          active
                            ? "bg-[#6a9955]/25 text-[#a8d08d]"
                            : "text-[#888888] hover:bg-[#353535] hover:text-[#cccccc]"
                        }`}
                        aria-pressed={active}
                      >
                        {direction}
                      </button>
                    );
                  })}
                </div>
                <label className="block">
                  <FieldLabel>Extend amount — {settings.outpaint_amount ?? 256}px</FieldLabel>
                  <input
                    type="range"
                    min={64}
                    max={512}
                    step={32}
                    value={settings.outpaint_amount ?? 256}
                    onChange={(e) => onChange({ outpaint_amount: Number(e.target.value) })}
                    className="mt-1 w-full accent-[#6a9955]"
                  />
                </label>
                <label className="block">
                  <FieldLabel>Edge feather — {settings.outpaint_feathering ?? 40}px</FieldLabel>
                  <input
                    type="range"
                    min={0}
                    max={80}
                    value={settings.outpaint_feathering ?? 40}
                    onChange={(e) => onChange({ outpaint_feathering: Number(e.target.value) })}
                    className="mt-1 w-full accent-[#6a9955]"
                  />
                </label>
              </div>
            )}
            <p className="text-[10px] leading-snug text-[#777777]">
              {hardMask
                ? "Hard mask is on — grow and context padding still apply; feather is skipped at export."
                : "Paint or tap-select the mask on the canvas, then tune grow and feather."}
            </p>
          </>
        )}
      </div>
    </div>
  );
}
