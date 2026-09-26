import type { GenerationSettings } from "../lib/tauri-api";

type Props = {
  settings: GenerationSettings;
  onChange: (patch: Partial<GenerationSettings>) => void;
  isInpaint: boolean;
  routedModelLabel: string;
  editRouteSubtitle?: string;
  showEditStrength: boolean;
  advancedMode?: boolean;
};

/** Focused Qwen Image 2.1 edit controls; a mask turns the same mode into a masked edit. */
export function EditFamilySettingsPanel({
  settings,
  onChange,
  isInpaint,
  routedModelLabel,
  editRouteSubtitle,
  showEditStrength,
  advancedMode = false,
}: Props) {
  const hardMask = Boolean(settings.inpaint_hard_mask);

  return (
    <section className="overflow-hidden rounded-lg border border-dfui-border/50 bg-dfui-bg/25">
      <div className="flex items-center justify-between border-b border-dfui-border/40 px-2.5 py-2">
        <div className="min-w-0">
          <h3 className="text-xs font-semibold text-dfui-fg">Qwen Image 2.1 Edit</h3>
          <p className="truncate font-mono text-[9px] text-dfui-tertiary">
            {editRouteSubtitle ?? routedModelLabel}
          </p>
        </div>
        <span className="rounded-full border border-dfui-accent/30 bg-dfui-accent/10 px-2 py-0.5 text-[9px] font-medium text-dfui-accent">
          {isInpaint ? "Masked edit" : "Edit"}
        </span>
      </div>

      <div className="space-y-3 px-2.5 py-2.5">
        <p className="text-[10px] leading-snug text-dfui-tertiary">
          {isInpaint
            ? "Only the painted mask is changed. The source image and added references stay available to Qwen."
            : "Describe the change in the prompt. Image 1 is the edit target; added images are ordered references."}
        </p>

        {showEditStrength ? (
          <label className="block text-[10px] text-dfui-muted">
            Edit strength — {Math.round((settings.edit_strength ?? 1) * 100)}%
            <input
              type="range"
              min={0.1}
              max={1}
              step={0.01}
              value={settings.edit_strength ?? 1}
              onChange={(event) => onChange({ edit_strength: Number(event.target.value) })}
              className="mt-1 w-full accent-dfui-accent"
            />
          </label>
        ) : null}

        {!isInpaint ? (
          <div>
            <p className="mb-1.5 text-[10px] text-dfui-tertiary">Preserve from the source</p>
            <div className="grid grid-cols-2 gap-2">
              {(["preserve_style", "preserve_text"] as const).map((key) => (
                <label key={key} className="inline-flex items-center gap-1.5 text-[10px] text-dfui-muted">
                  <input
                    type="checkbox"
                    checked={Boolean(settings[key])}
                    onChange={(event) => onChange({ [key]: event.target.checked })}
                    className="accent-dfui-accent"
                  />
                  {key === "preserve_style" ? "Style" : "Text"}
                </label>
              ))}
            </div>
          </div>
        ) : null}

        {isInpaint && advancedMode ? (
          <div className="space-y-2 rounded-md border border-dfui-border/40 bg-dfui-panel/35 p-2">
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
              {([
                ["inpaint_grow", "Grow", 4, 24],
                ["inpaint_feather", "Feather", 4, 24],
                ["inpaint_mask_grow_by", "Context", 20, 64],
              ] as const).map(([key, label, fallback, max]) => (
                <label key={key} className="block text-[9px] text-dfui-muted">
                  {label} — {settings[key] ?? fallback}px
                  <input
                    type="range"
                    min={0}
                    max={max}
                    value={settings[key] ?? fallback}
                    disabled={key === "inpaint_feather" && hardMask}
                    onChange={(event) => onChange({ [key]: Number(event.target.value) })}
                    className="mt-1 w-full accent-dfui-accent disabled:opacity-40"
                  />
                </label>
              ))}
            </div>
            <label className="inline-flex items-center gap-1.5 text-[10px] text-dfui-muted">
              <input
                type="checkbox"
                checked={hardMask}
                onChange={(event) => onChange({ inpaint_hard_mask: event.target.checked || undefined })}
                className="accent-dfui-accent"
              />
              Hard edge (no feather)
            </label>
          </div>
        ) : null}
      </div>
    </section>
  );
}
