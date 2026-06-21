import { Images } from "lucide-react";
import type { GenerationSettings } from "../lib/tauri-api";

type Props = {
  settings: GenerationSettings;
  onChange: (patch: Partial<GenerationSettings>) => void;
};

/** Extract mode — feature maps for ControlNet prep; no generation pipeline. */
export function FeatureExtractionPanel({ settings, onChange }: Props) {
  const inputImage = settings.input_image;

  return (
    <div className="overflow-hidden rounded-md border border-[#4a4a4a] bg-[#353535] font-mono shadow-[0_2px_8px_rgba(0,0,0,0.35)]">
      <div className="flex items-center justify-between border-b border-[#4a4a4a] bg-[#232629] px-2.5 py-1.5">
        <span className="text-[12px] font-semibold text-[#cccccc]">Feature extract</span>
        <span className="text-[9px] uppercase tracking-wide text-[#777777]">image/preprocess</span>
      </div>

      <div className="border-b border-[#4a4a4a]/70 px-2.5 py-1.5">
        <p className="text-[9px] leading-snug text-[#777777]">
          Auto: saves a control map to outputs — drag back into Create for ControlNet (advanced).
        </p>
      </div>

      <div className="space-y-3 px-2.5 py-2.5">
        <label className="block">
          <span className="block text-[10px] text-[#aaaaaa]">extraction_type</span>
          <select
            value={settings.extraction_type ?? "canny"}
            onChange={(e) => onChange({ extraction_type: e.target.value })}
            className="mt-1 w-full rounded border border-[#555555] bg-[#2a2a2a] px-1.5 py-1 font-mono text-[11px] text-[#e8e8e8] focus:border-[#6a9955] focus:outline-none"
          >
            <option value="canny">Canny Edge</option>
            <option value="depth">Depth Map</option>
            <option value="openpose">OpenPose (Pose)</option>
            <option value="lineart">Lineart</option>
          </select>
        </label>

        <div className="rounded-md border border-dashed border-[#555555] bg-[#2a2a2a] p-3 text-center">
          {inputImage ? (
            <div className="flex flex-col items-center gap-2">
              <img
                src={`asset://${inputImage}`}
                alt="Input"
                className="max-h-32 rounded object-contain shadow-sm"
              />
              <button
                type="button"
                onClick={() => onChange({ input_image: undefined })}
                className="text-[10px] text-red-400 hover:text-red-300"
              >
                Clear input
              </button>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-1.5 py-2">
              <Images size={20} className="text-[#777777]" />
              <p className="text-[10px] text-[#888888]">
                Drag an image to the prompt bar or pick from history.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
