import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { isTauri } from "@tauri-apps/api/core";
import { appDataDir, join } from "@tauri-apps/api/path";
import { downloadCompanionEntries, installCustomNodePacks, installWorkflowModels, verifyCompanionEntries } from "../lib/studioBridge";
import {
  checkModelDependencies,
  downloadModel,
  onDownloadProgress,
  readTextFile,
  type DownloadProgressPayload,
  type ModelDependencyItem,
} from "../lib/tauri-api";
import { isCustomNodePackItem, isWorkflowModelItem } from "../lib/companionAssets";
import { formatCompanionInstallError } from "../lib/companionInstallErrors";

export type CompanionDownloadPhase = "idle" | "confirm" | "running" | "done" | "error";

export type CompanionDownloadLine = {
  ts: number;
  level: "info" | "ok" | "warn" | "error";
  text: string;
};

export type CompanionVerifyResult = {
  ready: boolean;
  stillMissing: ModelDependencyItem[];
};

function itemLabel(item: ModelDependencyItem): string {
  return item.id ?? item.filename ?? item.relative ?? "companion";
}

function companionCategory(relative: string | undefined, fallback?: string): string {
  if (fallback?.trim()) return fallback;
  const folder = relative?.split("/", 1)[0] ?? "";
  if (
    folder === "vae" ||
    folder === "clip" ||
    folder === "loras" ||
    folder === "text_encoders" ||
    folder === "controlnet" ||
    folder === "upscale_models" ||
    folder === "checkpoints" ||
    folder === "diffusion_models"
  ) {
    return folder;
  }
  return "text_encoders";
}

function companionFilename(item: ModelDependencyItem): string {
  if (item.filename?.trim()) return item.filename;
  const relative = item.relative ?? "";
  const parts = relative.split("/");
  return parts[parts.length - 1] || item.id || "companion.safetensors";
}

async function companionInstallProgressPath(): Promise<string | null> {
  if (!isTauri()) return null;
  try {
    return await join(await appDataDir(), "companion_install_progress.jsonl");
  } catch {
    return null;
  }
}

type ProgressPollHandle = {
  stop: () => void;
};

function startInstallProgressPolling(
  progressPath: string,
  onLine: (message: string) => void,
): ProgressPollHandle {
  let offset = 0;
  let stopped = false;
  const timer = window.setInterval(async () => {
    if (stopped) return;
    try {
      const content = await readTextFile(progressPath);
      if (!content || content.length <= offset) return;
      const chunk = content.slice(offset);
      offset = content.length;
      for (const line of chunk.split("\n")) {
        const trimmed = line.trim();
        if (!trimmed) continue;
        try {
          const parsed = JSON.parse(trimmed) as { message?: string };
          if (parsed.message) onLine(parsed.message);
        } catch {
          onLine(trimmed);
        }
      }
    } catch {
      /* progress file not created yet */
    }
  }, 450);
  return {
    stop: () => {
      stopped = true;
      window.clearInterval(timer);
    },
  };
}

function itemDestination(item: ModelDependencyItem): string {
  return item.relative ?? `${item.category ?? "models"}/${companionFilename(item)}`;
}

function manualInstallText(model: string, missing: ModelDependencyItem[]): string {
  const lines = [
    `DreamForge missing assets for: ${model || "workflow-assets"}`,
    "",
    "Download each file and place it at the listed destination under your models folder.",
    "",
  ];
  for (const item of missing) {
    lines.push(`- ${itemLabel(item)}`);
    lines.push(`  Destination: ${itemDestination(item)}`);
    lines.push(`  URL: ${item.url ?? "No direct URL configured. Use the note below."}`);
    if (item.note) lines.push(`  Note: ${item.note}`);
    if (item.expected_path) lines.push(`  Expected path: ${item.expected_path}`);
    lines.push("");
  }
  return lines.join("\n").trim();
}

type Options = {
  verifyReady?: () => Promise<CompanionVerifyResult>;
  /** When false, downloads/installs are deferred until ComfyUI is ready. */
  requireComfyReady?: () => boolean;
};

