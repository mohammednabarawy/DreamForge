import { Boxes, Palette, SlidersHorizontal, Globe } from "lucide-react";
import { useMemo, useState } from "react";
import type { StyleGroup } from "../lib/inventory";
import { modelMatches } from "../lib/model-selection";
import type {
  GenerationSettings,
  LoraGalleryItem,
  ModelGalleryItem,
  UiDefaults,
} from "../lib/tauri-api";
import { StyleThumbnailGrid } from "./StyleThumbnailGrid";
import { ThumbnailGallery, type GalleryTile } from "./ThumbnailGallery";
import { MarketplaceTab } from "./MarketplaceTab";
import { LoraStackPanel } from "./LoraStackPanel";
import type { StudioSettings } from "../lib/studioBridge";

type Tab = "discover" | "models" | "styles" | "settings";

type Props = {
  settings: GenerationSettings;
  onChange: (patch: Partial<GenerationSettings>) => void;
  modelGallery: ModelGalleryItem[];
  loraGallery: LoraGalleryItem[];
  modelFilter: string;
  onModelFilterChange: (value: string) => void;
  loraFilter: string;
  onLoraFilterChange: (value: string) => void;
  lockFamilyDefaults: boolean;
  onLockFamilyDefaultsChange: (value: boolean) => void;
  profileHints: string[];
  galleryLoading?: boolean;
  onSelectModel: (item: ModelGalleryItem) => void;
  onToggleLora: (name: string) => void;
  styleGroups: StyleGroup[];
  aspectPresets: string[];
  uiDefaults: UiDefaults | null;
  onRefreshInventory: () => void;
  activeModelLabel: string;
  onUseCaseChange: (useCase: string) => void;
  modelDependencies?: { missing: Array<{ id?: string; relative?: string; note?: string }>; ready: boolean };
  companionDownloadBusy?: boolean;
  onDownloadCompanions?: () => void;
  onRefreshModelDependencies?: () => void;
  studioSettings?: StudioSettings | null;
  onSaveStudioSettings?: (patch: StudioSettings) => void | Promise<void>;
  imageNumberMax?: number;
};

const CUSTOM_PERF = "Custom...";

