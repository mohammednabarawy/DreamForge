import { Bot, CheckCircle2, KeyRound, ShieldCheck, X, XCircle, DownloadCloud, Loader2, FolderOpen } from "lucide-react";
import { useState, useEffect } from "react";
import { checkComfyBackend, installComfyBackend, pickFolder, type ComfyBackendStatus } from "../lib/tauri-api";
import {
  applyRuntimePreferences,
  getRuntimeStatus,
  repairInstallation,
  type ModelsSource,
} from "../lib/runtimeSetup";
import type {
  AgentProviderPreset,
  AgentProviderTestResult,
  DreamForgeAppConfig,
  DreamForgeAppConfigPatch,
  StudioSettings,
  UserStyleProfile,
} from "../lib/studioBridge";

type Props = {
  open: boolean;
  onClose: () => void;
  appConfig: DreamForgeAppConfig | null;
  onSaveAppConfig: (patch: DreamForgeAppConfigPatch) => void | Promise<void>;
  agentProviders?: AgentProviderPreset[];
  agentProviderTest?: AgentProviderTestResult | null;
  agentProviderBusy?: boolean;
  onTestAgentProvider?: (patch?: DreamForgeAppConfigPatch) => void | Promise<void>;
  studioSettings?: StudioSettings | null;
  onSaveStudioSettings?: (patch: StudioSettings) => void | Promise<void>;
  userStyleProfile?: UserStyleProfile | null;
  userStyleProfilePath?: string;
  onUserStyleMemoryEnabledChange?: (enabled: boolean) => void | Promise<void>;
  onClearUserStyleMemory?: () => void | Promise<void>;
  onExportUserStyleMemory?: () => void | Promise<void>;
};