export function useCompanionDownload(options?: Options) {
  const verifyReadyRef = useRef(options?.verifyReady);
  verifyReadyRef.current = options?.verifyReady;
  const requireComfyReadyRef = useRef(options?.requireComfyReady);
  requireComfyReadyRef.current = options?.requireComfyReady;

  const [open, setOpen] = useState(false);
  const [phase, setPhase] = useState<CompanionDownloadPhase>("idle");
  const [lines, setLines] = useState<CompanionDownloadLine[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [totalCount, setTotalCount] = useState(0);
  const [currentItem, setCurrentItem] = useState<ModelDependencyItem | null>(null);
  const [fileProgress, setFileProgress] = useState<DownloadProgressPayload | null>(null);
  const [modelName, setModelName] = useState("");
  const [pendingMissing, setPendingMissing] = useState<ModelDependencyItem[]>([]);
  const runIdRef = useRef(0);

  const append = useCallback((level: CompanionDownloadLine["level"], text: string) => {
    setLines((prev) => [...prev, { ts: Date.now(), level, text }]);
  }, []);

  const close = useCallback(() => {
    if (phase === "running") return;
    setOpen(false);
    setPhase("idle");
    setLines([]);
    setCurrentIndex(0);
    setTotalCount(0);
    setCurrentItem(null);
    setFileProgress(null);
    setModelName("");
    setPendingMissing([]);
  }, [phase]);

  const verifyDownloads = useCallback(
    async (model: string, requested: ModelDependencyItem[]): Promise<CompanionVerifyResult> => {
      if (requested.length > 0) {
        const exact = await verifyCompanionEntries(requested);
        return {
          ready: Boolean(exact.ready),
          stillMissing: (exact.missing ?? []) as ModelDependencyItem[],
        };
      }
      if (verifyReadyRef.current) {
        return verifyReadyRef.current();
      }
      const check = await checkModelDependencies(model);
      return {
        ready: Boolean(check.ready),
        stillMissing: check.missing ?? requested,
      };
    },
    [],
  );

  const runDownload = useCallback(
    async (model: string, missing: ModelDependencyItem[]) => {
      if (requireComfyReadyRef.current && !requireComfyReadyRef.current()) {
        append("warn", "ComfyUI server is still starting — download will wait until the engine is ready.");
        setPhase("confirm");
        return;
      }
      const runId = ++runIdRef.current;
      setPhase("running");
      setLines([]);
      setCurrentIndex(0);
      setTotalCount(missing.length);
      setCurrentItem(null);
      setFileProgress(null);
      setModelName(model);

      append("info", `Model: ${model}`);
      append("info", `Preparing to download ${missing.length} required asset(s).`);
      append(
        "info",
        "Large model files can take several minutes. You can keep DreamForge open while this runs.",
      );

      let queue = missing;
      if (queue.length > 0) {
        append("info", "Checking which assets are already installed…");
        try {
          const pre = await verifyDownloads(model, queue);
          if (pre.ready) {
            append("ok", "All required assets are already present.");
            setPhase("done");
            return;
          }
          if (pre.stillMissing.length < queue.length) {
            const skipped = queue.length - pre.stillMissing.length;
            append("ok", `Found ${skipped} asset(s) already on disk — skipping download.`);
            queue = pre.stillMissing;
            setTotalCount(queue.length);
          } else {
            queue = pre.stillMissing;
          }
        } catch (e) {
          append("warn", `Could not pre-check assets: ${String(e)}`);
        }
      }

      if (queue.length === 0) {
        append("info", "Rechecking dependencies…");
        try {
          const verify = await verifyDownloads(model, missing);
          if (verify.ready) append("ok", "All companion files are present.");
          else
            append(
              "warn",
              `Still missing ${verify.stillMissing.length} file(s) after check.`,
            );
        } catch (e) {
          append("error", `Dependency check failed: ${String(e)}`);
        }
        setPhase("done");
        return;
      }

      const customNodePacks = queue.filter(isCustomNodePackItem);
      const workflowModels = queue.filter(isWorkflowModelItem);
      const modelAssets = queue.filter(
        (item) =>
          !isCustomNodePackItem(item) &&
          !isWorkflowModelItem(item),
      );

      const progressPath = await companionInstallProgressPath();
      let progressPoll: ProgressPollHandle | null = null;
      const beginLiveProgress = () => {
        if (!progressPath) return;
        progressPoll?.stop();
        progressPoll = startInstallProgressPolling(progressPath, (message) => {
          if (runId !== runIdRef.current) return;
          append("info", message);
        });
      };
      const endLiveProgress = () => {
        progressPoll?.stop();
        progressPoll = null;
      };

      let failures = 0;
      if (customNodePacks.length > 0) {
        const packIds = customNodePacks
          .map((item) => item.pack_id ?? item.id)
          .filter((value): value is string => Boolean(value?.trim()));
        append(
          "info",
          `Installing ${packIds.length} ComfyUI custom node pack(s)…`,
        );
        setTotalCount(customNodePacks.length + modelAssets.length);
        for (let i = 0; i < customNodePacks.length; i += 1) {
          if (runId !== runIdRef.current) return;
          const item = customNodePacks[i];
          setCurrentIndex(i + 1);
          setCurrentItem(item);
          append("info", `Installing custom node pack: ${itemLabel(item)}`);
        }
        try {
          const managerCount = customNodePacks.filter(
            (item) => item.install_via === "manager",
          ).length;
          if (managerCount > 0) {
            append(
              "info",
              `Using ComfyUI-Manager for ${managerCount} optional node pack(s)…`,
            );
          }
          beginLiveProgress();
          const payload = await installCustomNodePacks(packIds, {
            strategy: "auto",
            restart_comfy: true,
            progress_file: progressPath ?? undefined,
          });
          endLiveProgress();
          if (runId !== runIdRef.current) return;
          if (!progressPath) {
            for (const message of payload.messages ?? []) {
              append("info", message);
            }
          }
          for (const packId of payload.installed ?? []) {
            append("ok", `Installed custom node pack: ${packId}`);
          }
          for (const err of payload.errors ?? []) {
            failures += 1;
            append("error", formatCompanionInstallError(err));
          }
          if (payload.ready) {
            append("ok", "Custom node packs are installed and registered.");
          } else if (!payload.errors?.length) {
            append("warn", "Custom node packs installed but ComfyUI still needs a restart.");
          }
        } catch (e) {
          endLiveProgress();
          failures += customNodePacks.length;
          append("error", `Custom node install failed: ${String(e)}`);
        }
      }

      if (workflowModels.length > 0) {
        const catalogIds = workflowModels
          .map((item) => item.catalog_id ?? item.id)
          .filter((value): value is string => Boolean(value?.trim()));
        append(
          "info",
          `Installing ${catalogIds.length} workflow model pack(s) (annotator weights, Segformer, etc.)…`,
        );
        setTotalCount(customNodePacks.length + workflowModels.length + modelAssets.length);
        for (let i = 0; i < workflowModels.length; i += 1) {
          const item = workflowModels[i];
          setCurrentIndex(customNodePacks.length + i + 1);
          setCurrentItem(item);
          setFileProgress({
            filename: item.filename ?? item.catalog_id ?? item.id ?? "workflow-model",
            percentage: 0,
            downloaded: 0,
            total: 0,
            status: "downloading",
            path: item.expected_path ?? item.relative,
          });
        }
        try {
          beginLiveProgress();
          const payload = await installWorkflowModels(catalogIds, {
            prefer_manager: true,
            progress_file: progressPath ?? undefined,
          });
          endLiveProgress();
          if (runId !== runIdRef.current) return;
          if (!progressPath) {
            for (const message of payload.messages ?? []) {
              append("info", message);
            }
          }
          const pctMatch = (payload.messages ?? [])
            .map((message) => message.match(/(\d+)%/))
            .filter(Boolean)
            .map((match) => Number(match?.[1] ?? 0));
          const lastPct = pctMatch.length > 0 ? pctMatch[pctMatch.length - 1] : payload.ready ? 100 : 0;
          if (workflowModels[0]) {
            setFileProgress({
              filename:
                workflowModels[0].filename ??
                workflowModels[0].catalog_id ??
                workflowModels[0].id ??
                "workflow-model",
              percentage: lastPct,
              downloaded: 0,
              total: 0,
              status: payload.ready ? "complete" : "downloading",
              path: workflowModels[0].expected_path ?? workflowModels[0].relative,
            });
          }
          if (payload.ready) {
            for (const catalogId of payload.installed ?? []) {
              append("ok", `Installed workflow model: ${catalogId}`);
            }
          } else {
            for (const catalogId of payload.installed ?? []) {
              append("warn", `Workflow model reported installed but verification failed: ${catalogId}`);
              failures += 1;
            }
          }
          for (const err of payload.errors ?? []) {
            failures += 1;
            append("error", formatCompanionInstallError(err));
          }
          if (!payload.ready && (payload.errors?.length ?? 0) === 0) {
            failures += workflowModels.length;
            append(
              "error",
              "Workflow model download finished but DreamForge could not verify the files on disk.",
            );
          }
        } catch (e) {
          endLiveProgress();
          failures += workflowModels.length;
          append("error", `Workflow model install failed: ${String(e)}`);
        }
      }

      endLiveProgress();

      const withoutUrl = modelAssets.filter((item) => !item.url);
      for (const item of withoutUrl) {
        append(
          "warn",
          `Manual install needed for ${itemLabel(item)}: no direct download URL configured.`,
        );
        failures += 1;
      }

      const downloadableCandidates = modelAssets.filter((item) => item.url);
      const downloadable: ModelDependencyItem[] = [];
      for (const item of downloadableCandidates) {
        try {
          const recheck = await verifyCompanionEntries([item]);
          if (recheck.ready || (recheck.missing ?? []).length === 0) {
            append("ok", `Already on disk (including variants): ${itemLabel(item)}`);
            continue;
          }
        } catch {
          /* proceed with download attempt */
        }
        downloadable.push(item);
      }
      if (downloadable.length > 0) {
        append("info", `Downloading ${downloadable.length} asset(s) to the models folder…`);
        setTotalCount(customNodePacks.length + workflowModels.length + downloadable.length);
        for (let i = 0; i < downloadable.length; i += 1) {
          if (runId !== runIdRef.current) return;
          const item = downloadable[i];
          const filename = companionFilename(item);
          const category = companionCategory(item.relative, item.category);
          setCurrentIndex(customNodePacks.length + i + 1);
          setCurrentItem(item);
          setFileProgress({
            filename,
            percentage: 0,
            downloaded: 0,
            total: 0,
            status: "downloading",
            category,
          });
          append(
            "info",
            `Starting ${i + 1} of ${downloadable.length}: ${itemLabel(item)}${item.relative ? ` → ${item.relative}` : ""}`,
          );

          try {
            if (isTauri()) {
              const unlisten = await onDownloadProgress((payload) => {
                if (runId !== runIdRef.current) return;
                if (payload.filename !== filename) return;
                setFileProgress(payload);
              });
              try {
                await downloadModel({
                  url: item.url!,
                  category,
                  filename,
                  apiKey: null,
                  minBytes: item.min_bytes ?? null,
                });
              } finally {
                unlisten();
              }
              append("ok", `  Download complete: ${itemLabel(item)}`);
            } else {
              const payload = await downloadCompanionEntries([item]);
              if (payload.ok === false && payload.error) {
                failures += 1;
                append("error", `  ${payload.error}`);
                continue;
              }
              for (const err of payload.errors ?? []) {
                failures += 1;
                append(
                  "error",
                  `  Failed ${err.id ?? err.relative ?? "asset"}: ${err.error ?? "unknown error"}`,
                );
              }
              const result = payload.results?.[0];
              if (result?.status === "downloaded") {
                append("ok", `  Download complete: ${itemLabel(item)}`);
              } else if (result?.status === "exists") {
                append("ok", `  Already present: ${itemLabel(item)}`);
              }
              setFileProgress({
                filename,
                percentage: 100,
                downloaded: 0,
                total: 0,
                status: "complete",
                category,
              });
            }
          } catch (e) {
            failures += 1;
            append("error", `  Failed ${itemLabel(item)}: ${String(e)}`);
          }
        }
      }

      setFileProgress(null);
      setCurrentItem(null);
      append("info", "Checking that DreamForge can see the downloaded assets…");
      try {
        const verify = await verifyDownloads(model, missing);
        if (verify.ready) {
          append("ok", "All required companions are now on disk.");
          setPhase(failures > 0 ? "error" : "done");
        } else {
          append(
            "warn",
            `DreamForge still cannot see ${verify.stillMissing.length} required asset(s):`,
          );
          for (const m of verify.stillMissing) {
            append(
              "warn",
              `  • ${itemLabel(m)}${m.relative ? ` → ${m.relative}` : ""}${m.note ? ` — ${m.note}` : ""}`,
            );
          }
          setPhase("error");
        }
      } catch (e) {
        append("error", `Verification failed: ${String(e)}`);
        setPhase("error");
      }
    },
    [append, verifyDownloads],
  );

  const start = useCallback(
    (model: string, missing: ModelDependencyItem[]) => {
      setOpen(true);
      setPhase("confirm");
      setLines([]);
      setCurrentIndex(0);
      setTotalCount(missing.length);
      setCurrentItem(null);
      setFileProgress(null);
      setModelName(model);
      setPendingMissing(missing);
      append("info", `Model: ${model}`);
      append("info", `${missing.length} required asset(s) need your approval before download.`);
      for (const item of missing.slice(0, 8)) {
        append("info", `  • ${itemLabel(item)}${item.relative ? ` → ${item.relative}` : ""}`);
      }
      if (missing.length > 8) append("info", `  • ${missing.length - 8} more…`);
    },
    [append],
  );

  const approve = useCallback(() => {
    if (!modelName) return;
    void runDownload(modelName, pendingMissing);
  }, [modelName, pendingMissing, runDownload]);

  const copyLinks = useCallback(async () => {
    const links = pendingMissing
      .map((item) => item.url)
      .filter((url): url is string => Boolean(url?.trim()));
    if (links.length === 0) {
      append("warn", "No direct download links are configured for these assets.");
      return;
    }
    try {
      await navigator.clipboard.writeText([...new Set(links)].join("\n"));
      append("ok", `Copied ${new Set(links).size} download link(s) to clipboard.`);
    } catch (e) {
      append("error", `Could not copy links: ${String(e)}`);
    }
  }, [append, pendingMissing]);

  const copyManualList = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(manualInstallText(modelName, pendingMissing));
      append("ok", "Copied manual download/install list to clipboard.");
    } catch (e) {
      append("error", `Could not copy manual list: ${String(e)}`);
    }
  }, [append, modelName, pendingMissing]);

  const retry = useCallback(() => {
    if (!modelName) return;
    void verifyDownloads(modelName, pendingMissing).then((verify) => {
      void runDownload(modelName, verify.stillMissing.length ? verify.stillMissing : pendingMissing);
    });
  }, [modelName, pendingMissing, runDownload, verifyDownloads]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && phase !== "running") close();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, phase, close]);

  return useMemo(
    () => ({
      open,
      phase,
      lines,
      currentIndex,
      totalCount,
      currentItem,
      fileProgress,
      modelName,
      pendingMissing,
      busy: phase === "running",
      start,
      approve,
      copyLinks,
      copyManualList,
      close,
      retry,
    }),
    [
      open,
      phase,
      lines,
      currentIndex,
      totalCount,
      currentItem,
      fileProgress,
      modelName,
      pendingMissing,
      start,
      approve,
      copyLinks,
      copyManualList,
      close,
      retry,
    ],
  );
}
