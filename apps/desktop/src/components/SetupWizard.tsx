import { useCallback, useEffect, useMemo, useState } from "react";
import {
  FolderOpen,
  HardDrive,
  Loader2,
  Sparkles,
  CheckCircle2,
  AlertTriangle,
} from "lucide-react";
import { pickFolder } from "../lib/tauri-api";
import {
  SETUP_STEP_LABELS,
  applyRuntimePreferences,
  finalizeSetup,
  getRuntimeStatus,
  getSetupProgress,
  runBootstrapStep,
  startEngineAfterSetup,
  type ModelsSource,
  type RuntimeStatus,
} from "../lib/runtimeSetup";

type WizardStep = "welcome" | "models" | "system" | "install" | "done";

type Props = {
  onComplete: () => void;
};

export function SetupWizard({ onComplete }: Props) {
  const [step, setStep] = useState<WizardStep>("welcome");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<RuntimeStatus | null>(null);
  const [modelsSource, setModelsSource] = useState<ModelsSource>("managed");
  const [externalModelsPath, setExternalModelsPath] = useState("");
  const [installLog, setInstallLog] = useState<string>("");
  const [installPct, setInstallPct] = useState(0);

  const defaultModelsPath = useMemo(
    () => status?.paths.data_root ? `${status.paths.data_root}/models` : "",
    [status],
  );

  const refreshStatus = useCallback(async () => {
    const next = await getRuntimeStatus();
    setStatus(next);
    if (next.config.models_source === "external" && next.config.models_root) {
      setModelsSource("external");
      setExternalModelsPath(next.config.models_root);
    }
    return next;
  }, []);

  useEffect(() => {
    void refreshStatus().catch((err) => {
      setError(String(err));
    });
  }, [refreshStatus]);

  const saveModelsPreference = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const models_root =
        modelsSource === "external" ? externalModelsPath.trim() : undefined;
      if (modelsSource === "external" && !models_root) {
        throw new Error("Choose an existing ComfyUI models folder or use the managed folder.");
      }
      const result = await applyRuntimePreferences({
        models_source: modelsSource,
        models_root,
      });
      if (!result.ok) {
        const msg = result.models_validation.errors?.join(" ") || "Models folder validation failed.";
        throw new Error(msg);
      }
      await refreshStatus();
      setStep("system");
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }, [externalModelsPath, modelsSource, refreshStatus]);

  const browseModelsFolder = useCallback(async () => {
    const picked = await pickFolder();
    if (picked) setExternalModelsPath(picked);
  }, []);

  const runInstall = useCallback(async () => {
    setBusy(true);
    setError(null);
    setInstallLog("");
    const poll = window.setInterval(() => {
      void getSetupProgress()
        .then((progress) => {
          const lines = progress.log_lines ?? [];
          if (lines.length > 0) {
            setInstallLog(lines.join("\n"));
          } else if (progress.current_message) {
            setInstallLog(progress.current_message);
          }
          setInstallPct(progress.progress_pct);
        })
        .catch(() => undefined);
    }, 450);
    try {
      let progress = await getSetupProgress();
      for (const stepName of progress.steps) {
        if (progress.completed_steps.includes(stepName)) continue;
        setInstallLog((prev) =>
          prev
            ? `${prev}\n${SETUP_STEP_LABELS[stepName] ?? stepName}…`
            : `${SETUP_STEP_LABELS[stepName] ?? stepName}…`,
        );
        const result = await runBootstrapStep(stepName);
        if (!result.ok) {
          throw new Error(result.error || `Setup step failed: ${stepName}`);
        }
        progress = result.progress ?? (await getSetupProgress());
        if (progress.log_lines?.length) {
          setInstallLog(progress.log_lines.join("\n"));
        }
        setInstallPct(progress.progress_pct);
      }
      await finalizeSetup();
      await startEngineAfterSetup();
      setStep("done");
      onComplete();
    } catch (err) {
      setError(String(err));
      const failed = await getSetupProgress().catch(() => null);
      if (failed?.log_lines?.length) {
        setInstallLog(failed.log_lines.join("\n"));
      }
    } finally {
      window.clearInterval(poll);
      setBusy(false);
    }
  }, [onComplete]);

  const diskOk = status?.system.disk_ok ?? true;
  const diskFree = status?.system.disk_free_gb ?? 0;

  return (
    <div className="fixed inset-0 z-[200] flex items-center justify-center bg-black/70 p-6 backdrop-blur-sm">
      <div className="w-full max-w-xl rounded-2xl border border-dfui-border/60 bg-dfui-panel/95 p-6 shadow-2xl">
        <div className="mb-5 flex items-center gap-3">
          <div className="rounded-xl bg-dfui-accent/15 p-2.5 text-dfui-accent">
            <Sparkles className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-dfui-primary">Welcome to DreamForge</h1>
            <p className="text-xs text-dfui-muted">First-run setup · local AI studio</p>
          </div>
        </div>

        {step === "welcome" && (
          <div className="space-y-4">
            <p className="text-sm leading-relaxed text-dfui-secondary">
              DreamForge will configure ComfyUI, required custom nodes, and model folders on this
              machine. Model weights stay separate — you can point to an existing ComfyUI library
              or let DreamForge manage a new folder.
            </p>
            <ul className="space-y-2 text-xs text-dfui-muted">
              <li>· Portable Python at <code className="text-dfui-data">python_embeded</code> (same as setup.bat)</li>
              <li>· ComfyUI engine + pinned custom nodes (downloaded on first run)</li>
              <li>· Your choice of models folder (managed or existing ComfyUI layout)</li>
              <li>· GPU engine starts after setup completes</li>
            </ul>
            <button
              type="button"
              className="df-btn df-btn-primary w-full"
              onClick={() => setStep("models")}
            >
              Continue
            </button>
          </div>
        )}

        {step === "models" && (
          <div className="space-y-4">
            <p className="text-sm text-dfui-secondary">Where should DreamForge look for models?</p>

            <label className="flex cursor-pointer gap-3 rounded-xl border border-dfui-border/50 p-3 hover:border-dfui-accent/40">
              <input
                type="radio"
                name="models-source"
                checked={modelsSource === "managed"}
                onChange={() => setModelsSource("managed")}
                className="mt-1 accent-dfui-accent"
              />
              <span>
                <span className="block text-sm font-medium text-dfui-primary">
                  Managed folder (recommended)
                </span>
                <span className="mt-1 block text-xs text-dfui-muted">
                  DreamForge creates a ComfyUI-compatible layout at{" "}
                  <code className="text-dfui-data">{defaultModelsPath || "…/models"}</code>
                </span>
              </span>
            </label>

            <label className="flex cursor-pointer gap-3 rounded-xl border border-dfui-border/50 p-3 hover:border-dfui-accent/40">
              <input
                type="radio"
                name="models-source"
                checked={modelsSource === "external"}
                onChange={() => setModelsSource("external")}
                className="mt-1 accent-dfui-accent"
              />
              <span className="flex-1">
                <span className="block text-sm font-medium text-dfui-primary">
                  Existing ComfyUI models folder
                </span>
                <span className="mt-1 block text-xs text-dfui-muted">
                  Use checkpoints, LoRAs, VAE, and diffusion models you already have.
                </span>
                {modelsSource === "external" && (
                  <div className="mt-3 flex gap-2">
                    <input
                      type="text"
                      value={externalModelsPath}
                      onChange={(e) => setExternalModelsPath(e.target.value)}
                      placeholder="D:\ComfyUI\models"
                      className="df-input flex-1 text-xs"
                    />
                    <button
                      type="button"
                      className="df-btn df-btn-secondary shrink-0"
                      onClick={() => void browseModelsFolder()}
                    >
                      <FolderOpen className="h-4 w-4" />
                    </button>
                  </div>
                )}
              </span>
            </label>

            <div className="flex gap-2">
              <button type="button" className="df-btn df-btn-secondary flex-1" onClick={() => setStep("welcome")}>
                Back
              </button>
              <button
                type="button"
                className="df-btn df-btn-primary flex-1"
                disabled={busy}
                onClick={() => void saveModelsPreference()}
              >
                {busy ? <Loader2 className="mx-auto h-4 w-4 animate-spin" /> : "Continue"}
              </button>
            </div>
          </div>
        )}

        {step === "system" && (
          <div className="space-y-4">
            <div className="rounded-xl border border-dfui-border/40 bg-dfui-surface/40 p-4">
              <div className="flex items-start gap-3">
                <HardDrive className="mt-0.5 h-4 w-4 text-dfui-data" />
                <div>
                  <p className="text-sm font-medium text-dfui-primary">Storage check</p>
                  <p className="mt-1 text-xs text-dfui-muted">
                    {diskFree} GB free on data drive
                    {!diskOk && " — 30 GB+ recommended for ComfyUI dependencies."}
                  </p>
                </div>
              </div>
            </div>
            {!diskOk && (
              <div className="flex items-start gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-100/90">
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                Low disk space may cause setup to fail. Free space or choose another data drive in a
                future update.
              </div>
            )}
            <p className="text-xs text-dfui-muted">
              Models folder:{" "}
              <code className="text-dfui-data">{status?.paths.models_root ?? "…"}</code>
            </p>
            <div className="flex gap-2">
              <button type="button" className="df-btn df-btn-secondary flex-1" onClick={() => setStep("models")}>
                Back
              </button>
              <button
                type="button"
                className="df-btn df-btn-primary flex-1"
                onClick={() => {
                  setStep("install");
                  void runInstall();
                }}
              >
                Install engine
              </button>
            </div>
          </div>
        )}

        {step === "install" && (
          <div className="space-y-4">
            <div className="h-2 overflow-hidden rounded-full bg-dfui-border/40">
              <div
                className="h-full rounded-full bg-dfui-accent transition-all duration-300"
                style={{ width: `${Math.max(installPct, busy ? 8 : 0)}%` }}
              />
            </div>
            <p className="text-sm text-dfui-secondary">
              {busy ? "Setting up ComfyUI and dependencies…" : "Setup paused"}
            </p>
            {installLog && (
              <pre className="max-h-48 overflow-auto rounded-lg border border-dfui-border/30 bg-black/30 p-3 font-mono text-[10px] text-dfui-muted whitespace-pre-wrap">
                {installLog}
              </pre>
            )}
            {!busy && error && (
              <div className="space-y-2">
                <p className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-200">
                  {error}
                </p>
                <button type="button" className="df-btn df-btn-primary w-full" onClick={() => void runInstall()}>
                  Retry setup
                </button>
              </div>
            )}
          </div>
        )}

        {step === "done" && (
          <div className="space-y-4 text-center">
            <CheckCircle2 className="mx-auto h-10 w-10 text-emerald-400" />
            <p className="text-sm text-dfui-secondary">DreamForge is ready. The GPU engine is starting.</p>
          </div>
        )}

        {error && step !== "install" && (
          <p className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-200">
            {error}
          </p>
        )}
      </div>
    </div>
  );
}
