import {
  FolderOpen,
  LayoutGrid,
  Play,
  RefreshCw,
  FileText,
  FileJson,
  Images,
} from "lucide-react";
import { useAutomation, type AutomationType } from "../hooks/useAutomation";
import type { GenerationSettings, ModelGalleryItem } from "../lib/tauri-api";
import type { StudioMode } from "../lib/model-selection";
import { pickFolder, pickTextFile } from "../lib/tauri-api";
import type { AutomationPreview } from "../lib/studioBridge";

type PreviewJob = NonNullable<AutomationPreview["jobs"]>[number];

type Props = {
  settings: GenerationSettings;
  studioMode: StudioMode;
  modelGallery: ModelGalleryItem[];
  advancedMode?: boolean;
  vramGb?: number | null;
  mpsAvailable?: boolean | null;
  generating: boolean;
  onStatus: (message: string) => void;
  onRefreshOutputs: () => void;
  onBeforeRun?: () => Promise<boolean>;
  onRevealPath: (path: string) => void;
  onRunBatch: (runner: () => Promise<{ ok: boolean }>) => void;
};

const TYPE_OPTIONS: Array<{
  id: AutomationType;
  label: string;
  hint: string;
  icon: typeof LayoutGrid;
}> = [
  {
    id: "seed_batch",
    label: "Seed batch",
    hint: "Same prompt, different seeds",
    icon: LayoutGrid,
  },
  {
    id: "recipe_batch",
    label: "Recipe batch",
    hint: "Recipe v2 with a seed sweep",
    icon: FileJson,
  },
  {
    id: "recipe_folder",
    label: "Recipe queue",
    hint: "Queue every Recipe v2 JSON in a folder",
    icon: FolderOpen,
  },
  {
    id: "prompt_lines",
    label: "Prompt lines",
    hint: "One .txt file, one line per job",
    icon: FileText,
  },
  {
    id: "prompt_folder",
    label: "Prompt folder",
    hint: "Every .txt in a folder",
    icon: FolderOpen,
  },
  {
    id: "input_folder",
    label: "Input folder",
    hint: "Batch upscale or edit every image",
    icon: Images,
  },
];

function basename(path: string): string {
  const parts = path.split(/[/\\]/);
  return parts[parts.length - 1] || path;
}

