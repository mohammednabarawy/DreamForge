import type { GenerationSettings, ModelGalleryItem } from "../lib/tauri-api";
import { MODE_AUTO_SUMMARY } from "../lib/generationTabVisibility";
import { isFluxKontextEditModel, isQwenEditModel } from "../lib/editModel";
import {
  INPAINT_INTENTS,
  normalizeInpaintIntent,
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
  modelGallery = [],
}: Props) {
  const autoSummary = isInpaint ? MODE_AUTO_SUMMARY.inpaint : MODE_AUTO_SUMMARY.edit;
  const inpaintIntent = normalizeInpaintIntent(settings.inpaint_intent);
  const activeIntent = INPAINT_INTENTS.find((item) => item.id === inpaintIntent);

  const applyInpaintIntent = (intent: typeof inpaintIntent) => {
    onChange({
      ...patchForInpaintIntent(intent),
      model: selectInpaintModelForIntent(modelGallery, intent, settings.model),
    });
  };

  const panelTitle = editPanelTitle(settings, modelGallery, isInpaint);

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
              denoise / edit strength — {Math.round((settings.edit_strength ?? 0.98) * 100)}%
            </FieldLabel>
            <input
              type="range"
              min={0.1}
              max={1}
              step={0.01}
              value={settings.edit_strength ?? 0.98}
              onChange={(e) => onChange({ edit_strength: Number(e.target.value) })}
              className="mt-1 w-full accent-[#6a9955]"
            />
          </label>
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
            <div>
              <p className="mb-1.5 text-[10px] font-medium text-[#aaaaaa]">Inpaint mode</p>
              <div className="grid grid-cols-3 gap-1 rounded-md border border-[#4a4a4a]/70 bg-[#2a2a2a]/60 p-0.5">
                {INPAINT_INTENTS.map((item) => {
                  const active = inpaintIntent === item.id;
                  return (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => applyInpaintIntent(item.id)}
                      title={item.hint}
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

            <p className="text-[10px] leading-snug text-[#777777]">
              Paint or tap-select the mask on the canvas, then tune grow and feather.
            </p>
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
                <FieldLabel>Feather — {settings.inpaint_feather ?? 4}px</FieldLabel>
                <input
                  type="range"
                  min={0}
                  max={24}
                  value={settings.inpaint_feather ?? 4}
                  onChange={(e) => onChange({ inpaint_feather: Number(e.target.value) })}
                  className="mt-1 w-full accent-[#6a9955]"
                />
              </label>
              <label className="block">
                <FieldLabel>Comfy expand — {settings.inpaint_mask_grow_by ?? 20}px</FieldLabel>
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
          </>
        )}
      </div>
    </div>
  );
}
