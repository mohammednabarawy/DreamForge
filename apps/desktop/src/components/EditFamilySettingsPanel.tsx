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
  const visibleEditTasks = EDIT_TASKS.filter((item) =>
    isInpaint ? item.id !== "global_edit" : item.id === "global_edit",
  );

  const applyInpaintIntent = (intent: typeof inpaintIntent) => {
    onChange({
      ...patchForInpaintIntent(intent),
      edit_task: undefined,
      model: selectInpaintModelForIntent(modelGallery, intent, settings.model),
    });
  };

  const applyEditTask = (task: EditTask) => {
    const item = EDIT_TASKS.find((entry) => entry.id === task);
    const patch = patchForEditTask(task);
    onChange({
      ...patch,
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
  const hardMask = Boolean(settings.inpaint_hard_mask);
  const editStrengthLabel =
    settings.edit_strength == null
      ? "auto"
      : `${Math.round(settings.edit_strength * 100)}%`;

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
        {showEditStrength && (
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
            <div className="grid grid-cols-3 gap-1 rounded-md border border-[#4a4a4a]/70 bg-[#2a2a2a]/60 p-0.5">
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

        {!isInpaint && (
          <>
            <label className="inline-flex items-center gap-1.5 text-[11px] text-[#cccccc]">
              <input
                type="checkbox"
                checked={Boolean(settings.face_preservation)}
                onChange={(e) =>
                  onChange({
                    face_preservation: e.target.checked,
                    preserve_character: e.target.checked ? settings.preserve_character : undefined,
                    identity_mode: e.target.checked ? "preserve_face" : undefined,
                  })
                }
                className="h-3.5 w-3.5 accent-[#6a9955]"
              />
              Face guidance
            </label>
            <p className="text-[10px] leading-snug text-[#777777]">
              Preserve face via Kontext/Qwen identity routing (not legacy FaceID weights).
            </p>
            <div>
              <p className="mb-1.5 text-[10px] leading-snug text-[#777777]">
                Preservation hints — what to keep from the source image during edit.
              </p>
              <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-3">
                {(
                  [
                    ["preserve_character", "Character"],
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
