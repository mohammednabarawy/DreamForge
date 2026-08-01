import { ChevronDown, ChevronRight, ClipboardPaste, Copy, Dices, RotateCcw, Save, Shuffle } from "lucide-react";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  ASPECT_GROUP_ACCENT,
  ASPECT_GROUP_LABELS,
  CUSTOM_PERFORMANCE,
  IDEOGRAM_PERFORMANCE_PREVIEW,
  PERFORMANCE_PREVIEW,
  groupAspectPresets,
  ideogramPerformanceHint,
  isCustomPerformance,
  performanceHint,
} from "../lib/generationSettingsUi";
import {
  hidreamPerformancePreview,
} from "../lib/hidreamPerformance";
import {
  applyHiDreamO1DevAtSubmit,
  isHiDreamO1DevCheckpoint,
} from "../lib/hidreamO1Profiles";
import type { GenerationSettings, ModelDependencyItem, UiDefaults, ModelGalleryItem } from "../lib/tauri-api";
import type { StudioSettings } from "../lib/studioBridge";
import { listCreativeTemplates, type CreativeTemplateSummary } from "../lib/studioBridge";
import { defaultTemplateIdForMode } from "../lib/creativeTemplates";
import {
  buildGenerationTabContext,
  generationSectionVisible,
  isGenerateFamilyMode,
  MODE_AUTO_SUMMARY,
} from "../lib/generationTabVisibility";
import { EditFamilySettingsPanel } from "./EditFamilySettingsPanel";
import { CreativeToolboxPanel } from "./CreativeToolboxPanel";
import { UltimateSDUpscalePanel } from "./UltimateSDUpscalePanel";
import { AutoEnhancePanel } from "./AutoEnhancePanel";
import type { EnhanceTarget } from "../lib/autoEnhance";

const GENERATION_PRESETS_KEY = "dreamforge.generate.user-presets.v1";
const GENERATION_DENSITY_KEY = "dreamforge.generate.control-density.v1";
type UserGenerationPreset = { name: string; settings: Partial<GenerationSettings> };

function readUserPresets(): UserGenerationPreset[] {
  try {
    const value = JSON.parse(localStorage.getItem(GENERATION_PRESETS_KEY) ?? "[]");
    return Array.isArray(value) ? value.filter((item) => item?.name && item?.settings) : [];
  } catch {
    return [];
  }
}

function boundedNumber(value: string, min: number, max: number, fallback: number) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? Math.min(max, Math.max(min, parsed)) : fallback;
}

type Props = {
  settings: GenerationSettings;
  onChange: (patch: Partial<GenerationSettings>) => void;
  aspectPresets: string[];
  uiDefaults: UiDefaults | null;
  studioSettings?: StudioSettings | null;
  onSaveStudioSettings?: (patch: StudioSettings) => void | Promise<void>;
  imageNumberMax?: number;
  studioMode: string;
  isInpaint: boolean;
  showGenerateLikeSettings: boolean;
  showEditStrength: boolean;
  routedModelLabel: string;
  editRouteSubtitle?: string;
  isQwenModel: boolean;
  activeModelLabel: string;
  advancedMode?: boolean;
  modelGallery?: ModelGalleryItem[];
  onInstallCompanionItems?: (items: ModelDependencyItem[]) => void;
  onAutoEnhance?: (target: EnhanceTarget) => void;
  onVaryImage?: (amount: "subtle" | "strong") => void;
};

export function isModernModel(label: string): boolean {
  const lower = label.toLowerCase();
  return (
    lower.includes("flux") ||
    lower.includes("qwen") ||
    lower.includes("hidream") ||
    lower.includes("sd3") ||
    lower.includes("ideogram") ||
    lower.includes("krea")
  );
}

function SettingsSection({
  title,
  subtitle,
  defaultOpen = true,
  changed = false,
  onReset,
  children,
}: {
  title: string;
  subtitle?: string;
  defaultOpen?: boolean;
  changed?: boolean;
  onReset?: () => void;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section className="rounded-lg border border-dfui-border/45 bg-dfui-bg/25">
      <div className="flex items-center">
        <button type="button" onClick={() => setOpen((v) => !v)} aria-expanded={open} className="flex min-w-0 flex-1 items-center gap-2 px-2.5 py-2 text-left">
          {open ? <ChevronDown size={14} className="shrink-0 text-dfui-muted" /> : <ChevronRight size={14} className="shrink-0 text-dfui-muted" />}
          <span className="min-w-0 flex-1">
            <span className="block text-[10px] font-semibold uppercase tracking-wide text-dfui-muted">{title}{changed ? " · Modified" : ""}</span>
            {subtitle ? <span className="block text-[10px] leading-snug text-dfui-tertiary">{subtitle}</span> : null}
          </span>
        </button>
        {onReset ? (
          <button
            type="button"
            aria-label={`Reset ${title}`}
            onClick={onReset}
            className="mr-2 rounded p-1 text-dfui-tertiary hover:bg-dfui-surface hover:text-dfui-fg"
          >
            <RotateCcw size={12} />
          </button>
        ) : null}
      </div>
      {open && <div className="space-y-2.5 border-t border-dfui-border/30 px-2.5 pb-2.5 pt-2">{children}</div>}
    </section>
  );
}

