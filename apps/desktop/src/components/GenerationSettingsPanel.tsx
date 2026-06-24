import { ChevronDown, ChevronRight } from "lucide-react";
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
import type { GenerationSettings, UiDefaults, ModelGalleryItem } from "../lib/tauri-api";
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
import { UltimateSDUpscalePanel } from "./UltimateSDUpscalePanel";

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
  children,
}: {
  title: string;
  subtitle?: string;
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section className="rounded-lg border border-dfui-border/45 bg-dfui-bg/25">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 px-2.5 py-2 text-left"
      >
        {open ? (
          <ChevronDown size={14} className="shrink-0 text-dfui-muted" />
        ) : (
          <ChevronRight size={14} className="shrink-0 text-dfui-muted" />
        )}
        <span className="min-w-0 flex-1">
          <span className="block text-[10px] font-semibold uppercase tracking-wide text-dfui-muted">
            {title}
          </span>
          {subtitle && (
            <span className="block text-[10px] leading-snug text-dfui-tertiary">{subtitle}</span>
          )}
        </span>
      </button>
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
}: Props) {
  const [creativeTemplates, setCreativeTemplates] = useState<CreativeTemplateSummary[]>([]);

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
  const activeModelLower = activeModelLabel.toLowerCase();
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
    if (performance === "Quality") {
      perfPreview = { steps: 50, cfg: 5, sampler: "euler", scheduler: "normal" };
    } else if (performance === "Speed") {
      perfPreview = { steps: 28, cfg: 1, sampler: "euler", scheduler: "normal" };
    } else if (performance === "Lightning") {
      perfPreview = { steps: 16, cfg: 1, sampler: "euler", scheduler: "normal" };
    }
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

  const tabCtx = buildGenerationTabContext({
    studioMode,
    advancedMode,
    activeModelLabel,
    isQwenModel,
    showGenerateLikeSettings,
    showEditStrength,
    customPerf,
  });
  const show = (section: Parameters<typeof generationSectionVisible>[0]) =>
    generationSectionVisible(section, tabCtx);

  return (
    <div className="space-y-2.5">
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
        <UltimateSDUpscalePanel settings={settings} onChange={onChange} />
      )}
      {show("editFamilyPanel") && (
        <EditFamilySettingsPanel
          settings={settings}
          onChange={onChange}
          isInpaint={isInpaint}
          routedModelLabel={routedModelLabel}
          editRouteSubtitle={editRouteSubtitle}
          showEditStrength={showEditStrength}
          modelGallery={modelGallery}
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
      >
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
            onChange={(e) => onChange({ performance: e.target.value })}
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
            <FieldLabel hint="SDXL-trained sizes work best; portrait / square / landscape groups match Fooocus.">
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
      </SettingsSection>
      )}

      {show("customSampling") && (
        <SettingsSection
          title="Custom sampling"
          subtitle={
            customPerf
              ? "RuinedFooocus: steps, CFG, sampler, scheduler"
              : "Select Custom… in Performance to unlock"
          }
          defaultOpen={customPerf}
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
                <input
                  type="range"
                  min={1}
                  max={12}
                  step={0.1}
                  value={settings.cfg_scale ?? 4}
                  onChange={(e) =>
                    onChange({ performance: CUSTOM_PERFORMANCE, cfg_scale: Number(e.target.value) })
                  }
                  className="mt-1 w-full accent-dfui-accent"
                />
              </label>
              <label className="block">
                <FieldLabel>Steps — {settings.steps ?? 20}</FieldLabel>
                <input
                  type="range"
                  min={4}
                  max={60}
                  value={settings.steps ?? 20}
                  onChange={(e) =>
                    onChange({ performance: CUSTOM_PERFORMANCE, steps: Number(e.target.value) })
                  }
                  className="mt-1 w-full accent-dfui-accent"
                />
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

      {show("controlNet") && (
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

      {show("qwen") && (
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
            </select>
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

      {show("promptHelpers") && (
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

      {show("hardware") && (
      <SettingsSection
        title="Hardware & limits"
        subtitle="VRAM tier and batch limits"
        defaultOpen={false}
      >
        <label className="block">
          <FieldLabel hint="Changing this affects ComfyUI launch flags; restart the GPU engine after switching profiles.">
            VRAM profile
          </FieldLabel>
          <select
            value={settings.vram_profile ?? "auto"}
            onChange={(e) =>
              onChange({
                vram_profile: e.target.value as GenerationSettings["vram_profile"],
              })
            }
            className="df-select mt-1 w-full px-2.5 py-2 text-xs"
          >
            <option value="auto">auto (detect hardware)</option>
            <optgroup label="Apple Silicon (unified memory)">
              <option value="mps_24gb">Mac — 24 GB tier</option>
              <option value="mps_16gb">Mac — 16 GB tier</option>
              <option value="mps_8gb">Mac — 8 GB tier</option>
              <option value="mps_4gb">Mac — 4 GB tier (tight)</option>
            </optgroup>
            <optgroup label="NVIDIA / discrete GPU">
              <option value="16gb">16 GB VRAM — recommended / reserve 1 GB</option>
              <option value="8gb">8 GB VRAM — low VRAM / reserve 0.5 GB</option>
              <option value="5gb">5 GB VRAM (tight) — low VRAM / reserve 0.5 GB</option>
              <option value="no_gpu">CPU only — very slow, no GPU</option>
            </optgroup>
          </select>
        </label>
        {onSaveStudioSettings && studioSettings && (
          <>
            <label className="block">
              <FieldLabel>Max images per run</FieldLabel>
              <input
                type="number"
                min={1}
                max={50}
                defaultValue={studioSettings.image_number_max ?? imageNumberMax}
                onBlur={(e) =>
                  void onSaveStudioSettings({
                    image_number_max: Number(e.target.value),
                  })
                }
                className="df-input mt-1 w-full px-2.5 py-1.5 font-mono text-xs"
              />
            </label>
            <div className="grid grid-cols-2 gap-2">
              <label className="block">
                <FieldLabel>LoRA weight min</FieldLabel>
                <input
                  type="number"
                  step={0.05}
                  defaultValue={studioSettings.lora_min ?? 0}
                  onBlur={(e) =>
                    void onSaveStudioSettings({ lora_min: Number(e.target.value) })
                  }
                  className="df-input mt-1 w-full font-mono text-[10px]"
                />
              </label>
              <label className="block">
                <FieldLabel>LoRA weight max</FieldLabel>
                <input
                  type="number"
                  step={0.05}
                  defaultValue={studioSettings.lora_max ?? 2}
                  onBlur={(e) =>
                    void onSaveStudioSettings({ lora_max: Number(e.target.value) })
                  }
                  className="df-input mt-1 w-full font-mono text-[10px]"
                />
              </label>
            </div>
          </>
        )}
        <p className="text-[10px] leading-snug text-dfui-tertiary">
          Global hardware limits — same profile across all modes. Models, LoRAs, and styles live on
          sibling inspector tabs.
        </p>
      </SettingsSection>
      )}
    </div>
  );
}
