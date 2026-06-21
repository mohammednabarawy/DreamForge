import type { GenerationSettings } from "../lib/tauri-api";
import { MODE_AUTO_SUMMARY } from "../lib/generationTabVisibility";

type Props = {
  settings: GenerationSettings;
  onChange: (patch: Partial<GenerationSettings>) => void;
  isInpaint: boolean;
  routedModelLabel: string;
  editRouteSubtitle?: string;
  showEditStrength: boolean;
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

/** Edit / inpaint controls only — routing and sampling stay on DreamForge defaults. */
export function EditFamilySettingsPanel({
  settings,
  onChange,
  isInpaint,
  routedModelLabel,
  editRouteSubtitle,
  showEditStrength,
}: Props) {
  const autoSummary = isInpaint ? MODE_AUTO_SUMMARY.inpaint : MODE_AUTO_SUMMARY.edit;

  return (
    <div className="overflow-hidden rounded-md border border-[#4a4a4a] bg-[#353535] font-mono shadow-[0_2px_8px_rgba(0,0,0,0.35)]">
      <div className="flex items-center justify-between border-b border-[#4a4a4a] bg-[#232629] px-2.5 py-1.5">
        <span className="text-[12px] font-semibold text-[#cccccc]">
          {isInpaint ? "Flux Fill inpaint" : "Flux Kontext edit"}
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
                    identity_mode: e.target.checked ? "faceid" : undefined,
                  })
                }
                className="h-3.5 w-3.5 accent-[#6a9955]"
              />
              Face guidance (when identity is attached)
            </label>
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
          </>
        )}

        {isInpaint && (
          <>
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
