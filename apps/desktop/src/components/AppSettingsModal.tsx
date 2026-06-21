import { Bot, CheckCircle2, KeyRound, ShieldCheck, X, XCircle, DownloadCloud, Loader2, FolderOpen } from "lucide-react";
import { useState, useEffect } from "react";
import { ReferencePacksPanel } from "./ReferencePacksPanel";
import { IdentitiesPanel } from "./IdentitiesPanel";
import { checkComfyBackend, installComfyBackend, pickFolder, type GenerationSettings, type ComfyBackendStatus } from "../lib/tauri-api";
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
  IdentityRecord,
  ReferencePack,
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
  settings: GenerationSettings;
  referencePacks?: ReferencePack[];
  onAttachReferencePack?: (packId: string) => void;
  onReferencePackRoleChange?: (role: ReferencePack["type"]) => void;
  onCreateReferencePack?: (
    name: string,
    type: ReferencePack["type"],
    meta?: { tags?: string[]; notes?: string; imagePaths?: string[] },
  ) => void | Promise<void>;
  onDeleteReferencePack?: (packId: string) => void | Promise<void>;
  onRefreshReferencePacks?: () => void | Promise<void>;
  sessionImagePaths?: string[];
  identities?: IdentityRecord[];
  onAttachIdentity?: (identityId: string) => void;
  onIdentityRoleChange?: (role: IdentityRecord["type"]) => void;
  onCreateIdentity?: (
    name: string,
    type: IdentityRecord["type"],
    imagePaths?: string[],
  ) => void | Promise<void>;
  onDeleteIdentity?: (identityId: string) => void | Promise<void>;
  onRefreshIdentities?: () => void | Promise<void>;
  onChange: (patch: Partial<GenerationSettings>) => void;
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
  settings,
  referencePacks = [],
  onAttachReferencePack,
  onReferencePackRoleChange,
  onCreateReferencePack,
  onDeleteReferencePack,
  onRefreshReferencePacks,
  sessionImagePaths = [],
  identities = [],
  onAttachIdentity,
  onIdentityRoleChange,
  onCreateIdentity,
  onDeleteIdentity,
  onRefreshIdentities,
  onChange,
}: Props) {
  if (!open) return null;

  const activeProvider = agentProviders.find((p) => p.id === appConfig?.agent.provider);
  const profileLabel = userStyleProfile?.enabled ? "Local profile" : "Local profile (memory off)";

  const [backendStatus, setBackendStatus] = useState<ComfyBackendStatus | null>(null);
  const [installingBackend, setInstallingBackend] = useState(false);
  const [modelsSource, setModelsSource] = useState<ModelsSource>("managed");
  const [modelsRoot, setModelsRoot] = useState("");
  const [modelsPathBusy, setModelsPathBusy] = useState(false);
  const [modelsPathMessage, setModelsPathMessage] = useState<string | null>(null);
  const [repairBusy, setRepairBusy] = useState(false);
  const [repairMessage, setRepairMessage] = useState<string | null>(null);
  const [repairLog, setRepairLog] = useState<string | null>(null);

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
      <div className="flex max-h-[88vh] w-full max-w-lg flex-col rounded-xl border border-dfui-border bg-dfui-panel shadow-2xl">
        <div className="flex shrink-0 items-center justify-between border-b border-dfui-border/50 px-4 py-3">
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
        <div className="min-h-0 flex-1 overflow-y-auto p-4">
          <div className="space-y-4">
            {appConfig && (
              <section className="space-y-2">
                <p className="text-[10px] font-medium uppercase tracking-wide text-dfui-muted">
                  Discover & downloads
                </p>
                <label className="block">
                  <span className="text-[10px] text-dfui-tertiary">Civitai API key</span>
                  <div className="mt-0.5 flex items-center gap-2 rounded-md border border-dfui-border/50 bg-dfui-bg/30 px-2 py-1.5">
                    <KeyRound size={12} className="text-dfui-muted" />
                    <input
                      key={
                        appConfig.ui.civitai_api_key_configured
                          ? `civitai-configured-${appConfig.ui.civitai_api_key_tail ?? ""}`
                          : "civitai-empty"
                      }
                      type="password"
                      defaultValue=""
                      onBlur={(e) => {
                        const next = e.target.value.trim();
                        if (!next && appConfig.ui.civitai_api_key_configured) return;
                        void onSaveAppConfig({
                          ui: { civitai_api_key: next },
                        });
                      }}
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

            <section className="space-y-2 rounded-lg border border-dfui-border/50 bg-dfui-bg/20 p-2.5">
              <p className="text-[10px] font-medium uppercase tracking-wide text-dfui-muted">
                Models storage
              </p>
              <p className="text-[10px] text-dfui-tertiary">
                ComfyUI-compatible folder for checkpoints, LoRAs, VAE, and diffusion models.
              </p>
              <label className="flex items-center gap-2 text-[11px] text-dfui-secondary">
                <input
                  type="radio"
                  checked={modelsSource === "managed"}
                  onChange={() => setModelsSource("managed")}
                  className="accent-dfui-accent"
                />
                Managed folder (inside DreamForge data)
              </label>
              <label className="flex items-center gap-2 text-[11px] text-dfui-secondary">
                <input
                  type="radio"
                  checked={modelsSource === "external"}
                  onChange={() => setModelsSource("external")}
                  className="accent-dfui-accent"
                />
                Existing ComfyUI models folder
              </label>
              {modelsSource === "external" && (
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={modelsRoot}
                    onChange={(e) => setModelsRoot(e.target.value)}
                    className="df-input min-w-0 flex-1 text-[10px]"
                    placeholder="Path to models folder"
                  />
                  <button
                    type="button"
                    className="df-btn df-btn-secondary shrink-0 px-2"
                    onClick={() => void pickFolder().then((p) => p && setModelsRoot(p))}
                  >
                    <FolderOpen className="h-3.5 w-3.5" />
                  </button>
                </div>
              )}
              {modelsSource === "managed" && modelsRoot && (
                <p className="truncate font-mono text-[10px] text-dfui-muted">{modelsRoot}</p>
              )}
              <button
                type="button"
                className="df-btn df-btn-secondary w-full text-[11px]"
                disabled={modelsPathBusy}
                onClick={() => void handleSaveModelsFolder()}
              >
                {modelsPathBusy ? "Saving…" : "Apply models folder"}
              </button>
              {modelsPathMessage && (
                <p className="text-[10px] text-dfui-secondary">{modelsPathMessage}</p>
              )}
            </section>

            {appConfig && (
              <section className="space-y-2 rounded-lg border border-dfui-accent/25 bg-dfui-accent/5 p-2.5">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <Bot size={14} className="text-dfui-accent" />
                    <div>
                      <p className="text-[10px] font-medium uppercase tracking-wide text-dfui-muted">
                        Agent runtime
                      </p>
                      <p className="text-[10px] text-dfui-tertiary">
                        Optional local planner; review changes before running
                      </p>
                    </div>
                  </div>
                  {agentProviderTest && (
                    <span
                      className={`inline-flex items-center gap-1 rounded-md border px-1.5 py-1 text-[9px] ${
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
                  <span className="text-[10px] text-dfui-tertiary">Runtime</span>
                  <select
                    value={appConfig.agent.provider}
                    onChange={(e) => {
                      const preset = agentProviders.find((p) => p.id === e.target.value);
                      void onSaveAppConfig({
                        agent: {
                          provider: e.target.value,
                          base_url: preset?.base_url ?? appConfig.agent.base_url,
                          model: preset?.default_model ?? appConfig.agent.model,
                        },
                      });
                    }}
                    className="df-select mt-0.5 w-full px-2.5 py-2 text-xs"
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
                    <span className="text-[10px] text-dfui-tertiary">Base URL</span>
                    <input
                      defaultValue={appConfig.agent.base_url}
                      onBlur={(e) =>
                        void onSaveAppConfig({
                          agent: { base_url: e.target.value },
                        })
                      }
                      className="df-input mt-0.5 w-full px-2 py-1.5 font-mono text-[10px]"
                    />
                  </label>
                  <label className="block">
                    <span className="text-[10px] text-dfui-tertiary">Model</span>
                    <input
                      defaultValue={appConfig.agent.model}
                      onBlur={(e) =>
                        void onSaveAppConfig({
                          agent: { model: e.target.value },
                        })
                      }
                      className="df-input mt-0.5 w-full px-2 py-1.5 font-mono text-[10px]"
                    />
                  </label>
                </div>
                <label className="block">
                  <span className="text-[10px] text-dfui-tertiary">Agent instructions</span>
                  <textarea
                    rows={2}
                    defaultValue={appConfig.agent.custom_instructions}
                    onBlur={(e) =>
                      void onSaveAppConfig({
                        agent: { custom_instructions: e.target.value },
                      })
                    }
                    className="df-input mt-0.5 w-full resize-none px-2 py-1.5 text-[10px]"
                    placeholder="Prefer Arabic typography workflows, ask before expensive runs…"
                  />
                </label>
                <label className="flex items-start gap-2 text-[10px] text-dfui-muted">
                  <input
                    type="checkbox"
                    checked={appConfig.agent.approval_required}
                    onChange={(e) =>
                      void onSaveAppConfig({
                        agent: { approval_required: e.target.checked },
                      })
                    }
                    className="mt-0.5 accent-dfui-accent"
                  />
                  Approve agent workflow changes
                </label>
                <div className="flex items-center justify-between gap-2 border-t border-dfui-border/30 pt-2">
                  <span className="inline-flex items-center gap-1 text-[10px] text-dfui-tertiary">
                    <ShieldCheck size={12} />
                    {activeProvider?.id === "embedded"
                      ? "Embedded local model"
                      : "Local server runtime"}
                  </span>
                  <button
                    type="button"
                    disabled={agentProviderBusy}
                    onClick={() => void onTestAgentProvider?.()}
                    className="rounded-md border border-dfui-accent/40 bg-dfui-accent/10 px-2 py-1 text-[10px] font-medium text-dfui-accent hover:bg-dfui-accent/20 disabled:opacity-50"
                  >
                    {agentProviderBusy ? "Testing…" : "Test connection"}
                  </button>
                </div>
                {agentProviderTest?.detail && (
                  <p className="break-words font-mono text-[9px] leading-snug text-dfui-tertiary">
                    {agentProviderTest.detail}
                  </p>
                )}
              </section>
            )}

            {appConfig && backendStatus && (
              <section className="space-y-2 rounded-lg border border-dfui-border/40 bg-dfui-surface/50 p-2.5">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <DownloadCloud size={14} className="text-dfui-muted" />
                    <div>
                      <p className="text-[10px] font-medium uppercase tracking-wide text-dfui-fg">
                        ComfyUI Backend
                      </p>
                      <p className="text-[10px] text-dfui-tertiary">
                        Managed ComfyUI used by workflows that need Comfy nodes
                      </p>
                    </div>
                  </div>
                  <span
                    className={`inline-flex items-center gap-1 rounded-md border px-1.5 py-1 text-[9px] ${
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
                      className="inline-flex items-center gap-1 rounded-md bg-dfui-accent px-3 py-1.5 text-[11px] font-medium text-white transition hover:bg-dfui-accent/80 disabled:opacity-50"
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
                    className="inline-flex items-center gap-1 rounded-md border border-dfui-border/60 bg-dfui-bg/40 px-3 py-1.5 text-[11px] text-dfui-secondary transition hover:border-dfui-accent/40 disabled:opacity-50"
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
                    className="inline-flex items-center gap-1 rounded-md border border-amber-400/30 bg-amber-400/10 px-3 py-1.5 text-[11px] text-amber-100/90 transition hover:bg-amber-400/20 disabled:opacity-50"
                    title="Clears pip skip markers and re-runs all setup steps"
                  >
                    Full repair
                  </button>
                </div>
                {repairMessage && (
                  <p className="text-[10px] text-dfui-tertiary">{repairMessage}</p>
                )}
                {repairLog && (
                  <pre className="max-h-28 overflow-auto rounded-md border border-dfui-border/30 bg-black/20 p-2 font-mono text-[9px] text-dfui-muted whitespace-pre-wrap">
                    {repairLog}
                  </pre>
                )}
              </section>
            )}

            {userStyleProfile && onUserStyleMemoryEnabledChange && (
              <section className="space-y-2 rounded-lg border border-dfui-border/50 bg-dfui-bg/30 p-2.5">
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <p className="text-[10px] font-medium uppercase tracking-wide text-dfui-muted">
                      Local style memory
                    </p>
                    <p className="text-[10px] text-dfui-tertiary">
                      Opt-in preferences stored on this machine only
                    </p>
                  </div>
                  <label className="inline-flex items-center gap-1.5 text-[10px] text-dfui-secondary">
                    <input
                      type="checkbox"
                      checked={userStyleProfile.enabled}
                      onChange={(e) =>
                        void onUserStyleMemoryEnabledChange(e.target.checked)
                      }
                      className="accent-dfui-accent"
                    />
                    Enabled
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
                  <p className="truncate font-mono text-[9px] text-dfui-muted">
                    {userStyleProfilePath}
                  </p>
                )}
                <div className="flex flex-wrap gap-1.5">
                  {onExportUserStyleMemory && (
                    <button
                      type="button"
                      onClick={() => void onExportUserStyleMemory()}
                      className="rounded-md border border-dfui-border/60 px-2 py-1 text-[10px] text-dfui-secondary hover:border-dfui-accent/40"
                    >
                      Export JSON
                    </button>
                  )}
                  {onClearUserStyleMemory && (
                    <button
                      type="button"
                      onClick={() => void onClearUserStyleMemory()}
                      className="rounded-md border border-amber-400/30 px-2 py-1 text-[10px] text-amber-200 hover:border-amber-300/50"
                    >
                      Clear memory
                    </button>
                  )}
                </div>
              </section>
            )}

            {(onAttachReferencePack || onCreateReferencePack) && (
              <ReferencePacksPanel
                compact
                settings={settings}
                referencePacks={referencePacks}
                sessionImagePaths={sessionImagePaths}
                onAttachReferencePack={onAttachReferencePack}
                onReferencePackRoleChange={onReferencePackRoleChange}
                onCreateReferencePack={onCreateReferencePack}
                onDeleteReferencePack={onDeleteReferencePack}
                onRefreshReferencePacks={onRefreshReferencePacks}
              />
            )}

            {(onAttachIdentity || onCreateIdentity) && (
              <IdentitiesPanel
                compact
                settings={settings}
                identities={identities}
                sessionImagePaths={sessionImagePaths}
                onAttachIdentity={onAttachIdentity}
                onIdentityRoleChange={onIdentityRoleChange}
                onChange={onChange}
                onCreateIdentity={onCreateIdentity}
                onDeleteIdentity={onDeleteIdentity}
                onRefreshIdentities={onRefreshIdentities}
              />
            )}

            {onSaveStudioSettings && studioSettings && (
              <section className="space-y-2 rounded-lg border border-dfui-border/40 p-2.5">
                <p className="text-[10px] font-medium uppercase tracking-wide text-dfui-muted">
                  Model paths (saved to config)
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
              </section>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
