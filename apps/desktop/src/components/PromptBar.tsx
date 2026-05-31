import { AtSign, Download, Play, Sparkles, Square } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import type { GenerationSettings } from "../lib/tauri-api";
import type { StudioMode } from "../lib/model-selection";
import type { EditFamilyPlanState } from "../lib/generationReadiness";
import { detectAgentPromptHint } from "../lib/parseAgentPrompt";
import {
  activeReferenceMode,
  readImagePathFromDrop,
  type ReferenceImageMode,
} from "../lib/referenceImage";
import { ReferenceImageControl } from "./ReferenceImageControl";
import { PromptToolsMenu } from "./PromptToolsMenu";

type Mention = { kind: "model" | "style"; label: string; value: string };

type Props = {
  settings: GenerationSettings;
  studioMode: StudioMode;
  agentPlannedMode?: StudioMode | null;
  onStudioModeChange: (mode: StudioMode) => void;
  onChange: (patch: Partial<GenerationSettings>) => void;
  mentions: Mention[];
  generating: boolean;
  workerReady: boolean;
  canGenerate: boolean;
  generateBlockReason?: string;
  needsCompanionDownload?: boolean;
  missingCompanionCount?: number;
  companionDownloadBusy?: boolean;
  onDownloadCompanions?: () => void;
  onDryRun: () => void;
  onGenerate: () => void;
  onCancel: () => void;
  onAttachReferenceImage: (path: string, mode: ReferenceImageMode) => void;
  onAttachExtraReferenceImage?: (path: string) => void;
  onRemoveExtraReferenceImage?: (index: number) => void;
  onClearReferenceImage: () => void;
  onOpenInpaintMask?: () => void;
  activeModelLabel: string;
  referenceModelFamily?: string;
  editPlanState?: EditFamilyPlanState;
};

