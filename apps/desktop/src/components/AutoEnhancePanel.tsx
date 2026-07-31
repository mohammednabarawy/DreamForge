import type { GenerationSettings } from "../lib/tauri-api";
import {
  ENHANCE_TARGETS,
  normalizeEnhanceTarget,
  patchForEnhanceTarget,
  type EnhanceTarget,
} from "../lib/autoEnhance";

type Props = {
  settings: GenerationSettings;
  sourceImage?: string;
  onChange: (patch: Partial<GenerationSettings>) => void;
  onAutoEnhance?: (target: EnhanceTarget) => void;
  onVaryImage?: (amount: "subtle" | "strong") => void;
};

export function AutoEnhancePanel({
  settings,
  sourceImage,
  onChange,
  onAutoEnhance,
  onVaryImage,
}: Props) {
  const activeTarget = normalizeEnhanceTarget(settings.enhance_target);
  const autoFix = Boolean(settings.enhance_auto_fix || activeTarget);
  const src =
    sourceImage?.trim() ||
    settings.upscale_image?.trim() ||
    settings.input_image?.trim() ||
    "";

  const selectTarget = (target: EnhanceTarget) => {
    if (!src) return;
    onChange(
      patchForEnhanceTarget(target, src, {
        detectionPrompt: settings.enhance_detection_prompt,
        postUpscale: settings.enhance_post_upscale,
        detailPrompt: settings.detail_prompt,
      }),
    );
    if (onAutoEnhance) {
      onAutoEnhance(target);
    }
  };

  return (
    <div className="overflow-hidden rounded-md border border-[#4a4a4a] bg-[#353535] font-mono shadow-[0_2px_8px_rgba(0,0,0,0.35)]">
      <div className="border-b border-[#4a4a4a] bg-[#232629] px-2.5 py-1.5">
        <span className="text-[12px] font-semibold text-[#cccccc]">Detect, Fix &amp; Vary</span>
        <p className="text-[9px] leading-snug text-[#777777]">
          Auto-detect face, hands, or eyes to repair, or generate variations.
        </p>
      </div>

      <div className="space-y-2 px-2.5 py-2">
        <div className="flex flex-wrap items-center gap-1">
          <span className="text-[9px] text-[#aaaaaa] mr-1">Fix:</span>
          {ENHANCE_TARGETS.map((target) => {
            const selected = activeTarget === target.id;
            return (
              <button
                key={target.id}
                type="button"
                title={target.hint}
                disabled={!src}
                onClick={() => selectTarget(target.id)}
                className={`rounded border px-2 py-0.5 text-[10px] transition disabled:opacity-40 ${
                  selected
                    ? "border-[#6a9955] bg-[#3d4a38] text-[#cccccc]"
                    : "border-[#555555] text-[#aaaaaa] hover:border-[#6a9955]/60"
                }`}
              >
                {target.short}
              </button>
            );
          })}
        </div>

        {onVaryImage && (
          <div className="flex flex-wrap items-center gap-1 pt-1 border-t border-[#444444]">
            <span className="text-[9px] text-[#aaaaaa] mr-1">Vary:</span>
            <button
              type="button"
              title="Light img2img variation"
              disabled={!src}
              onClick={() => onVaryImage("subtle")}
              className="rounded border border-[#555555] px-2 py-0.5 text-[10px] text-[#aaaaaa] transition hover:border-[#6a9955]/60 hover:text-[#cccccc] disabled:opacity-40"
            >
              Subtle
            </button>
            <button
              type="button"
              title="Stronger img2img variation"
              disabled={!src}
              onClick={() => onVaryImage("strong")}
              className="rounded border border-[#555555] px-2 py-0.5 text-[10px] text-[#aaaaaa] transition hover:border-[#6a9955]/60 hover:text-[#cccccc] disabled:opacity-40"
            >
              Strong
            </button>
          </div>
        )}

        <label className="block">
          <span className="text-[9px] text-[#aaaaaa]">Detection prompt</span>
          <input
            type="text"
            value={settings.enhance_detection_prompt ?? ""}
            disabled={!src}
            placeholder="face, hands, eyes"
            onChange={(e) =>
              onChange({
                enhance_detection_prompt: e.target.value,
                detail_prompt: e.target.value.trim() || settings.detail_prompt,
              })
            }
            className="mt-0.5 w-full rounded border border-[#555555] bg-[#2a2a2a] px-2 py-1 text-[10px] text-[#e8e8e8] focus:border-[#6a9955] focus:outline-none disabled:opacity-40"
          />
        </label>

        <label className="flex items-center gap-2 text-[10px] text-[#aaaaaa]">
          <input
            type="checkbox"
            checked={Boolean(settings.enhance_post_upscale)}
            disabled={!src}
            onChange={(e) =>
              onChange({
                enhance_post_upscale: e.target.checked,
                post_upscale_enabled: e.target.checked,
                post_upscale: e.target.checked
                  ? settings.post_upscale ?? "ultimate_sd_upscale"
                  : settings.post_upscale,
              })
            }
            className="accent-[#6a9955]"
          />
          Upscale after fix (2× Ultimate SD)
        </label>

        {!src ? (
          <p className="text-[9px] text-[#888888]">Attach a source image to enable auto-fix and vary.</p>
        ) : autoFix ? (
          <p className="text-[9px] text-[#6a9955]">
            Ready — generate to run{" "}
            {activeTarget === "eyes"
              ? "masked inpaint (improve detail)"
              : "FaceDetailer"}{" "}
            on {activeTarget ?? "target"}.
          </p>
        ) : null}
      </div>
    </div>
  );
}