export function InspectorPanel({
  settings,
  onChange,
  modelGallery,
  loraGallery,
  modelFilter,
  onModelFilterChange,
  loraFilter,
  onLoraFilterChange,
  lockFamilyDefaults,
  onLockFamilyDefaultsChange,
  profileHints,
  galleryLoading,
  onSelectModel,
  onToggleLora,
  styleGroups,
  aspectPresets,
  uiDefaults,
  onRefreshInventory,
  activeModelLabel,
  onUseCaseChange,
  modelDependencies,
  companionDownloadBusy,
  onDownloadCompanions,
  onRefreshModelDependencies,
  studioSettings,
  onSaveStudioSettings,
  imageNumberMax = 8,
}: Props) {
  const [tab, setTab] = useState<Tab>("models");
  const [styleFilter, setStyleFilter] = useState("");

  const performances = uiDefaults?.performances ?? [
    "Speed",
    "Quality",
    "Extreme Speed",
    CUSTOM_PERF,
  ];
  const isCustomPerf =
    (settings.performance ?? "Speed") === CUSTOM_PERF ||
    settings.performance === "Custom";

  const selectedCount = (settings.styles ?? []).length;
  const activeLoras = settings.lora ?? [];

  const modelTiles: GalleryTile[] = useMemo(
    () =>
      modelGallery.map((m) => ({
        key: `${m.category}:${m.relative_path}`,
        value: `${m.category}:${m.relative_path}`,
        label: PathLabel(m.caption),
        sublabel: m.family,
        thumbnailPath: m.thumbnail_path,
        badge: m.category !== "checkpoints" ? m.category : undefined,
        selected: modelMatches(m, settings.model),
      })),
    [modelGallery, settings.model],
  );

  const loraTiles: GalleryTile[] = useMemo(
    () =>
      loraGallery.map((l) => ({
        key: l.relative_path ?? l.name,
        value: l.relative_path ?? l.name,
        label: l.stem || l.name,
        sublabel:
          l.relative_path && l.relative_path !== l.name
            ? PathLabel(l.relative_path)
            : undefined,
        thumbnailPath: l.thumbnail_path,
        selected: activeLoras.some((e) =>
          e.startsWith(`${l.relative_path ?? l.name}:`),
        ),
      })),
    [loraGallery, activeLoras],
  );

  const toggleStyle = (styleId: string) => {
    const set = new Set(settings.styles ?? []);
    if (set.has(styleId)) set.delete(styleId);
    else set.add(styleId);
    onChange({ styles: [...set] });
  };

  const tabs: { id: Tab; label: string; icon: typeof Boxes }[] = [
    { id: "discover", label: "Discover", icon: Globe },
    { id: "models", label: "Models", icon: Boxes },
    { id: "styles", label: "Styles", icon: Palette },
    { id: "settings", label: "Settings", icon: SlidersHorizontal },
  ];

  return (
    <aside className="flex h-full min-w-0 flex-col glass-panel rounded-none border-y-0 border-r-0">
      <div className="flex gap-1.5 border-b border-dfui-border/40 p-2 bg-dfui-panel/40 backdrop-blur-md">
        {tabs.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            type="button"
            onClick={() => setTab(id)}
            className={`flex flex-1 items-center justify-center gap-1.5 py-2 px-3 text-xs font-medium rounded-lg transition-all duration-200 ${
              tab === id ? "df-tab-active" : "df-tab"
            }`}
          >
            <Icon size={14} />
            {label}
            {id === "styles" && selectedCount > 0 && (
              <span className="rounded-full bg-dfui-accent/20 px-1.5 font-mono text-[9px] text-dfui-accent">
                {selectedCount}
              </span>
            )}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto p-3 text-sm">
        {tab === "discover" && (
          <MarketplaceTab
            civitaiApiKey={settings.civitai_api_key ?? ""}
            onApiKeyChange={(key) => onChange({ civitai_api_key: key })}
            onRefreshInventory={onRefreshInventory}
          />
        )}

        {tab === "models" && (
          <div className="space-y-3">
            <label className="flex items-center gap-2 text-[11px] text-dfui-muted">
              <input
                type="checkbox"
                checked={lockFamilyDefaults}
                onChange={(e) => onLockFamilyDefaultsChange(e.target.checked)}
                className="accent-dfui-accent"
              />
              Apply model family defaults (like web UI)
            </label>

            <div className="rounded-lg border border-dfui-accent/25 bg-dfui-accent/5 px-2.5 py-2">
              <p className="text-[10px] uppercase tracking-wide text-dfui-muted">
                Active model
              </p>
              <p className="truncate font-mono text-xs text-dfui-fg">
                {activeModelLabel}
              </p>
              {modelDependencies && !modelDependencies.ready && (
                <div className="mt-2 space-y-1.5 border-t border-dfui-border/30 pt-2">
                  <p className="text-[10px] text-amber-200/90">
                    Missing companion files ({modelDependencies.missing.length})
                  </p>
                  <ul className="max-h-24 space-y-0.5 overflow-y-auto text-[9px] text-dfui-tertiary">
                    {modelDependencies.missing.map((m) => (
                      <li key={m.id ?? m.relative} className="font-mono truncate">
                        {m.relative ?? m.id}
                      </li>
                    ))}
                  </ul>
                  <div className="flex flex-wrap gap-1.5 pt-0.5">
                    {onDownloadCompanions && (
                      <button
                        type="button"
                        disabled={companionDownloadBusy}
                        onClick={() => onDownloadCompanions()}
                        className="rounded-md border border-dfui-accent/40 bg-dfui-accent/10 px-2 py-1 text-[10px] font-medium text-dfui-accent hover:bg-dfui-accent/20 disabled:opacity-50"
                      >
                        {companionDownloadBusy ? "Downloading…" : "Download missing companions"}
                      </button>
                    )}
                    {onRefreshModelDependencies && (
                      <button
                        type="button"
                        onClick={() => onRefreshModelDependencies()}
                        className="rounded-md border border-dfui-border/50 px-2 py-1 text-[10px] text-dfui-muted hover:text-dfui-fg"
                      >
                        Recheck
                      </button>
                    )}
                  </div>
                </div>
              )}
            </div>

            <div>
              <div className="mb-1 flex items-center justify-between">
                <span className="text-xs text-dfui-muted">Base models</span>
                {galleryLoading && (
                  <span className="font-mono text-[9px] text-dfui-tertiary">
                    loading…
                  </span>
                )}
              </div>
              <input
                value={modelFilter}
                onChange={(e) => onModelFilterChange(e.target.value)}
                placeholder="Filter checkpoints, Flux, HiDream…"
                className="df-input mb-1.5 w-full px-2.5 py-1.5 text-xs"
              />
              <div className="max-h-[min(42vh,360px)] overflow-y-auto rounded-lg border border-dfui-border/50 bg-dfui-bg/25 p-1.5">
                <ThumbnailGallery
                  items={modelTiles}
                  columns={2}
                  emptyMessage="No models match. Add checkpoints under models/ or refresh."
                  onSelect={(key) => {
                    const item = modelGallery.find(
                      (m) => `${m.category}:${m.relative_path}` === key,
                    );
                    if (item) void onSelectModel(item);
                  }}
                />
              </div>
            </div>

            {profileHints.length > 0 && (
              <ul className="space-y-0.5 rounded-lg border border-dfui-accent/20 bg-dfui-accent/5 px-2 py-1.5">
                {profileHints.map((h) => (
                  <li
                    key={h}
                    className="text-[10px] leading-snug text-dfui-secondary"
                  >
                    {h}
                  </li>
                ))}
              </ul>
            )}

            <label className="block">
              <span className="text-xs text-dfui-muted">Use case recipe</span>
              <select
                value={settings.use_case ?? ""}
                onChange={(e) => onUseCaseChange(e.target.value)}
                className="df-select mt-1 w-full px-2.5 py-2 text-xs"
              >
                <option value="">—</option>
                <option value="product_ad">product_ad</option>
                <option value="cinematic_scene">cinematic_scene</option>
                <option value="social_post">social_post</option>
                <option value="arabic_poster">arabic_poster</option>
                <option value="fast_draft">fast_draft</option>
                <option value="image_edit">image_edit</option>
              </select>
            </label>

            <div>
              <span className="text-xs text-dfui-muted">LoRAs</span>
              <input
                value={loraFilter}
                onChange={(e) => onLoraFilterChange(e.target.value)}
                placeholder="Filter LoRAs…"
                className="df-input mt-1 mb-1.5 w-full px-2.5 py-1.5 text-xs"
              />
              <div className="max-h-[min(28vh,220px)] overflow-y-auto rounded-lg border border-dfui-border/50 bg-dfui-bg/25 p-1.5">
                <ThumbnailGallery
                  items={loraTiles}
                  columns={3}
                  multiSelect
                  emptyMessage="No LoRAs found."
                  onSelect={(name) => onToggleLora(name)}
                />
              </div>
              <LoraStackPanel
                lora={activeLoras}
                loraMin={studioSettings?.lora_min}
                loraMax={studioSettings?.lora_max}
                onChange={(lora) => onChange({ lora })}
              />
              {activeLoras.length > 0 && (
                <button
                  type="button"
                  className="mt-1 text-[10px] text-dfui-tertiary hover:text-dfui-fg"
                  onClick={() => onChange({ lora: [] })}
                >
                  Clear {activeLoras.length} LoRA
                  {activeLoras.length === 1 ? "" : "s"}
                </button>
              )}
            </div>
          </div>
        )}

        {tab === "styles" && (
          <StyleThumbnailGrid
            groups={styleGroups}
            selected={settings.styles ?? []}
            filter={styleFilter}
            onFilterChange={setStyleFilter}
            onToggle={toggleStyle}
          />
        )}

        {tab === "settings" && (
          <div className="space-y-3">
            <label className="block">
              <span className="text-xs text-dfui-muted">Performance (DreamForge)</span>
              <select
                value={settings.performance ?? "Speed"}
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
            <label className="block">
              <span className="text-xs text-dfui-muted">VRAM profile</span>
              <select
                value={settings.vram_profile ?? "auto"}
                onChange={(e) =>
                  onChange({
                    vram_profile: e.target.value as GenerationSettings["vram_profile"],
                  })
                }
                className="df-select mt-1 w-full px-2.5 py-2 text-xs"
              >
                <option value="auto">auto</option>
                <option value="16gb">16 GB (RTX 5060 Ti)</option>
                <option value="8gb">8 GB</option>
                <option value="5gb">5 GB</option>
              </select>
            </label>
            <label className="block">
              <span className="text-xs text-dfui-muted">Aspect ratio</span>
              <select
                value={settings.aspect_ratio ?? "1024x1024"}
                onChange={(e) => onChange({ aspect_ratio: e.target.value })}
                className="df-select mt-1 w-full px-2.5 py-2 text-xs"
              >
                {aspectPresets.map((a) => (
                  <option key={a} value={a}>
                    {a}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="text-xs text-dfui-muted">
                Image count — {settings.image_number ?? 1}
              </span>
              <input
                type="range"
                min={1}
                max={imageNumberMax}
                value={settings.image_number ?? 1}
                onChange={(e) =>
                  onChange({ image_number: Number(e.target.value) })
                }
                className="mt-1 w-full accent-dfui-accent"
              />
            </label>
            <label className="flex items-center gap-2 text-[11px] text-dfui-muted">
              <input
                type="checkbox"
                checked={settings.auto_negative_prompt ?? false}
                onChange={(e) =>
                  onChange({ auto_negative_prompt: e.target.checked })
                }
                className="accent-dfui-accent"
              />
              Auto negative prompt (web UI)
            </label>
            <label className="block">
              <span className="text-xs text-dfui-muted">CLIP skip</span>
              <input
                type="number"
                min={1}
                max={12}
                value={settings.clip_skip ?? studioSettings?.clip_skip ?? 1}
                onChange={(e) =>
                  onChange({ clip_skip: Number(e.target.value) })
                }
                className="df-input mt-1 w-full px-2.5 py-1.5 font-mono text-xs"
              />
            </label>
            {onSaveStudioSettings && studioSettings && (
              <div className="space-y-2 rounded-lg border border-dfui-border/40 p-2">
                <p className="text-[10px] font-medium uppercase tracking-wide text-dfui-muted">
                  Paths (saved to config)
                </p>
                <label className="block">
                  <span className="text-[10px] text-dfui-tertiary">Checkpoints</span>
                  <textarea
                    rows={2}
                    defaultValue={studioSettings.path_checkpoints ?? ""}
                    onBlur={(e) =>
                      void onSaveStudioSettings({
                        path_checkpoints: e.target.value,
                      })
                    }
                    className="df-input mt-0.5 w-full font-mono text-[10px]"
                  />
                </label>
                <label className="block">
                  <span className="text-[10px] text-dfui-tertiary">LoRAs</span>
                  <textarea
                    rows={2}
                    defaultValue={studioSettings.path_loras ?? ""}
                    onBlur={(e) =>
                      void onSaveStudioSettings({ path_loras: e.target.value })
                    }
                    className="df-input mt-0.5 w-full font-mono text-[10px]"
                  />
                </label>
              </div>
            )}
            <label className="block">
              <span className="text-xs text-dfui-muted">Seed (−1 = random)</span>
              <input
                type="number"
                value={settings.seed ?? -1}
                onChange={(e) => onChange({ seed: Number(e.target.value) })}
                className="df-input mt-1 w-full px-2.5 py-1.5 font-mono text-xs"
              />
            </label>
            <label className="block">
              <span className="text-xs text-dfui-muted">Negative prompt</span>
              <textarea
                value={settings.negative_prompt ?? ""}
                onChange={(e) => onChange({ negative_prompt: e.target.value })}
                rows={2}
                className="df-input mt-1 w-full px-2.5 py-1.5 text-xs resize-none"
              />
            </label>
            {isCustomPerf && (
              <>
                <label className="block">
                  <span className="text-xs text-dfui-muted">
                    Steps — {settings.steps ?? 20}
                  </span>
                  <input
                    type="range"
                    min={4}
                    max={60}
                    value={settings.steps ?? 20}
                    onChange={(e) => onChange({ steps: Number(e.target.value) })}
                    className="mt-1 w-full accent-dfui-accent"
                  />
                </label>
                <label className="block">
                  <span className="text-xs text-dfui-muted">
                    CFG — {settings.cfg_scale ?? 4}
                  </span>
                  <input
                    type="range"
                    min={1}
                    max={12}
                    step={0.1}
                    value={settings.cfg_scale ?? 4}
                    onChange={(e) =>
                      onChange({ cfg_scale: Number(e.target.value) })
                    }
                    className="mt-1 w-full accent-dfui-accent"
                  />
                </label>
                <label className="block">
                  <span className="text-xs text-dfui-muted">Sampler</span>
                  <select
                    value={settings.sampler ?? "dpmpp_2m_sde_gpu"}
                    onChange={(e) => onChange({ sampler: e.target.value })}
                    className="df-select mt-1 w-full px-2.5 py-2 text-xs"
                  >
                    {(uiDefaults?.samplers ?? ["dpmpp_2m_sde_gpu"]).map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block">
                  <span className="text-xs text-dfui-muted">Scheduler</span>
                  <select
                    value={settings.scheduler ?? "karras"}
                    onChange={(e) => onChange({ scheduler: e.target.value })}
                    className="df-select mt-1 w-full px-2.5 py-2 text-xs"
                  >
                    {(uiDefaults?.schedulers ?? ["karras"]).map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                </label>
              </>
            )}
            <label className="block">
              <span className="text-xs text-dfui-muted">ControlNet preset</span>
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
            {(settings.cn_selection === "Custom..." ||
              settings.input_image) && (
              <label className="block">
                <span className="text-xs text-dfui-muted">Input image path</span>
                <input
                  value={settings.input_image ?? ""}
                  onChange={(e) => onChange({ input_image: e.target.value })}
                  placeholder="D:\path\to\image.png"
                  className="df-input mt-1 w-full px-2.5 py-1.5 font-mono text-[10px]"
                />
              </label>
            )}
            <p className="text-[10px] leading-snug text-dfui-tertiary">
              Model and LoRA tiles use the same cache thumbnails as the Gradio
              web UI (engine/cache/checkpoints and loras). Style cards mirror the
              multiselect list; live step preview uses the same worker as webui.py.
            </p>
            <label className="block">
              <span className="text-xs text-dfui-muted">Subject</span>
              <input
                value={settings.subject ?? ""}
                onChange={(e) => onChange({ subject: e.target.value })}
                className="df-input mt-1 w-full px-2.5 py-1.5 text-xs"
              />
            </label>
            <label className="block">
              <span className="text-xs text-dfui-muted">Lighting</span>
              <input
                value={settings.lighting ?? ""}
                onChange={(e) => onChange({ lighting: e.target.value })}
                className="df-input mt-1 w-full px-2.5 py-1.5 text-xs"
              />
            </label>
            <label className="block">
              <span className="text-xs text-dfui-muted">Camera</span>
              <input
                value={settings.camera ?? ""}
                onChange={(e) => onChange({ camera: e.target.value })}
                className="df-input mt-1 w-full px-2.5 py-1.5 text-xs"
              />
            </label>
          </div>
        )}
      </div>
    </aside>
  );
}

function PathLabel(caption: string): string {
  const bracketEnd = caption.indexOf("] ");
  if (caption.startsWith("[") && bracketEnd > 0) {
    return caption.slice(bracketEnd + 2).trim();
  }
  const parts = caption.split(/[/\\]/);
  return parts[parts.length - 1] ?? caption;
}