export function PromptBar({
  settings,
  studioMode,
  agentPlannedMode,
  onStudioModeChange,
  onChange,
  mentions,
  generating,
  workerReady: _workerReady,
  canGenerate,
  generateBlockReason,
  needsCompanionDownload = false,
  missingCompanionCount = 0,
  companionDownloadBusy = false,
  onDownloadCompanions,
  onDryRun,
  onGenerate,
  onCancel,
  onAttachReferenceImage,
  onAttachExtraReferenceImage,
  onRemoveExtraReferenceImage,
  onClearReferenceImage,
  onOpenInpaintMask,
  activeModelLabel,
  referenceModelFamily,
  editPlanState = "none",
}: Props) {
  const [mentionQuery, setMentionQuery] = useState<string | null>(null);
  const [promptDragOver, setPromptDragOver] = useState(false);
  const isAgentMode = studioMode === "agent";
  const isEditFamily =
    studioMode === "edit" || studioMode === "inpaint" || studioMode === "upscale";
  const primaryActionLabel = isAgentMode
    ? "Apply & open route"
    : isEditFamily
      ? editPlanState === "ready"
        ? "Run plan"
        : editPlanState === "stale"
          ? "Refresh plan"
          : "Plan run"
      : "Generate";
  const canRunPrimary =
    isAgentMode && !generating
      ? Boolean((settings.prompt ?? "").trim())
      : canGenerate;

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
        e.preventDefault();
        if (generating) onCancel();
        else if (canRunPrimary) onGenerate();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [generating, canRunPrimary, onGenerate, onCancel]);

  const filtered = useMemo(() => {
    if (mentionQuery === null) return [];
    const q = mentionQuery.toLowerCase();
    return mentions
      .filter((m) => m.label.toLowerCase().includes(q))
      .slice(0, 12);
  }, [mentionQuery, mentions]);

  const agentHint = useMemo(
    () => detectAgentPromptHint(settings.prompt),
    [settings.prompt],
  );
  const modes: Array<{ id: StudioMode; label: string }> = [
    { id: "generate", label: "Generate" },
    { id: "edit", label: "Edit" },
    { id: "inpaint", label: "Inpaint" },
    { id: "upscale", label: "Upscale" },
    { id: "agent", label: "Agent" },
  ];

  const onPromptChange = (value: string) => {
    onChange({ prompt: value });
    const at = value.lastIndexOf("@");
    if (at >= 0 && (at === 0 || /\s/.test(value[at - 1] ?? ""))) {
      setMentionQuery(value.slice(at + 1));
    } else {
      setMentionQuery(null);
    }
  };

  const applyMention = (m: Mention) => {
    const base = (settings.prompt ?? "").replace(/@[^\s]*$/, "").trimEnd();
    if (m.kind === "model") {
      onChange({ prompt: base, model: m.value });
    } else {
      onChange({ prompt: base, style: m.value });
    }
    setMentionQuery(null);
  };

  return (
    <div
      className={`relative border-t border-dfui-border/60 bg-dfui-panel/85 p-3 backdrop-blur-glass transition-colors ${
        promptDragOver ? "ring-1 ring-inset ring-df-blue/30" : ""
      }`}
      onDragEnter={(event) => {
        event.preventDefault();
        if (!generating) setPromptDragOver(true);
      }}
      onDragOver={(event) => {
        event.preventDefault();
        if (!generating) setPromptDragOver(true);
      }}
      onDragLeave={(event) => {
        if (!(event.currentTarget as HTMLElement).contains(
          event.relatedTarget as Node,
        )) {
          setPromptDragOver(false);
        }
      }}
      onDrop={(event) => {
        event.preventDefault();
        setPromptDragOver(false);
        const path = readImagePathFromDrop(event.dataTransfer);
        if (path) {
          onAttachReferenceImage(path, activeReferenceMode(settings));
        }
      }}
    >
      {filtered.length > 0 && (
        <ul className="absolute bottom-full left-3 right-3 mb-1 max-h-48 overflow-y-auto rounded-lg border border-dfui-border bg-dfui-panel shadow-glass">
          {filtered.map((m) => (
            <li key={`${m.kind}-${m.value}`}>
              <button
                type="button"
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs hover:bg-dfui-surface-hover"
                onClick={() => applyMention(m)}
              >
                <AtSign size={12} className="text-dfui-accent" />
                <span className="text-dfui-muted">{m.kind}</span>
                <span className="truncate text-dfui-fg">{m.label}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      <motion.div className="mb-2 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-dfui-border/50 bg-dfui-bg/40 px-2.5 py-1.5">
        <div className="flex gap-1">
          {modes.map((mode) => (
            <button
              key={mode.id}
              type="button"
              onClick={() => onStudioModeChange(mode.id)}
              disabled={generating}
              className={`rounded-md px-2 py-1 text-[10px] font-medium transition-colors ${
                studioMode === mode.id
                  ? "bg-dfui-accent/20 text-dfui-accent"
                  : "text-dfui-muted hover:bg-dfui-surface hover:text-dfui-fg"
              } disabled:opacity-60`}
            >
              {mode.label}
            </button>
          ))}
        </div>
        <div className="flex min-w-0 items-center gap-2">
          <p className="shrink-0 text-[10px] uppercase tracking-wide text-dfui-muted">
            {studioMode === "generate" ? "Model" : "Route"}
          </p>
          <p className="truncate font-mono text-[11px] text-dfui-accent">
            {studioMode === "agent" && agentPlannedMode
              ? `Planned ${agentPlannedMode}: ${activeModelLabel}`
              : studioMode === "generate"
                ? activeModelLabel
                : `Auto: ${activeModelLabel}`}
          </p>
        </div>
      </motion.div>
      <div className="mb-2 flex flex-col gap-2 sm:flex-row sm:items-stretch">
        <div className="sm:w-72 shrink-0">
          <ReferenceImageControl
            settings={settings}
            modelFamily={referenceModelFamily}
            onAttach={onAttachReferenceImage}
            onAttachExtra={onAttachExtraReferenceImage}
            onRemoveExtra={onRemoveExtraReferenceImage}
            onClear={onClearReferenceImage}
            onOpenInpaintMask={onOpenInpaintMask}
            onEditStrengthChange={(edit_strength) => onChange({ edit_strength })}
            disabled={generating}
          />
        </div>
        <textarea
          value={settings.prompt ?? ""}
          onChange={(e) => onPromptChange(e.target.value)}
          rows={3}
          placeholder={
            isAgentMode
              ? "Tell the agent what you want. Example: edit this poster, preserve Arabic text, make it cinematic"
              : "Describe the shot… Type @ to pick a model or style"
          }
          className="df-textarea-glowing min-h-[84px] flex-1"
        />
      </div>
      <motion.div className="mt-2 flex items-center justify-between gap-2">
        <p className="text-[11px] text-dfui-muted">
          {agentHint ??
            (promptDragOver
              ? "Drop to attach as reference image"
              : "@mentions · drag history image to prompt bar")}
        </p>
        <div className="flex gap-2">
          <PromptToolsMenu
            settings={settings}
            onChange={onChange}
            disabled={generating}
          />
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            type="button"
            onClick={onDryRun}
            disabled={generating}
            className="inline-flex items-center gap-1.5 rounded-lg border border-dfui-border px-3 py-1.5 text-xs text-dfui-fg hover:border-df-blue/40 disabled:opacity-50 transition-colors"
          >
            <Sparkles size={14} className="text-df-blue" />
            {isAgentMode ? "Ask agent" : "Dry run"}
          </motion.button>
          {generating ? (
            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              type="button"
              onClick={onCancel}
              className="inline-flex items-center gap-1.5 rounded-lg border border-red-500/50 bg-red-500/10 px-4 py-1.5 text-xs font-semibold text-red-300 hover:bg-red-500/20 transition-all shadow-glow-orange/10"
            >
              <Square size={14} className="text-red-400" />
              Cancel
            </motion.button>
          ) : (
            <>
              {needsCompanionDownload && onDownloadCompanions && (
                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  type="button"
                  onClick={onDownloadCompanions}
                  disabled={companionDownloadBusy}
                  title={
                    missingCompanionCount > 0
                      ? `Download ${missingCompanionCount} missing companion file(s) for this model`
                      : "Download missing companion files"
                  }
                  className="inline-flex items-center gap-1.5 rounded-lg border border-df-blue/50 bg-df-blue/15 px-3 py-1.5 text-xs font-semibold text-df-blue hover:border-df-blue/70 hover:bg-df-blue/25 disabled:cursor-wait disabled:opacity-60 transition-colors"
                >
                  <Download
                    size={14}
                    className={companionDownloadBusy ? "animate-pulse" : undefined}
                  />
                  {companionDownloadBusy
                    ? "Downloading…"
                    : missingCompanionCount > 0
                      ? `Download (${missingCompanionCount})`
                      : "Download companions"}
                </motion.button>
              )}
              <motion.button
                whileHover={canRunPrimary ? { scale: 1.02, boxShadow: "0 0 15px rgba(247, 148, 30, 0.4)" } : {}}
                whileTap={canRunPrimary ? { scale: 0.98 } : {}}
                type="button"
                onClick={onGenerate}
                disabled={!canRunPrimary}
                title={
                  canRunPrimary
                    ? undefined
                    : isAgentMode
                      ? "Enter an instruction for the agent"
                      : needsCompanionDownload
                      ? "Download companion files first, then generate"
                      : generateBlockReason || "Cannot generate yet"
                }
                className="inline-flex items-center gap-1.5 rounded-lg bg-gradient-to-r from-df-orange to-df-orange-deep px-4 py-1.5 text-xs font-bold text-white disabled:cursor-not-allowed disabled:opacity-50 transition-all"
              >
                <Play size={14} fill="currentColor" />
                {primaryActionLabel}
              </motion.button>
            </>
          )}
        </div>
      </motion.div>
    </div>
  );
}