export function AutomationPanel({
  settings,
  studioMode,
  modelGallery,
  advancedMode,
  vramGb,
  mpsAvailable,
  generating,
  onStatus,
  onRefreshOutputs,
  onBeforeRun,
  onRevealPath,
  onRunBatch,
}: Props) {
  const automation = useAutomation({
    settings,
    studioMode,
    modelGallery,
    advancedMode,
    vramGb,
    mpsAvailable,
    generating,
    onStatus,
    onRefreshOutputs,
    onBeforeRun,
  });

  const needsInput = automation.automationType !== "seed_batch";

  return (
    <div className="flex h-full min-h-0 flex-col gap-3 overflow-y-auto p-1">
      <div>
        <p className="text-[10px] font-semibold uppercase tracking-wide text-dfui-muted">
          Batch automation
        </p>
        <p className="mt-0.5 text-[11px] leading-snug text-dfui-tertiary">
          Run many jobs sequentially with export to a folder. Uses current
          generation settings and creative template.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-1.5">
        {TYPE_OPTIONS.map((opt) => {
          const Icon = opt.icon;
          const active = automation.automationType === opt.id;
          return (
            <button
              key={opt.id}
              type="button"
              disabled={generating}
              onClick={() => automation.setAutomationType(opt.id)}
              className={`rounded-lg border px-2 py-2 text-left transition-colors ${
                active
                  ? "border-df-orange/55 bg-df-orange/10"
                  : "border-dfui-border/50 bg-dfui-bg/30 hover:border-dfui-border"
              } disabled:opacity-50`}
            >
              <span className="flex items-center gap-1.5 text-xs font-medium text-dfui-fg">
                <Icon size={13} className="shrink-0 text-df-orange" />
                {opt.label}
              </span>
              <span className="mt-0.5 block text-[10px] leading-snug text-dfui-tertiary">
                {opt.hint}
              </span>
            </button>
          );
        })}
      </div>

      {automation.automationType === "seed_batch" || automation.automationType === "recipe_batch" ? (
        <div className="grid grid-cols-3 gap-1.5">
          <label className="col-span-1 block">
            <span className="text-xs text-dfui-muted">Jobs</span>
            <input
              type="number"
              min={1}
              max={64}
              value={automation.count}
              disabled={generating}
              onChange={(e) =>
                automation.setCount(Math.max(1, Number(e.target.value) || 1))
              }
              className="df-input mt-1 w-full px-2.5 py-1.5 font-mono text-xs"
            />
          </label>
          <label className="col-span-1 block">
            <span className="text-xs text-dfui-muted">Seed start</span>
            <input
              type="number"
              value={automation.seedStart}
              disabled={generating}
              placeholder="auto"
              onChange={(e) => automation.setSeedStart(e.target.value)}
              className="df-input mt-1 w-full px-2.5 py-1.5 font-mono text-xs"
            />
          </label>
          <label className="col-span-1 block">
            <span className="text-xs text-dfui-muted">Step</span>
            <input
              type="number"
              value={automation.seedStep}
              disabled={generating}
              onChange={(e) => automation.setSeedStep(e.target.value)}
              className="df-input mt-1 w-full px-2.5 py-1.5 font-mono text-xs"
            />
          </label>
        </div>
      ) : null}

      {needsInput ? (
        <div className="space-y-2">
          <label className="block">
            <span className="text-xs text-dfui-muted">
              {automation.automationType === "prompt_lines"
                ? "Prompt file"
                : automation.automationType === "recipe_batch"
                  ? "Recipe v2 file"
                  : automation.automationType === "recipe_folder"
                    ? "Recipe folder"
                    : "Input folder"}
            </span>
            <div className="mt-1 flex gap-1.5">
              <input
                readOnly
                value={automation.inputPath}
                placeholder="Choose path…"
                className="df-input min-w-0 flex-1 px-2.5 py-1.5 text-xs"
              />
              <button
                type="button"
                disabled={generating}
                onClick={async () => {
                  if (
                    automation.automationType === "prompt_lines" ||
                    automation.automationType === "recipe_batch"
                  ) {
                    const picked = await pickTextFile();
                    if (picked) automation.setInputPath(picked);
                  } else {
                    const picked = await pickFolder();
                    if (picked) automation.setInputPath(picked);
                  }
                }}
                className="shrink-0 rounded-lg border border-dfui-border/60 px-2.5 text-xs text-dfui-fg hover:border-df-blue/45"
              >
                Browse
              </button>
            </div>
            {automation.inputPath ? (
              <span className="mt-1 block truncate text-[10px] text-dfui-tertiary">
                {basename(automation.inputPath)}
              </span>
            ) : null}
          </label>

          {automation.automationType === "input_folder" ? (
            <label className="block">
              <span className="text-xs text-dfui-muted">Task per image</span>
              <select
                value={automation.inputFolderMode}
                disabled={generating}
                onChange={(e) =>
                  automation.setInputFolderMode(e.target.value as StudioMode)
                }
                className="df-select mt-1 w-full px-2.5 py-2 text-xs"
              >
                <option value="upscale">Enhance (upscale)</option>
                <option value="edit">Edit</option>
                <option value="inpaint">Fix region (needs mask per image)</option>
              </select>
            </label>
          ) : null}
        </div>
      ) : null}

      <label className="block">
        <span className="text-xs text-dfui-muted">Export folder (optional)</span>
        <div className="mt-1 flex gap-1.5">
          <input
            readOnly
            value={automation.outputDir}
            placeholder="Session outputs if empty"
            className="df-input min-w-0 flex-1 px-2.5 py-1.5 text-xs"
          />
          <button
            type="button"
            disabled={generating}
            onClick={async () => {
              const picked = await pickFolder();
              if (picked) automation.setOutputDir(picked);
            }}
            className="shrink-0 rounded-lg border border-dfui-border/60 px-2.5 text-xs text-dfui-fg hover:border-df-blue/45"
          >
            Browse
          </button>
        </div>
      </label>

      <div className="rounded-lg border border-dfui-border/45 bg-dfui-bg/25 px-2.5 py-2">
        <div className="flex items-center justify-between gap-2">
          <span className="text-[10px] font-semibold uppercase tracking-wide text-dfui-muted">
            Preview
          </span>
          <button
            type="button"
            disabled={generating || automation.previewBusy}
            onClick={() => void automation.refreshPreview()}
            className="inline-flex items-center gap-1 text-[10px] text-dfui-tertiary hover:text-dfui-fg"
          >
            <RefreshCw
              size={11}
              className={automation.previewBusy ? "animate-spin" : undefined}
            />
            Refresh
          </button>
        </div>
        <p className="mt-1 text-xs text-dfui-fg">
          {automation.previewBusy
            ? "Counting jobs…"
            : automation.preview?.message
              ? automation.preview.message
            : `${automation.preview?.job_count ?? 0} job(s) queued`}
        </p>
        {automation.preview?.jobs?.length ? (
          <ul className="mt-1 max-h-24 space-y-0.5 overflow-y-auto text-[10px] text-dfui-tertiary">
            {automation.preview.jobs.slice(0, 8).map((job: PreviewJob) => (
              <li key={job.index} className="truncate">
                {job.index}. {job.label}
              </li>
            ))}
            {(automation.preview.job_count ?? 0) > 8 ? (
              <li>…and {(automation.preview.job_count ?? 0) - 8} more</li>
            ) : null}
          </ul>
        ) : null}
      </div>

      <div className="mt-auto flex flex-wrap gap-2 pt-1">
        <button
          type="button"
          disabled={!automation.canRun}
          onClick={() =>
            onRunBatch(async () => {
              const result = await automation.runBatch();
              return { ok: result.ok };
            })
          }
          className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-gradient-to-r from-df-orange to-df-orange-deep px-3 py-2 text-xs font-bold text-white disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Play size={13} fill="currentColor" />
          Run batch
        </button>
        {automation.lastOutputDir ? (
          <button
            type="button"
            onClick={() => onRevealPath(automation.lastOutputDir!)}
            className="inline-flex items-center gap-1.5 rounded-lg border border-dfui-border/60 px-3 py-2 text-xs text-dfui-fg hover:border-df-blue/45"
          >
            <FolderOpen size={13} />
            Open export
          </button>
        ) : null}
      </div>
    </div>
  );
}