export function AppSettingsModal({
  open,
  onClose,
  appConfig,
  onSaveAppConfig,
  agentProviders = [],
  agentProviderTest,
  agentProviderBusy,
  onTestAgentProvider,
  studioSettings,
  onSaveStudioSettings,
  userStyleProfile,
  userStyleProfilePath,
  onUserStyleMemoryEnabledChange,
  onClearUserStyleMemory,
  onExportUserStyleMemory,
}: Props) {
  if (!open) return null;

  const [civitaiKey, setCivitaiKey] = useState("");
  const [agentProvider, setAgentProvider] = useState("ollama");
  const [baseUrl, setBaseUrl] = useState("http://localhost:11434");
  const [model, setModel] = useState("gemma3:4b");
  const [customInstructions, setCustomInstructions] = useState("");
  const [approvalRequired, setApprovalRequired] = useState(true);
  const [autoEnhance, setAutoEnhance] = useState(false);
  const [enhanceStrength, setEnhanceStrength] = useState<"balanced" | "minimal" | "rich">("balanced");
  const [useFlufferizer, setUseFlufferizer] = useState(true);

  const [pathCheckpoints, setPathCheckpoints] = useState("");
  const [pathLoras, setPathLoras] = useState("");

  const [backendStatus, setBackendStatus] = useState<ComfyBackendStatus | null>(null);
  const [installingBackend, setInstallingBackend] = useState(false);
  const [modelsSource, setModelsSource] = useState<ModelsSource>("managed");
  const [modelsRoot, setModelsRoot] = useState("");
  const [modelsPathBusy, setModelsPathBusy] = useState(false);
  const [modelsPathMessage, setModelsPathMessage] = useState<string | null>(null);
  const [repairBusy, setRepairBusy] = useState(false);
  const [repairMessage, setRepairMessage] = useState<string | null>(null);
  const [repairLog, setRepairLog] = useState<string | null>(null);
  const [saveBusy, setSaveBusy] = useState(false);

  const activeProvider = agentProviders.find((p) => p.id === agentProvider);
  const profileLabel = userStyleProfile?.enabled ? "Local profile" : "Local profile (memory off)";

  useEffect(() => {
    if (open) {
      checkComfyBackend().then(setBackendStatus).catch(console.error);
      getRuntimeStatus()
        .then((status) => {
          setModelsSource(status.config.models_source ?? "managed");
          setModelsRoot(status.paths.models_root ?? "");
        })
        .catch(console.error);
    }
  }, [open]);

  useEffect(() => {
    if (open && appConfig) {
      setAgentProvider(appConfig.agent.provider ?? "ollama");
      setBaseUrl(appConfig.agent.base_url ?? "");
      setModel(appConfig.agent.model ?? "");
      setCustomInstructions(appConfig.agent.custom_instructions ?? "");
      setApprovalRequired(appConfig.agent.approval_required !== false);
      setAutoEnhance(Boolean(appConfig.ui.auto_enhance_on_generate));
      setEnhanceStrength(appConfig.ui.enhance_strength ?? "balanced");
      setUseFlufferizer(appConfig.ui.use_flufferizer !== false);
      setCivitaiKey("");
    }
  }, [open, appConfig]);

  useEffect(() => {
    if (open && studioSettings) {
      setPathCheckpoints(studioSettings.path_checkpoints ?? "");
      setPathLoras(studioSettings.path_loras ?? "");
    }
  }, [open, studioSettings]);

  const handleSaveModelsFolder = async () => {
    setModelsPathBusy(true);
    setModelsPathMessage(null);
    try {
      const result = await applyRuntimePreferences({
        models_source: modelsSource,
        models_root: modelsSource === "external" ? modelsRoot.trim() : undefined,
      });
      if (!result.ok) {
        setModelsPathMessage(result.models_validation.errors?.[0] ?? "Invalid models folder.");
        return;
      }
      setModelsRoot(result.paths.models_root);
      setModelsPathMessage("Models folder updated. Restart the GPU engine to rescan.");
    } catch (err) {
      setModelsPathMessage(String(err));
    } finally {
      setModelsPathBusy(false);
    }
  };

  const handleInstallBackend = async () => {
    setInstallingBackend(true);
    try {
      await installComfyBackend(true);
      const updated = await checkComfyBackend();
      setBackendStatus(updated);
    } catch (err) {
      console.error(err);
    } finally {
      setInstallingBackend(false);
    }
  };

  const handleRepairInstallation = async (clearMarkers: boolean) => {
    setRepairBusy(true);
    setRepairMessage(null);
    setRepairLog(null);
    try {
      const result = await repairInstallation(clearMarkers);
      if (!result.ok) {
        setRepairMessage(result.error ?? "Repair failed.");
        if (result.progress?.log_lines?.length) {
          setRepairLog(result.progress.log_lines.join("\n"));
        }
        return;
      }
      setRepairMessage("Installation repair completed. Restart the GPU engine if it was running.");
      if (result.progress?.log_lines?.length) {
        setRepairLog(result.progress.log_lines.join("\n"));
      }
      const updated = await checkComfyBackend();
      setBackendStatus(updated);
    } catch (err) {
      setRepairMessage(String(err));
    } finally {
      setRepairBusy(false);
    }
  };

  const handleTestConnection = async () => {
    if (onTestAgentProvider) {
      await onTestAgentProvider({
        agent: {
          provider: agentProvider,
          base_url: baseUrl,
          model: model,
        }
      });
    }
  };

  const handleSaveAll = async () => {
    setSaveBusy(true);
    try {
      const appPatch: DreamForgeAppConfigPatch = {
        agent: {
          provider: agentProvider,
          base_url: baseUrl,
          model: model,
          custom_instructions: customInstructions,
          approval_required: approvalRequired,
        },
        ui: {
          auto_enhance_on_generate: autoEnhance,
          enhance_strength: enhanceStrength,
          use_flufferizer: useFlufferizer,
        }
      };
      if (civitaiKey.trim()) {
        appPatch.ui = {
          ...appPatch.ui,
          civitai_api_key: civitaiKey.trim(),
        };
      }
      await onSaveAppConfig(appPatch);

      if (onSaveStudioSettings) {
        await onSaveStudioSettings({
          path_checkpoints: pathCheckpoints,
          path_loras: pathLoras,
        });
      }
      onClose();
    } catch (err) {
      console.error(err);
    } finally {
      setSaveBusy(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="app-settings-title"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="flex max-h-[88vh] w-full max-w-lg flex-col rounded-xl border border-dfui-border bg-dfui-panel shadow-2xl overflow-hidden">
        <div className="flex shrink-0 items-center justify-between border-b border-dfui-border/50 px-4 py-3 bg-dfui-surface/20">
          <div>
            <h2 id="app-settings-title" className="text-sm font-semibold text-dfui-fg">
              App settings
            </h2>
            <p className="text-[10px] text-dfui-tertiary">{profileLabel}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md p-1 text-dfui-tertiary transition hover:bg-dfui-surface hover:text-dfui-fg"
            aria-label="Close app settings"
          >
            <X size={18} />
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto p-4 bg-dfui-panel/40">
          <div className="space-y-4">
            {appConfig && (
              <section className="space-y-2 rounded-lg border border-dfui-border/30 bg-dfui-bg/10 p-3">
                <p className="text-[10px] font-semibold uppercase tracking-wide text-dfui-muted">
                  Discover & downloads
                </p>
                <label className="block">
                  <span className="text-[10px] text-dfui-tertiary font-medium">Civitai API key</span>
                  <div className="mt-1 flex items-center gap-2 rounded-md border border-dfui-border/50 bg-dfui-bg/30 px-2.5 py-2">
                    <KeyRound size={12} className="text-dfui-muted" />
                    <input
                      type="password"
                      value={civitaiKey}
                      onChange={(e) => setCivitaiKey(e.target.value)}
                      className="min-w-0 flex-1 bg-transparent font-mono text-[10px] text-dfui-fg outline-none placeholder:text-dfui-tertiary"
                      placeholder={
                        appConfig.ui.civitai_api_key_configured
                          ? `Configured (••••${appConfig.ui.civitai_api_key_tail ?? ""})`
                          : "Used for gated Civitai downloads in Discover"
                      }
                    />
                  </div>
                </label>
              </section>
            )}

            <section className="space-y-3 rounded-lg border border-dfui-border/50 bg-dfui-bg/20 p-3">
              <p className="text-[10px] font-semibold uppercase tracking-wide text-dfui-muted">
                Models storage
              </p>
              <p className="text-[10px] text-dfui-tertiary leading-relaxed">
                ComfyUI-compatible folder for checkpoints, LoRAs, VAE, and diffusion models.
              </p>
              <div className="space-y-2">
                <label className="flex items-center gap-2 text-[11px] text-dfui-secondary cursor-pointer">
                  <input
                    type="radio"
                    checked={modelsSource === "managed"}
                    onChange={() => setModelsSource("managed")}
                    className="accent-dfui-accent"
                  />
                  <span>Managed folder (inside DreamForge data)</span>
                </label>
                <label className="flex items-center gap-2 text-[11px] text-dfui-secondary cursor-pointer">
                  <input
                    type="radio"
                    checked={modelsSource === "external"}
                    onChange={() => setModelsSource("external")}
                    className="accent-dfui-accent"
                  />
                  <span>Existing ComfyUI models folder</span>
                </label>
              </div>
              {modelsSource === "external" && (
                <div className="flex gap-2 mt-1">
                  <input
                    type="text"
                    value={modelsRoot}
                    onChange={(e) => setModelsRoot(e.target.value)}
                    className="df-input min-w-0 flex-1 text-[10px] bg-black/25"
                    placeholder="Path to models folder"
                  />
                  <button
                    type="button"
                    className="df-btn df-btn-secondary shrink-0 px-3"
                    onClick={() => void pickFolder().then((p) => p && setModelsRoot(p))}
                  >
                    <FolderOpen className="h-3.5 w-3.5" />
                  </button>
                </div>
              )}
              {modelsSource === "managed" && modelsRoot && (
                <p className="truncate font-mono text-[10px] text-dfui-muted bg-black/10 px-2 py-1.5 rounded">{modelsRoot}</p>
              )}
              <button
                type="button"
                className="df-btn df-btn-secondary w-full text-[11px] py-2 mt-1 font-medium"
                disabled={modelsPathBusy}
                onClick={() => void handleSaveModelsFolder()}
              >
                {modelsPathBusy ? "Saving…" : "Apply models folder"}
              </button>
              {modelsPathMessage && (
                <p className="text-[10px] text-dfui-secondary bg-dfui-surface/40 px-2.5 py-1.5 rounded border border-dfui-border/30">{modelsPathMessage}</p>
              )}
            </section>

            {appConfig && (
              <section className="space-y-3 rounded-lg border border-dfui-accent/20 bg-dfui-accent/5 p-3.5">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <Bot size={15} className="text-dfui-accent" />
                    <div>
                      <p className="text-[10px] font-semibold uppercase tracking-wide text-dfui-muted">
                        Agent brain (LLM)
                      </p>
                      <p className="text-[10px] text-dfui-tertiary">
                        Optional local planner; review changes before running
                      </p>
                    </div>
                  </div>
                  {agentProviderTest && (
                    <span
                      className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[9px] font-medium ${
                        agentProviderTest.ok
                          ? "border-emerald-400/30 bg-emerald-400/10 text-emerald-200"
                          : "border-amber-400/30 bg-amber-400/10 text-amber-200"
                      }`}
                    >
                      {agentProviderTest.ok ? (
                        <CheckCircle2 size={11} />
                      ) : (
                        <XCircle size={11} />
                      )}
                      {agentProviderTest.ok ? "Connected" : "Check failed"}
                    </span>
                  )}
                </div>
                <label className="block">
                  <span className="text-[10px] text-dfui-tertiary font-medium">Provider</span>
                  <select
                    value={agentProvider}
                    onChange={(e) => {
                      const val = e.target.value;
                      setAgentProvider(val);
                      const preset = agentProviders.find((p) => p.id === val);
                      if (preset) {
                        setBaseUrl(preset.base_url ?? "");
                        setModel(preset.default_model ?? "");
                      }
                    }}
                    className="df-select mt-1 w-full px-2.5 py-2 text-xs bg-dfui-bg/40"
                  >
                    {agentProviders.map((provider) => (
                      <option key={provider.id} value={provider.id}>
                        {provider.label}
                      </option>
                    ))}
                  </select>
                </label>
                <div className="grid grid-cols-2 gap-2">
                  <label className="block">
                    <span className="text-[10px] text-dfui-tertiary font-medium">Base URL</span>
                    <input
                      value={baseUrl}
                      onChange={(e) => setBaseUrl(e.target.value)}
                      className="df-input mt-1 w-full px-2 py-1.5 font-mono text-[10px]"
                    />
                  </label>
                  <label className="block">
                    <span className="text-[10px] text-dfui-tertiary font-medium">Model</span>
                    <input
                      value={model}
                      onChange={(e) => setModel(e.target.value)}
                      className="df-input mt-1 w-full px-2 py-1.5 font-mono text-[10px]"
                    />
                  </label>
                </div>
                <label className="block">
                  <span className="text-[10px] text-dfui-tertiary font-medium">Agent instructions</span>
                  <textarea
                    rows={2}
                    value={customInstructions}
                    onChange={(e) => setCustomInstructions(e.target.value)}
                    className="df-input mt-1 w-full resize-none px-2 py-1.5 text-[10px]"
                    placeholder="Prefer Arabic typography workflows, ask before expensive runs…"
                  />
                </label>
                <div className="space-y-2 pt-1">
                  <label className="flex items-start gap-2 text-[10px] text-dfui-secondary cursor-pointer">
                    <input
                      type="checkbox"
                      checked={approvalRequired}
                      onChange={(e) => setApprovalRequired(e.target.checked)}
                      className="mt-0.5 accent-dfui-accent"
                    />
                    <span>Approve agent workflow changes before execution</span>
                  </label>
                  <label className="flex items-start gap-2 text-[10px] text-dfui-secondary cursor-pointer">
                    <input
                      type="checkbox"
                      checked={autoEnhance}
                      onChange={(e) => setAutoEnhance(e.target.checked)}
                      className="mt-0.5 accent-dfui-accent"
                    />
                    <span>Auto-enhance prompts on Generate (uses LLM)</span>
                  </label>
                </div>
                <div className="space-y-1.5 border-t border-dfui-border/30 pt-2.5">
                  <span className="text-[10px] text-dfui-tertiary font-medium">Enhance strength (wand + auto-enhance)</span>
                  <div className="flex flex-wrap gap-1">
                    {(
                      [
                        ["minimal", "Minimal"],
                        ["balanced", "Balanced"],
                        ["rich", "Rich"],
                      ] as const
                    ).map(([id, label]) => (
                      <button
                        key={id}
                        type="button"
                        onClick={() => setEnhanceStrength(id)}
                        className={`rounded-md border px-3 py-1 text-[10px] transition-colors ${
                          enhanceStrength === id
                            ? "border-dfui-accent/50 bg-dfui-accent/15 text-dfui-accent"
                            : "border-dfui-border/50 text-dfui-muted hover:border-dfui-accent/30"
                        }`}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </div>
                <label className="flex items-start gap-2 text-[10px] text-dfui-secondary cursor-pointer border-t border-dfui-border/30 pt-2.5">
                  <input
                    type="checkbox"
                    checked={useFlufferizer}
                    onChange={(e) => setUseFlufferizer(e.target.checked)}
                    className="mt-0.5 accent-dfui-accent"
                  />
                  <span>Use Flufferizer for SDXL / legacy models (Fooocus-style tags)</span>
                </label>
                <div className="flex items-center justify-between gap-2 border-t border-dfui-border/30 pt-2.5">
                  <span className="inline-flex items-center gap-1 text-[10px] text-dfui-tertiary font-medium">
                    <ShieldCheck size={12} className="text-dfui-accent/60" />
                    {activeProvider?.id === "embedded"
                      ? "Embedded local model"
                      : "Local server runtime"}
                  </span>
                  <button
                    type="button"
                    disabled={agentProviderBusy}
                    onClick={() => void handleTestConnection()}
                    className="rounded-md border border-dfui-accent/40 bg-dfui-accent/10 px-2.5 py-1 text-[10px] font-semibold text-dfui-accent hover:bg-dfui-accent/20 disabled:opacity-50 transition-colors"
                  >
                    {agentProviderBusy ? "Testing…" : "Test connection"}
                  </button>
                </div>
                {agentProviderTest?.detail && (
                  <p className="break-words font-mono text-[9px] leading-snug text-dfui-tertiary bg-black/20 p-2 rounded border border-dfui-border/25">
                    {agentProviderTest.detail}
                  </p>
                )}
              </section>
            )}

            {appConfig && backendStatus && (
              <section className="space-y-3 rounded-lg border border-dfui-border/40 bg-dfui-surface/50 p-3">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <DownloadCloud size={15} className="text-dfui-muted" />
                    <div>
                      <p className="text-[10px] font-semibold uppercase tracking-wide text-dfui-fg">
                        ComfyUI Backend
                      </p>
                      <p className="text-[10px] text-dfui-tertiary">
                        Managed ComfyUI used by workflows that need Comfy nodes
                      </p>
                    </div>
                  </div>
                  <span
                    className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[9px] font-medium ${
                      backendStatus.installed && !backendStatus.needs_update
                        ? "border-emerald-400/30 bg-emerald-400/10 text-emerald-200"
                        : "border-amber-400/30 bg-amber-400/10 text-amber-200"
                    }`}
                  >
                    {backendStatus.installed && !backendStatus.needs_update ? (
                      <CheckCircle2 size={11} />
                    ) : (
                      <XCircle size={11} />
                    )}
                    {backendStatus.installed
                      ? backendStatus.needs_update
                        ? "Update Available"
                        : "Installed"
                      : "Not Installed"}
                  </span>
                </div>
                <div className="flex items-center justify-between gap-2 border-t border-dfui-border/30 pt-2 text-[10px] text-dfui-tertiary">
                  <span>Current: {backendStatus.current || "None"}</span>
                  <span>Target: {backendStatus.target}</span>
                </div>
                <div className="flex flex-wrap justify-end gap-2 pt-1">
                  {(!backendStatus.installed || backendStatus.needs_update) && (
                    <button
                      type="button"
                      disabled={installingBackend || repairBusy}
                      onClick={handleInstallBackend}
                      className="inline-flex items-center gap-1.5 rounded-md bg-dfui-accent px-3 py-1.5 text-[11px] font-semibold text-white transition hover:bg-dfui-accent/80 disabled:opacity-50 shadow"
                    >
                      {installingBackend ? (
                        <>
                          <Loader2 size={12} className="animate-spin" />
                          Installing...
                        </>
                      ) : (
                        "Install / Update Backend"
                      )}
                    </button>
                  )}
                  <button
                    type="button"
                    disabled={repairBusy || installingBackend}
                    onClick={() => void handleRepairInstallation(false)}
                    className="inline-flex items-center gap-1 rounded-md border border-dfui-border/60 bg-dfui-bg/40 px-3 py-1.5 text-[11px] font-medium text-dfui-secondary transition hover:border-dfui-accent/40 disabled:opacity-50"
                  >
                    {repairBusy ? (
                      <>
                        <Loader2 size={12} className="animate-spin" />
                        Repairing...
                      </>
                    ) : (
                      "Repair installation"
                    )}
                  </button>
                  <button
                    type="button"
                    disabled={repairBusy || installingBackend}
                    onClick={() => void handleRepairInstallation(true)}
                    className="inline-flex items-center gap-1 rounded-md border border-amber-400/30 bg-amber-400/10 px-3 py-1.5 text-[11px] font-medium text-amber-100/90 transition hover:bg-amber-400/20 disabled:opacity-50"
                    title="Clears pip skip markers and re-runs all setup steps"
                  >
                    Full repair
                  </button>
                </div>
                {repairMessage && (
                  <p className="text-[10px] text-dfui-secondary bg-dfui-surface/40 p-2 rounded border border-dfui-border/30">{repairMessage}</p>
                )}
                {repairLog && (
                  <pre className="max-h-28 overflow-auto rounded-md border border-dfui-border/30 bg-black/20 p-2 font-mono text-[9px] text-dfui-muted whitespace-pre-wrap">
                    {repairLog}
                  </pre>
                )}
              </section>
            )}

            {userStyleProfile && onUserStyleMemoryEnabledChange && (
              <section className="space-y-3 rounded-lg border border-dfui-border/50 bg-dfui-bg/30 p-3">
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-wide text-dfui-muted">
                      Local style memory
                    </p>
                    <p className="text-[10px] text-dfui-tertiary">
                      Opt-in preferences stored on this machine only
                    </p>
                  </div>
                  <label className="inline-flex items-center gap-1.5 text-[10px] text-dfui-secondary cursor-pointer">
                    <input
                      type="checkbox"
                      checked={userStyleProfile.enabled}
                      onChange={(e) =>
                        void onUserStyleMemoryEnabledChange(e.target.checked)
                      }
                      className="accent-dfui-accent"
                    />
                    <span>Enabled</span>
                  </label>
                </div>
                <p className="text-[10px] text-dfui-tertiary">
                  {userStyleProfile.generation_count} remembered job
                  {userStyleProfile.generation_count === 1 ? "" : "s"}
                  {userStyleProfile.favorite_models[0]
                    ? ` · top model: ${userStyleProfile.favorite_models[0]}`
                    : ""}
                </p>
                {userStyleProfilePath && (
                  <p className="truncate font-mono text-[9px] text-dfui-muted bg-black/10 px-2 py-1 rounded">
                    {userStyleProfilePath}
                  </p>
                )}
                <div className="flex flex-wrap gap-1.5">
                  {onExportUserStyleMemory && (
                    <button
                      type="button"
                      onClick={() => void onExportUserStyleMemory()}
                      className="rounded-md border border-dfui-border/60 px-2.5 py-1 text-[10px] text-dfui-secondary hover:border-dfui-accent/40 font-medium transition-colors"
                    >
                      Export JSON
                    </button>
                  )}
                  {onClearUserStyleMemory && (
                    <button
                      type="button"
                      onClick={() => void onClearUserStyleMemory()}
                      className="rounded-md border border-amber-400/30 px-2.5 py-1 text-[10px] text-amber-200 hover:border-amber-300/50 font-medium transition-colors"
                    >
                      Clear memory
                    </button>
                  )}
                </div>
              </section>
            )}

            {studioSettings && (
              <section className="space-y-3 rounded-lg border border-dfui-border/40 p-3">
                <p className="text-[10px] font-semibold uppercase tracking-wide text-dfui-muted">
                  Model paths (saved to config)
                </p>
                <label className="block">
                  <span className="text-[10px] text-dfui-tertiary font-medium">Checkpoints</span>
                  <textarea
                    rows={2}
                    value={pathCheckpoints}
                    onChange={(e) => setPathCheckpoints(e.target.value)}
                    className="df-input mt-1 w-full font-mono text-[10px]"
                  />
                </label>
                <label className="block">
                  <span className="text-[10px] text-dfui-tertiary font-medium">LoRAs</span>
                  <textarea
                    rows={2}
                    value={pathLoras}
                    onChange={(e) => setPathLoras(e.target.value)}
                    className="df-input mt-1 w-full font-mono text-[10px]"
                  />
                </label>
              </section>
            )}
          </div>
        </div>
        <div className="flex shrink-0 items-center justify-end gap-2 border-t border-dfui-border/50 px-4 py-3 bg-dfui-surface/30">
          <button
            type="button"
            onClick={onClose}
            className="df-btn df-btn-secondary px-4 py-2 text-xs"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={saveBusy}
            onClick={handleSaveAll}
            className="inline-flex items-center gap-1.5 rounded-md bg-dfui-accent hover:bg-dfui-accent/80 px-4 py-2 text-xs font-semibold text-white shadow transition-colors disabled:opacity-50"
          >
            {saveBusy ? (
              <>
                <Loader2 size={12} className="animate-spin" />
                Saving...
              </>
            ) : (
              "Save changes"
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