function FieldLabel({ children, hint }: { children: ReactNode; hint?: string }) {
  return (
    <span className="block">
      <span className="text-xs text-dfui-muted">{children}</span>
      {hint && <span className="mt-0.5 block text-[10px] leading-snug text-dfui-tertiary">{hint}</span>}
    </span>
  );
}

export function GenerationSettingsPanel({
  settings,
  onChange,
  aspectPresets,
  uiDefaults,
  studioSettings,
  onSaveStudioSettings,
  imageNumberMax = 8,
  studioMode,
  isInpaint,
  showGenerateLikeSettings,
  showEditStrength,
  routedModelLabel,
  editRouteSubtitle,
  isQwenModel,
  activeModelLabel,
  advancedMode = false,
  modelGallery = [],
  onInstallCompanionItems,
  onAutoEnhance,
  onVaryImage,
}: Props) {
  const [creativeTemplates, setCreativeTemplates] = useState<CreativeTemplateSummary[]>([]);
  const [controlDensity, setControlDensity] = useState<"basic" | "advanced">(() =>
    localStorage.getItem(GENERATION_DENSITY_KEY) === "advanced" ? "advanced" : "basic",
  );
  const [userPresets, setUserPresets] = useState<UserGenerationPreset[]>(readUserPresets);
  const [customSize, setCustomSize] = useState(false);
  const [lockAspect, setLockAspect] = useState(true);

  useEffect(() => {
    if (!advancedMode) {
      setCreativeTemplates([]);
      return;
    }
    let cancelled = false;
    void listCreativeTemplates(studioMode)
      .then((templates) => {
        if (!cancelled) setCreativeTemplates(templates);
      })
      .catch(() => {
        if (!cancelled) setCreativeTemplates([]);
      });
    return () => {
      cancelled = true;
    };
  }, [advancedMode, studioMode]);

  const activeTemplateId =
    settings.template_id?.trim() ||
    defaultTemplateIdForMode(
      studioMode as "generate" | "edit" | "inpaint" | "upscale" | "agent",
      settings.post_upscale_enabled,
    ) ||
    "";
  const performances = uiDefaults?.performances ?? [
    "Lightning",
    "Speed",
    "Quality",
    CUSTOM_PERFORMANCE,
  ];
  const performance = settings.performance ?? "Lightning";
  const customPerf = isCustomPerformance(performance);
  const aspectGroups = useMemo(() => groupAspectPresets(aspectPresets), [aspectPresets]);
  const activeAspect = settings.aspect_ratio ?? "768x768";
  const currentWidth = settings.width ?? (Number(activeAspect.split(/[x×]/)[0]) || 768);
  const currentHeight = settings.height ?? (Number(activeAspect.split(/[x×]/)[1]) || 768);
  const activeModelLower = activeModelLabel.toLowerCase();
  const activeModelFamily = modelGallery.find((item) =>
    item.engine_name === settings.model || item.relative_path === settings.model || item.caption === activeModelLabel,
  )?.family;
  const isIdeogramModel = activeModelLower.includes("ideogram");
  let perfPreview = PERFORMANCE_PREVIEW[performance];
  if (isQwenModel && !customPerf) {
    if (performance === "Quality") {
      perfPreview = { steps: 28, cfg: 2.5, sampler: "euler", scheduler: "beta" };
    } else if (performance === "Speed") {
      perfPreview = { steps: 20, cfg: 2.5, sampler: "euler", scheduler: "beta" };
    } else if (performance === "Lightning") {
      perfPreview = { steps: 8, cfg: 1.5, sampler: "euler", scheduler: "sgm_uniform" };
    }
  } else if (activeModelLower.includes("flux") && !customPerf) {
    if (performance === "Quality") {
      perfPreview = { steps: 28, cfg: 3.5, sampler: "euler", scheduler: "beta" };
    } else if (performance === "Speed") {
      perfPreview = { steps: 20, cfg: 3, sampler: "euler", scheduler: "beta" };
    } else if (performance === "Lightning") {
      perfPreview = { steps: 8, cfg: 2, sampler: "euler", scheduler: "beta" };
    }
  } else if (activeModelLower.includes("hidream") && !customPerf) {
    const hidreamPreview = hidreamPerformancePreview(settings.model, performance);
    if (hidreamPreview) perfPreview = hidreamPreview;
  } else if (activeModelLower.includes("sd3") && !customPerf) {
    if (performance === "Quality") {
      perfPreview = { steps: 40, cfg: 5, sampler: "dpmpp_2m", scheduler: "sgm_uniform" };
    } else if (performance === "Speed") {
      perfPreview = { steps: 30, cfg: 5, sampler: "dpmpp_2m", scheduler: "sgm_uniform" };
    } else if (performance === "Lightning") {
      perfPreview = { steps: 12, cfg: 4, sampler: "dpmpp_2m", scheduler: "sgm_uniform" };
    }
  }
  if (isIdeogramModel && !customPerf) {
    perfPreview =
      IDEOGRAM_PERFORMANCE_PREVIEW[performance] ?? IDEOGRAM_PERFORMANCE_PREVIEW.Speed;
  }
  const seedRandom = studioSettings?.seed_random ?? true;
  const hasNegative = Boolean((settings.negative_prompt ?? "").trim());
  const perfHint = isIdeogramModel
    ? ideogramPerformanceHint(performance)
    : performanceHint(performance);

  const enableCustomSampling = () => {
    onChange({ performance: CUSTOM_PERFORMANCE });
  };

  const handlePerformanceChange = (perf: string) => {
    if (
      isCustomPerformance(perf) ||
      !isHiDreamO1DevCheckpoint(settings.model) ||
      !isGenerateFamilyMode(studioMode)
    ) {
      onChange({ performance: perf });
      return;
    }
    const patched = applyHiDreamO1DevAtSubmit(
      { ...settings, performance: perf },
      settings.model,
    );
    onChange({
      performance: perf,
      steps: patched.steps,
      cfg_scale: patched.cfg_scale,
      sampler: patched.sampler,
      scheduler: patched.scheduler,
      aspect_ratio: patched.aspect_ratio,
      width: patched.width,
      height: patched.height,
      negative_prompt: patched.negative_prompt,
      styles: patched.styles,
      denoise: patched.denoise,
      hidream_noise_scale: patched.hidream_noise_scale,
      hidream_s_noise: patched.hidream_s_noise,
      hidream_s_noise_end: patched.hidream_s_noise_end,
      hidream_noise_clip_std: patched.hidream_noise_clip_std,
      hidream_patch_seam_smoothing: patched.hidream_patch_seam_smoothing,
      hidream_reference_megapixels: patched.hidream_reference_megapixels,
      hidream_prompt_refinement: patched.hidream_prompt_refinement,
    });
  };

  const tabCtx = buildGenerationTabContext({
    studioMode,
    advancedMode,
    activeModelLabel,
    modelFamily: activeModelFamily,
    isQwenModel,
    showGenerateLikeSettings,
    showEditStrength,
    customPerf,
  });
  const show = (section: Parameters<typeof generationSectionVisible>[0]) =>
    generationSectionVisible(section, tabCtx);

  const setDensity = (density: "basic" | "advanced") => {
    setControlDensity(density);
    localStorage.setItem(GENERATION_DENSITY_KEY, density);
  };
  const saveCurrentPreset = () => {
    const name = window.prompt("Preset name", `Preset ${userPresets.length + 1}`)?.trim();
    if (!name) return;
    const preset: UserGenerationPreset = {
      name,
      settings: {
        performance: settings.performance,
        aspect_ratio: settings.aspect_ratio,
        width: settings.width,
        height: settings.height,
        image_number: settings.image_number,
        steps: settings.steps,
        cfg_scale: settings.cfg_scale,
        sampler: settings.sampler,
        scheduler: settings.scheduler,
      },
    };
    const next = [...userPresets.filter((item) => item.name !== name), preset];
    setUserPresets(next);
    localStorage.setItem(GENERATION_PRESETS_KEY, JSON.stringify(next));
  };
  const resetRunSettings = () => onChange({
    performance: "Lightning",
    aspect_ratio: "768x768",
    width: undefined,
    height: undefined,
    image_number: 1,
    seed: -1,
    steps: 20,
    cfg_scale: 3.5,
    sampler: undefined,
    scheduler: undefined,
  });

  return (
    <div className="space-y-2.5">
      {!show("upscalePanel") ? (
        <div className="sticky top-0 z-10 space-y-2 rounded-lg border border-dfui-border/60 bg-dfui-panel/95 p-2 shadow-sm backdrop-blur-md">
          <div className="flex items-center justify-between gap-2">
            <div className="min-w-0">
              <p className="truncate text-[10px] font-semibold text-dfui-fg" title={activeModelLabel}>{activeModelLabel || "Automatic model"}</p>
              <p className="truncate font-mono text-[9px] text-dfui-tertiary">
                {performance} · {activeAspect.replace("x", "×")} · {settings.image_number ?? 1} image{(settings.image_number ?? 1) === 1 ? "" : "s"} · seed {seedRandom ? "random" : settings.seed ?? -1}
              </p>
            </div>
            <button type="button" onClick={resetRunSettings} className="rounded p-1.5 text-dfui-muted hover:bg-dfui-surface hover:text-dfui-fg" title="Reset run settings" aria-label="Reset run settings">
              <RotateCcw size={13} />
            </button>
          </div>
          <div className="flex items-center gap-1">
            {advancedMode ? (["basic", "advanced"] as const).map((density) => (
              <button key={density} type="button" aria-pressed={controlDensity === density} onClick={() => setDensity(density)} className={`rounded px-2 py-1 text-[9px] font-semibold uppercase tracking-wide ${controlDensity === density ? "bg-dfui-accent/15 text-dfui-accent" : "text-dfui-muted hover:bg-dfui-surface"}`}>
                {density}
              </button>
            )) : null}
            <select aria-label="Apply saved generation preset" defaultValue="" onChange={(event) => {
              const preset = userPresets.find((item) => item.name === event.target.value);
              if (preset) onChange(preset.settings);
              event.target.value = "";
            }} className="df-select ml-auto min-w-0 max-w-32 px-1.5 py-1 text-[9px]">
              <option value="">Presets…</option>
              {userPresets.map((preset) => <option key={preset.name} value={preset.name}>{preset.name}</option>)}
            </select>
            <button type="button" onClick={saveCurrentPreset} className="rounded p-1.5 text-dfui-muted hover:bg-dfui-surface hover:text-dfui-accent" title="Save current generation preset" aria-label="Save current generation preset"><Save size={12} /></button>
          </div>
        </div>
      ) : null}
      {show("creativeTemplate") && creativeTemplates.length > 0 && (
        <SettingsSection
          title="Creative template"
          subtitle="Override the default pipeline bundle for this mode"
          defaultOpen={false}
        >
          <label className="block">
            <FieldLabel hint="Bundles model routing, defaults, and optional post-upscale chain">
              Template
            </FieldLabel>
            <select
              value={activeTemplateId}
              onChange={(e) => {
                const id = e.target.value;
                const picked = creativeTemplates.find((t) => t.id === id);
                onChange({
                  template_id: id,
                  post_upscale: picked?.post_upscale,
                  post_upscale_enabled: Boolean(picked?.post_upscale),
                });
              }}
              className="df-select mt-1 w-full px-2.5 py-2 text-xs"
            >
              {creativeTemplates.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.label}
                  {t.post_upscale ? ` · +${t.post_upscale}` : ""}
                </option>
              ))}
            </select>
          </label>
        </SettingsSection>
      )}
      {show("upscalePanel") && (
        <>
          <UltimateSDUpscalePanel settings={settings} onChange={onChange} />
          <div className="mt-2">
            <AutoEnhancePanel
              settings={settings}
              sourceImage={settings.upscale_image ?? settings.input_image}
              onChange={onChange}
              onAutoEnhance={onAutoEnhance}
              onVaryImage={onVaryImage}
            />
          </div>
        </>
      )}
      {show("editFamilyPanel") && (
        <EditFamilySettingsPanel
          settings={settings}
          onChange={onChange}
          isInpaint={isInpaint}
          routedModelLabel={routedModelLabel}
          editRouteSubtitle={editRouteSubtitle}
          showEditStrength={showEditStrength}
          advancedMode={advancedMode}
          modelGallery={modelGallery}
        />
      )}
      {show("toolboxPanel") && (
        <CreativeToolboxPanel
          settings={settings}
          onChange={onChange}
          modelGallery={modelGallery}
          onInstallCompanionItems={onInstallCompanionItems}
        />
      )}

      {show("performance") && (
      <SettingsSection
        title="Performance & size"
        subtitle={
          isGenerateFamilyMode(studioMode)
            ? "Preset controls steps / CFG — Custom unlocks manual sampling"
            : "Preset for edit / inpaint — advanced unlocks manual sampling"
        }
        defaultOpen
        changed={performance !== "Lightning" || activeAspect !== "768x768" || (settings.image_number ?? 1) !== 1}
        onReset={() => onChange({ performance: "Lightning", aspect_ratio: "768x768", width: undefined, height: undefined, image_number: 1 })}
      >
        {tabCtx.isModernModel ? <p className="rounded-md border border-df-blue/20 bg-df-blue/5 px-2 py-1.5 text-[9px] leading-snug text-dfui-tertiary">{activeModelFamily || activeModelLabel} uses modern guidance; unsupported negative-prompt and CLIP-skip controls are hidden.</p> : null}
        {MODE_AUTO_SUMMARY[studioMode] && (
          <p className="rounded-md border border-[#4a4a4a]/50 bg-[#353535]/80 px-2 py-1.5 font-mono text-[9px] leading-snug text-dfui-tertiary">
            {MODE_AUTO_SUMMARY[studioMode]}
          </p>
        )}
        <label className="block">
          <FieldLabel hint={perfHint}>
            Performance
          </FieldLabel>
          <select
            value={performance}
            onChange={(e) => handlePerformanceChange(e.target.value)}
            className="df-select mt-1 w-full px-2.5 py-2 text-xs"
          >
            {performances.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </label>
        {!customPerf && perfPreview && (
          <p className="rounded-md border border-dfui-border/35 bg-dfui-panel/50 px-2 py-1.5 font-mono text-[10px] text-dfui-tertiary">
            {perfPreview.steps} steps · CFG {perfPreview.cfg} · {perfPreview.sampler} ·{" "}
            {perfPreview.scheduler}
          </p>
        )}
        {!customPerf && (
          <button
            type="button"
            onClick={enableCustomSampling}
            className="text-[10px] text-dfui-accent hover:underline"
          >
            Switch to Custom… for manual steps / CFG / sampler
          </button>
        )}

        {show("aspectRatio") && (
          <>
            <FieldLabel hint="SDXL-trained sizes through 1344px; HiDream-O1 Dev supports up to 2048×2048. Portrait / square / landscape groups match Fooocus.">
              Aspect ratio
            </FieldLabel>
            <div className="space-y-2">
              {(["portrait", "square", "landscape"] as const).map((group) => {
                const items = aspectGroups[group];
                if (!items.length) return null;
                return (
                  <div key={group}>
                    <p className="mb-1 text-[9px] font-medium uppercase tracking-wider text-dfui-tertiary">
                      {ASPECT_GROUP_LABELS[group]}
                    </p>
                    <div className="flex flex-wrap gap-1">
                      {items.map((preset) => {
                        const label = typeof preset === "string" ? preset : "";
                        if (!label) return null;
                        return (
                        <button
                          key={label}
                          type="button"
                          data-active={activeAspect === label}
                          onClick={() => onChange({ aspect_ratio: label })}
                          className={`rounded-md border px-2 py-1 font-mono text-[10px] transition ${ASPECT_GROUP_ACCENT[group]}`}
                        >
                          {label.replace("x", "×")}
                        </button>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
            {controlDensity === "advanced" ? (
              <div className="rounded-md border border-dfui-border/40 bg-dfui-bg/30 p-2">
                <div className="mb-1.5 flex items-center justify-between gap-2">
                  <label className="flex items-center gap-1.5 text-[10px] text-dfui-muted">
                    <input type="checkbox" checked={customSize} onChange={(event) => setCustomSize(event.target.checked)} className="accent-dfui-accent" /> Custom size
                  </label>
                  <div className="flex items-center gap-1">
                    <button type="button" onClick={() => setLockAspect((value) => !value)} aria-pressed={lockAspect} className={`rounded px-1.5 py-0.5 text-[9px] ${lockAspect ? "bg-dfui-accent/15 text-dfui-accent" : "text-dfui-muted"}`}>Lock ratio</button>
                    <button type="button" onClick={() => onChange({ width: currentHeight, height: currentWidth, aspect_ratio: `${currentHeight}x${currentWidth}` })} className="rounded p-1 text-dfui-muted hover:bg-dfui-surface hover:text-dfui-fg" title="Swap width and height" aria-label="Swap width and height"><Shuffle size={11} /></button>
                  </div>
                </div>
                {customSize ? (
                  <div className="grid grid-cols-2 gap-2">
                    <label className="text-[9px] text-dfui-muted">Width
                      <input type="number" min={256} max={4096} step={64} value={currentWidth} onChange={(event) => {
                        const width = boundedNumber(event.target.value, 256, 4096, currentWidth);
                        const height = lockAspect ? Math.max(256, Math.round((width * currentHeight / currentWidth) / 64) * 64) : currentHeight;
                        onChange({ width, height, aspect_ratio: `${width}x${height}` });
                      }} className="df-input mt-1 w-full px-2 py-1 font-mono text-[10px]" />
                    </label>
                    <label className="text-[9px] text-dfui-muted">Height
                      <input type="number" min={256} max={4096} step={64} value={currentHeight} onChange={(event) => {
                        const height = boundedNumber(event.target.value, 256, 4096, currentHeight);
                        const width = lockAspect ? Math.max(256, Math.round((height * currentWidth / currentHeight) / 64) * 64) : currentWidth;
                        onChange({ width, height, aspect_ratio: `${width}x${height}` });
                      }} className="df-input mt-1 w-full px-2 py-1 font-mono text-[10px]" />
                    </label>
                  </div>
                ) : null}
              </div>
            ) : null}
          </>
        )}

        {show("imageNumber") && (
          <label className="block">
            <FieldLabel>Image number — {settings.image_number ?? 1}</FieldLabel>
            <input
              type="range"
              min={1}
              max={imageNumberMax}
              value={settings.image_number ?? 1}
              onChange={(e) => onChange({ image_number: Number(e.target.value) })}
              className="mt-1 w-full accent-dfui-accent"
            />
          </label>
        )}

        {show("autoNegative") && (
          <label className="flex items-center gap-2 text-[11px] text-dfui-muted">
            <input
              type="checkbox"
              checked={settings.auto_negative_prompt ?? false}
              onChange={(e) => onChange({ auto_negative_prompt: e.target.checked })}
              className="accent-dfui-accent"
            />
            Auto negative prompt (RuinedFooocus-style)
          </label>
        )}
      </SettingsSection>
      )}

      {show("promptSeed") && (
      <SettingsSection
        title="Prompt & seed"
        subtitle="Guidance scale (CFG) lives under Custom sampling"
        defaultOpen={hasNegative || !seedRandom}
        changed={hasNegative || !seedRandom}
        onReset={() => {
          onChange({ negative_prompt: "", seed: -1 });
          if (onSaveStudioSettings) void onSaveStudioSettings({ seed_random: true });
        }}
      >
        {!tabCtx.isModernModel && (
          <label className="block">
            <FieldLabel hint="Leave empty when auto negative is on. At low CFG, negatives have little effect.">
              Negative prompt
            </FieldLabel>
            <textarea
              value={settings.negative_prompt ?? ""}
              onChange={(e) => onChange({ negative_prompt: e.target.value })}
              rows={2}
              placeholder="Things to avoid in the image…"
              className="df-input mt-1 w-full resize-none px-2.5 py-1.5 text-xs"
            />
          </label>
        )}
        <div className="flex flex-wrap items-end gap-2">
          <label className="flex flex-1 min-w-[120px] flex-col gap-1">
            <FieldLabel hint="−1 = random each run (Fooocus default).">
              Seed
            </FieldLabel>
            <input
              type="number"
              disabled={seedRandom}
              value={seedRandom ? -1 : (settings.seed ?? -1)}
              onChange={(e) => onChange({ seed: Number(e.target.value) })}
              className="df-input w-full px-2.5 py-1.5 font-mono text-xs disabled:opacity-50"
            />
          </label>
          {onSaveStudioSettings && studioSettings && (
            <label className="flex items-center gap-1.5 pb-1.5 text-[11px] text-dfui-muted">
              <input
                type="checkbox"
                checked={seedRandom}
                onChange={(e) => {
                  const random = e.target.checked;
                  void onSaveStudioSettings({ seed_random: random });
                  if (random) onChange({ seed: -1 });
                }}
                className="accent-dfui-accent"
              />
              Random
            </label>
          )}
        </div>
        <div className="flex flex-wrap gap-1">
          <button type="button" onClick={() => {
            const seed = Math.floor(Math.random() * 2_147_483_647);
            void onSaveStudioSettings?.({ seed_random: false });
            onChange({ seed });
          }} className="inline-flex items-center gap-1 rounded border border-dfui-border/50 px-2 py-1 text-[9px] text-dfui-muted hover:text-dfui-fg"><Dices size={11} /> Randomize</button>
          <button type="button" disabled={seedRandom} onClick={() => void navigator.clipboard.writeText(String(settings.seed ?? -1))} className="inline-flex items-center gap-1 rounded border border-dfui-border/50 px-2 py-1 text-[9px] text-dfui-muted hover:text-dfui-fg disabled:opacity-40"><Copy size={11} /> Copy</button>
          <button type="button" onClick={() => void navigator.clipboard.readText().then((value) => {
            const seed = boundedNumber(value, 0, 2_147_483_647, -1);
            if (seed >= 0) {
              void onSaveStudioSettings?.({ seed_random: false });
              onChange({ seed });
            }
          })} className="inline-flex items-center gap-1 rounded border border-dfui-border/50 px-2 py-1 text-[9px] text-dfui-muted hover:text-dfui-fg"><ClipboardPaste size={11} /> Paste</button>
        </div>
      </SettingsSection>
      )}

      {show("customSampling") && controlDensity === "advanced" && (
        <SettingsSection
          title="Custom sampling"
          subtitle={
            customPerf
              ? "RuinedFooocus: steps, CFG, sampler, scheduler"
              : "Select Custom… in Performance to unlock"
          }
          defaultOpen={customPerf}
          changed={customPerf}
          onReset={() => onChange({ performance: "Lightning", steps: 20, cfg_scale: 3.5, sampler: undefined, scheduler: undefined, clip_skip: undefined })}
        >
          {!customPerf ? (
            <div className="space-y-2">
              <p className="text-[10px] leading-snug text-dfui-tertiary">
                Presets control steps and guidance. Choose{" "}
                <strong className="font-medium text-dfui-secondary">Custom…</strong> in Performance
                to edit sampler settings manually (recommended for Flux, Z-Image-Turbo, etc.).
              </p>
              <button
                type="button"
                onClick={enableCustomSampling}
                className="rounded-md border border-dfui-accent/40 bg-dfui-accent/10 px-2.5 py-1.5 text-[10px] font-medium text-dfui-accent hover:bg-dfui-accent/20"
              >
                Enable Custom sampling
              </button>
            </div>
          ) : (
            <>
              <label className="block">
                <FieldLabel hint="Guidance scale — prompt adherence (CFG).">
                  Guidance scale (CFG) — {settings.cfg_scale ?? 4}
                </FieldLabel>
                <div className="mt-1 flex items-center gap-2"><input type="range" min={1} max={12} step={0.1} value={settings.cfg_scale ?? 4} onChange={(e) => onChange({ performance: CUSTOM_PERFORMANCE, cfg_scale: Number(e.target.value) })} className="min-w-0 flex-1 accent-dfui-accent" /><input aria-label="Exact CFG value" type="number" min={1} max={12} step={0.1} value={settings.cfg_scale ?? 4} onChange={(e) => onChange({ performance: CUSTOM_PERFORMANCE, cfg_scale: boundedNumber(e.target.value, 1, 12, 4) })} className="df-input w-16 px-1.5 py-1 font-mono text-[10px]" /></div>
              </label>
              <label className="block">
                <FieldLabel>Steps — {settings.steps ?? 20}</FieldLabel>
                <div className="mt-1 flex items-center gap-2"><input type="range" min={4} max={60} value={settings.steps ?? 20} onChange={(e) => onChange({ performance: CUSTOM_PERFORMANCE, steps: Number(e.target.value) })} className="min-w-0 flex-1 accent-dfui-accent" /><input aria-label="Exact step count" type="number" min={4} max={60} value={settings.steps ?? 20} onChange={(e) => onChange({ performance: CUSTOM_PERFORMANCE, steps: boundedNumber(e.target.value, 4, 60, 20) })} className="df-input w-16 px-1.5 py-1 font-mono text-[10px]" /></div>
              </label>
              <div className="grid grid-cols-2 gap-2">
                <label className="block">
                  <FieldLabel>Sampler</FieldLabel>
                  <select
                    value={settings.sampler ?? "dpmpp_2m_sde_gpu"}
                    onChange={(e) =>
                      onChange({ performance: CUSTOM_PERFORMANCE, sampler: e.target.value })
                    }
                    className="df-select mt-1 w-full px-2 py-1.5 text-[10px]"
                  >
                    {(uiDefaults?.samplers ?? ["dpmpp_2m_sde_gpu"]).map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block">
                  <FieldLabel>Scheduler</FieldLabel>
                  <select
                    value={settings.scheduler ?? "karras"}
                    onChange={(e) =>
                      onChange({ performance: CUSTOM_PERFORMANCE, scheduler: e.target.value })
                    }
                    className="df-select mt-1 w-full px-2 py-1.5 text-[10px]"
                  >
                    {(uiDefaults?.schedulers ?? ["karras"]).map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              {!tabCtx.isModernModel && (
                <label className="block">
                  <FieldLabel>CLIP skip</FieldLabel>
                  <input
                    type="number"
                    min={1}
                    max={12}
                    value={settings.clip_skip ?? studioSettings?.clip_skip ?? 1}
                    onChange={(e) =>
                      onChange({
                        performance: CUSTOM_PERFORMANCE,
                        clip_skip: Number(e.target.value),
                      })
                    }
                    className="df-input mt-1 w-full px-2.5 py-1.5 font-mono text-xs"
                  />
                </label>
              )}
            </>
          )}
        </SettingsSection>
      )}

      {show("controlNet") && controlDensity === "advanced" && (
        <SettingsSection title="ControlNet" subtitle="Structure / pose guidance" defaultOpen={false}>
          <label className="block">
            <FieldLabel>Preset</FieldLabel>
            <select
              value={settings.cn_selection ?? "None"}
              onChange={(e) => onChange({ cn_selection: e.target.value })}
              className="df-select mt-1 w-full px-2.5 py-2 text-xs"
            >
              <option value="None">None</option>
              {(uiDefaults?.controlnet_presets ?? []).map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
              <option value="Custom...">Custom…</option>
            </select>
          </label>
          {(settings.cn_selection === "Custom..." || settings.input_image) && (
            <label className="block">
              <FieldLabel>Input image path</FieldLabel>
              <input
                value={settings.input_image ?? ""}
                onChange={(e) => onChange({ input_image: e.target.value })}
                placeholder="/path/to/control image.png"
                className="df-input mt-1 w-full px-2.5 py-1.5 font-mono text-[10px]"
              />
            </label>
          )}
        </SettingsSection>
      )}

      {show("qwen") && controlDensity === "advanced" && (
        <SettingsSection title="Qwen Image" defaultOpen={false}>
          <label className="block">
            <FieldLabel>Edit graph</FieldLabel>
            <select
              value={settings.qwen_edit_mode ?? "auto"}
              onChange={(e) =>
                onChange({
                  qwen_edit_mode: e.target.value as GenerationSettings["qwen_edit_mode"],
                })
              }
              className="df-select mt-1 w-full px-2.5 py-2 text-xs"
            >
              <option value="auto">Auto (Plus when extra references)</option>
              <option value="single">Single (TextEncodeQwenImageEdit)</option>
              <option value="plus">Plus (TextEncodeQwenImageEditPlus)</option>
              <option value="raw_plus">
                Raw Plus (preserve resolution — ReferenceLatent)
              </option>
              <option value="preserve_resolution">
                Preserve resolution (alias of Raw Plus)
              </option>
              <option value="lightning_4step">
                Lightning 4-step (Fast edit)
              </option>
            </select>
          </label>
          <label className="mt-2 flex items-center gap-2 text-xs text-dfui-muted">
            <input
              type="checkbox"
              checked={Boolean(settings.qwen_preserve_resolution)}
              onChange={(e) =>
                onChange({
                  qwen_preserve_resolution: e.target.checked,
                  qwen_edit_mode: e.target.checked
                    ? settings.qwen_edit_mode === "single"
                      ? "raw_plus"
                      : settings.qwen_edit_mode
                    : settings.qwen_edit_mode,
                })
              }
              className="accent-dfui-accent"
            />
            Preserve source pixel layout (raw latent path)
          </label>
          <label className="block">
            <FieldLabel>Preserve megapixels (raw path)</FieldLabel>
            <input
              type="number"
              min={0}
              max={16}
              step={0.1}
              placeholder="auto (source size)"
              value={settings.qwen_preserve_megapixels ?? ""}
              onChange={(e) => {
                const raw = e.target.value.trim();
                onChange({
                  qwen_preserve_megapixels: raw === "" ? undefined : Number(raw),
                });
              }}
              className="df-input mt-1 w-full px-2.5 py-1.5 font-mono text-xs"
            />
          </label>
          <label className="block">
            <FieldLabel>AuraFlow shift — {settings.qwen_image_shift ?? 3.1}</FieldLabel>
            <input
              type="range"
              min={1}
              max={6}
              step={0.1}
              value={settings.qwen_image_shift ?? 3.1}
              onChange={(e) => onChange({ qwen_image_shift: Number(e.target.value) })}
              className="mt-1 w-full accent-dfui-accent"
            />
          </label>
          <label className="block">
            <FieldLabel>Edit scale (megapixels)</FieldLabel>
            <input
              type="number"
              min={0}
              max={4}
              step={0.05}
              placeholder="auto"
              value={settings.qwen_scale_megapixels ?? ""}
              onChange={(e) => {
                const raw = e.target.value.trim();
                onChange({
                  qwen_scale_megapixels: raw === "" ? undefined : Number(raw),
                });
              }}
              className="df-input mt-1 w-full px-2.5 py-1.5 font-mono text-xs"
            />
          </label>
        </SettingsSection>
      )}

      {show("promptHelpers") && controlDensity === "advanced" && (
      <SettingsSection title="Prompt helpers" subtitle="Subject, lighting, camera" defaultOpen={false}>
        <label className="block">
          <FieldLabel>Subject</FieldLabel>
          <input
            value={settings.subject ?? ""}
            onChange={(e) => onChange({ subject: e.target.value })}
            className="df-input mt-1 w-full px-2.5 py-1.5 text-xs"
          />
        </label>
        <label className="block">
          <FieldLabel>Lighting</FieldLabel>
          <input
            value={settings.lighting ?? ""}
            onChange={(e) => onChange({ lighting: e.target.value })}
            className="df-input mt-1 w-full px-2.5 py-1.5 text-xs"
          />
        </label>
        <label className="block">
          <FieldLabel>Camera</FieldLabel>
          <input
            value={settings.camera ?? ""}
            onChange={(e) => onChange({ camera: e.target.value })}
            className="df-input mt-1 w-full px-2.5 py-1.5 text-xs"
          />
        </label>
      </SettingsSection>
      )}

    </div>
  );
}
