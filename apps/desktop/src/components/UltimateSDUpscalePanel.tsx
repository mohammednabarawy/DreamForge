import { useMemo, type ReactNode } from "react";
import { clampUpscaleBy, clampUpscaleTile } from "../lib/companionAssets";
import { CUSTOM_PERFORMANCE } from "../lib/generationSettingsUi";
import type { GenerationSettings } from "../lib/tauri-api";
import {
  ULTIMATE_SD_AUTO_SUMMARY,
  ULTIMATE_SD_NODE,
  ULTIMATE_SD_USER_WIDGETS,
  upscaleSettingsKey,
  type NodeWidgetSpec,
} from "../lib/upscaleNodeUi";

type Props = {
  settings: GenerationSettings;
  onChange: (patch: Partial<GenerationSettings>) => void;
};

function patchUpscale(patch: Partial<GenerationSettings>): Partial<GenerationSettings> {
  return { upscale_method: "ultimate_sd_upscale", performance: CUSTOM_PERFORMANCE, ...patch };
}

function readWidgetValue(
  settings: GenerationSettings,
  spec: NodeWidgetSpec,
): number | string | boolean {
  const key = upscaleSettingsKey(spec.key);
  const raw = (settings as Record<string, unknown>)[key];
  if (raw !== undefined && raw !== null) return raw as number | string | boolean;
  return spec.defaultValue;
}

function WidgetRow({
  spec,
  children,
}: {
  spec: NodeWidgetSpec;
  children: ReactNode;
}) {
  return (
    <div className="grid grid-cols-[minmax(0,38%)_minmax(0,1fr)] items-center gap-2 px-2.5 py-1.5 hover:bg-[#3d3d3d]/60">
      <span
        className="truncate font-mono text-[10px] text-[#aaaaaa]"
        title={spec.tooltip}
      >
        {spec.label}
      </span>
      <div className="min-w-0">{children}</div>
    </div>
  );
}

function NodeNumberInput({
  value,
  spec,
  onChange,
}: {
  value: number;
  spec: NodeWidgetSpec;
  onChange: (value: number) => void;
}) {
  return (
    <input
      type="number"
      min={spec.min}
      max={spec.max}
      step={spec.step}
      value={value}
      onChange={(e) => onChange(Number(e.target.value))}
      className="w-full rounded border border-[#555555] bg-[#2a2a2a] px-1.5 py-0.5 font-mono text-[11px] text-[#e8e8e8] focus:border-[#6a9955] focus:outline-none"
    />
  );
}

function NodeSelect({
  value,
  options,
  onChange,
}: {
  value: string;
  options: readonly string[];
  onChange: (value: string) => void;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="w-full rounded border border-[#555555] bg-[#2a2a2a] px-1.5 py-0.5 font-mono text-[11px] text-[#e8e8e8] focus:border-[#6a9955] focus:outline-none"
    >
      {options.map((opt) => (
        <option key={opt} value={opt}>
          {opt}
        </option>
      ))}
    </select>
  );
}

export function UltimateSDUpscalePanel({ settings, onChange }: Props) {
  const widgetValues = useMemo(() => {
    const map = new Map<string, number | string | boolean>();
    for (const spec of ULTIMATE_SD_USER_WIDGETS) {
      map.set(spec.key, readWidgetValue(settings, spec));
    }
    return map;
  }, [settings]);

  const setWidget = (spec: NodeWidgetSpec, value: number | string | boolean) => {
    const settingsKey = upscaleSettingsKey(spec.key);
    onChange(patchUpscale({ [settingsKey]: value } as Partial<GenerationSettings>));
  };

  const renderWidget = (spec: NodeWidgetSpec) => {
    const value = widgetValues.get(spec.key) ?? spec.defaultValue;

    if (spec.key === "upscale_by") {
      return (
        <NodeNumberInput
          spec={spec}
          value={clampUpscaleBy(Number(value))}
          onChange={(v) => setWidget(spec, clampUpscaleBy(v))}
        />
      );
    }

    if (spec.key === "tile_width" || spec.key === "tile_height") {
      const fallback = 1024;
      return (
        <NodeNumberInput
          spec={spec}
          value={clampUpscaleTile(Number(value), fallback)}
          onChange={(v) => setWidget(spec, clampUpscaleTile(v, fallback))}
        />
      );
    }

    if (spec.kind === "enum") {
      return (
        <NodeSelect
          value={String(value)}
          options={spec.options ?? []}
          onChange={(v) => setWidget(spec, v)}
        />
      );
    }

    return (
      <NodeNumberInput
        spec={spec}
        value={Number(value)}
        onChange={(v) => setWidget(spec, v)}
      />
    );
  };

  return (
    <div className="overflow-hidden rounded-md border border-[#4a4a4a] bg-[#353535] font-mono shadow-[0_2px_8px_rgba(0,0,0,0.35)]">
      <div className="flex items-center justify-between border-b border-[#4a4a4a] bg-[#232629] px-2.5 py-1.5">
        <span className="text-[12px] font-semibold text-[#cccccc]">{ULTIMATE_SD_NODE.title}</span>
        <span className="text-[9px] uppercase tracking-wide text-[#777777]">
          {ULTIMATE_SD_NODE.category}
        </span>
      </div>

      <div className="border-b border-[#4a4a4a]/70 px-2.5 py-1.5">
        <p className="text-[9px] leading-snug text-[#777777]">{ULTIMATE_SD_AUTO_SUMMARY}</p>
      </div>

      <div className="divide-y divide-[#4a4a4a]/50">
        {ULTIMATE_SD_USER_WIDGETS.map((spec) => (
          <WidgetRow key={spec.key} spec={spec}>
            {renderWidget(spec)}
          </WidgetRow>
        ))}
      </div>

      <div className="border-t border-[#4a4a4a]/70 px-2.5 py-1.5">
        <p className="text-[9px] leading-snug text-[#777777]">
          Only tile upscale controls are shown here. Model, prompts, ControlNet, template overrides,
          and hardware limits use DreamForge defaults (VRAM auto-detect). Optional enhancement prompt
          is in the command bar below.
        </p>
      </div>
    </div>
  );
}
