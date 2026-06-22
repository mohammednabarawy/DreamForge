import { AtSign, Download, LayoutGrid, Play, Sparkles, Square, Wand2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import type { GenerationSettings } from "../lib/tauri-api";
import type { StudioMode } from "../lib/model-selection";
import {
  isSimpleExperience,
  studioModesForExperience,
  type UiExperience,
} from "../lib/experienceUi";
import { detectAgentPromptHint } from "../lib/parseAgentPrompt";
import {
  activeReferenceMode,
  handleImagePathDragOver,
  readImagePathFromDrop,
  type ReferenceImageMode,
} from "../lib/referenceImage";
import { ReferenceImageControl } from "./ReferenceImageControl";
import { PromptToolsMenu } from "./PromptToolsMenu";
import { IdeogramCaptionTemplatesMenu } from "./IdeogramCaptionTemplatesMenu";
import { IdeogramJsonPreview } from "./IdeogramJsonPreview";
import { IdeogramLayoutModal } from "./IdeogramLayoutModal";
import {
  listenForIdeogramLayoutApply,
  openIdeogramLayoutWindow,
} from "../lib/ideogramLayoutWindow";

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
  companionBlockedOnly?: boolean;
  generateBlockReason?: string;
  needsCompanionDownload?: boolean;
  missingCompanionCount?: number;
  companionDownloadBusy?: boolean;
  onDownloadCompanions?: () => void;
  onDryRun: () => void;
  onEnhancePrompt?: () => void;
  enhancePromptBusy?: boolean;
  onGenerate: () => void;
  onGenerateVariants?: (count: number) => void;
  imageNumberMax?: number;
  onCancel: () => void;
  onAttachReferenceImage: (path: string, mode: ReferenceImageMode) => void;
  onAttachExtraReferenceImage?: (path: string) => void;
  onRemoveExtraReferenceImage?: (index: number) => void;
  onClearReferenceImage: () => void;
  onOpenInpaintMask?: () => void;
  activeModelLabel: string;
  referenceModelFamily?: string;
  experience?: UiExperience;
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
  companionBlockedOnly = false,
  generateBlockReason,
  needsCompanionDownload = false,
  missingCompanionCount = 0,
  companionDownloadBusy = false,
  onDownloadCompanions,
  onDryRun,
  onEnhancePrompt,
  enhancePromptBusy = false,
  onGenerate,
  onGenerateVariants,
  imageNumberMax = 8,
  onCancel,
  onAttachReferenceImage,
  onAttachExtraReferenceImage,
  onRemoveExtraReferenceImage,
  onClearReferenceImage,
  onOpenInpaintMask,
  activeModelLabel,
  referenceModelFamily,
  experience = "pro",
}: Props) {
  const simpleExperience = isSimpleExperience(experience);
  const [mentionQuery, setMentionQuery] = useState<string | null>(null);
  const [promptDragOver, setPromptDragOver] = useState(false);
  const [ideogramLayoutOpen, setIdeogramLayoutOpen] = useState(false);
  const isAgentMode = studioMode === "agent";
  const isIdeogramModel = activeModelLabel.toLowerCase().includes("ideogram");
  const promptText = (settings.prompt ?? "").trim();
  const canEnhancePrompt =
    !isAgentMode &&
    studioMode === "generate" &&
    Boolean(promptText) &&
    !generating &&
    !enhancePromptBusy;
  const primaryActionLabel = "Generate";
  const simpleBatchCount = Math.min(4, Math.max(2, imageNumberMax >= 4 ? 4 : imageNumberMax));
  const dropReferenceMode = (): ReferenceImageMode => {
    if (studioMode === "inpaint") return "inpaint";
    if (studioMode === "upscale") return "upscale";
    return activeReferenceMode(settings);
  };
  const showSimpleBatch =
    simpleExperience &&
    studioMode === "generate" &&
    !isAgentMode &&
    simpleBatchCount > 1 &&
    Boolean(onGenerateVariants);
  const showPostUpscaleToggle =
    !isAgentMode && (studioMode === "edit" || studioMode === "inpaint");
  const canRunPrimary =
    isAgentMode && !generating
      ? Boolean((settings.prompt ?? "").trim())
      : canGenerate || companionBlockedOnly;
  const generateButtonTitle =
    canRunPrimary && companionBlockedOnly && !canGenerate
      ? `Download ${missingCompanionCount} missing asset(s) to continue`
      : canRunPrimary
        ? undefined
        : isAgentMode
          ? "Enter an instruction for the agent"
          : needsCompanionDownload
            ? "Generate to review and download missing assets"
            : generateBlockReason || "Cannot generate yet";

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

  useEffect(() => {
    let disposed = false;
    let unlisten: (() => void) | null = null;
    void listenForIdeogramLayoutApply(({ caption }) => {
      onChange({ prompt: caption, ideogram4_prompt_mode: "structured" });
    }).then((fn) => {
      if (disposed) fn();
      else unlisten = fn;
    });
    return () => {
      disposed = true;
      if (unlisten) unlisten();
    };
  }, [onChange]);

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
  const activeRouteLabel =
    studioMode === "agent" && agentPlannedMode
      ? `Planned ${agentPlannedMode}: ${activeModelLabel}`
      : studioMode === "generate"
        ? activeModelLabel
        : `Selected: ${activeModelLabel}`;
  const modes = studioModesForExperience(experience);

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

  const openLayoutBuilder = async () => {
    try {
      const opened = await openIdeogramLayoutWindow(settings);
      if (!opened) setIdeogramLayoutOpen(true);
    } catch {
      setIdeogramLayoutOpen(true);
    }
  };

  return (
    <div
      className={`df-command-deck relative shrink-0 border-t border-dfui-border/60 bg-dfui-panel/90 px-3 py-2 backdrop-blur-glass transition-colors ${
        promptDragOver ? "ring-1 ring-inset ring-df-blue/30" : ""
      }`}
      onDragEnterCapture={(event) => {
        if (handleImagePathDragOver(event, generating)) setPromptDragOver(true);
      }}
      onDragOverCapture={(event) => {
        if (handleImagePathDragOver(event, generating)) setPromptDragOver(true);
      }}
      onDragEnter={(event) => {
        if (handleImagePathDragOver(event, generating)) setPromptDragOver(true);
      }}
      onDragOver={(event) => {
        if (handleImagePathDragOver(event, generating)) setPromptDragOver(true);
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
          onAttachReferenceImage(path, dropReferenceMode());
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
      <motion.div className="df-command-route-row mb-1.5 flex min-w-0 items-center gap-2">
        <div className="flex min-w-0 shrink-0 items-center gap-1 overflow-x-auto rounded-lg border border-dfui-border/45 bg-dfui-bg/35 p-1">
          {modes.map((mode) => (
            <button
              key={mode.id}
              type="button"
              onClick={() => onStudioModeChange(mode.id)}
              disabled={generating}
              className={`min-h-8 shrink-0 rounded-md px-2.5 text-[10px] font-medium transition-colors ${
                studioMode === mode.id
                  ? "bg-dfui-accent/20 text-dfui-accent"
                  : "text-dfui-muted hover:bg-dfui-surface hover:text-dfui-fg"
              } disabled:opacity-60`}
            >
              {mode.label}
            </button>
          ))}
        </div>
        {!simpleExperience ? (
        <div className="flex min-h-8 min-w-0 flex-1 items-center gap-2 rounded-lg border border-dfui-border/45 bg-dfui-bg/30 px-2">
          <p className="shrink-0 text-[9px] uppercase tracking-wide text-dfui-muted">
            {studioMode === "generate" ? "Model" : "Route"}
          </p>
          <p className="truncate font-mono text-[10px] text-dfui-accent" title={activeRouteLabel}>
            {activeRouteLabel}
          </p>
        </div>
        ) : (
        <div className="hidden min-h-8 min-w-0 flex-1 items-center px-2 text-[10px] text-dfui-muted md:flex">
          {studioMode === "generate"
            ? "Describe what you want to create"
            : studioMode === "edit"
              ? "Describe what should change"
              : studioMode === "inpaint"
                ? "Paint a region, then describe the fix"
                : studioMode === "extract"
                  ? "Extract structure, depth, or pose from image"
                  : "Enhance resolution of your image"}
        </div>
        )}
        <div className="hidden shrink-0 items-center justify-end text-[10px] text-dfui-muted 2xl:flex">
          {agentHint ?? (promptDragOver ? "Drop image to attach" : "@mentions · drag images in")}
        </div>
      </motion.div>
      <div className="df-command-main-grid">
        <div className="min-w-0 self-stretch">
          <ReferenceImageControl
            settings={settings}
            modelFamily={referenceModelFamily}
            studioMode={studioMode}
            simpleAttach={simpleExperience}
            onAttach={onAttachReferenceImage}
            onAttachExtra={onAttachExtraReferenceImage}
            onRemoveExtra={onRemoveExtraReferenceImage}
            onClear={onClearReferenceImage}
            onOpenInpaintMask={onOpenInpaintMask}
            onEditStrengthChange={(edit_strength) => onChange({ edit_strength })}
            disabled={generating}
            compact
          />
        </div>
        <div className="flex min-w-0 flex-col gap-1">
          {studioMode === "upscale" ? (
            <textarea
              value={settings.prompt ?? ""}
              onChange={(e) => onPromptChange(e.target.value)}
              rows={2}
              placeholder="Optional enhancement — leave empty for auto restoration prompt"
              className="df-textarea-glowing min-h-[48px] flex-1 py-1.5 text-xs leading-snug"
            />
          ) : (
          <div className="flex min-w-0 items-stretch gap-1.5">
            <textarea
              value={settings.prompt ?? ""}
              onChange={(e) => onPromptChange(e.target.value)}
              rows={2}
              placeholder={
                isAgentMode
                  ? "Tell the agent what you want. Example: edit this poster, preserve Arabic text, make it cinematic"
                  : "Describe the shot… Type @ to pick a model or style"
              }
              className="df-textarea-glowing min-h-[48px] flex-1 py-1.5 text-xs leading-snug"
            />
            {!isAgentMode && studioMode === "generate" && onEnhancePrompt ? (
              <motion.button
                whileHover={{ scale: canEnhancePrompt ? 1.04 : 1 }}
                whileTap={{ scale: canEnhancePrompt ? 0.96 : 1 }}
                type="button"
                onClick={onEnhancePrompt}
                disabled={!canEnhancePrompt}
                title={
                  enhancePromptBusy
                    ? "Enhancing prompt…"
                    : promptText
                      ? `Enhance prompt for ${activeModelLabel || "selected model"} (${studioMode})`
                      : "Enter a prompt to enhance"
                }
                aria-label="Enhance prompt"
                className="inline-flex h-[48px] w-8 shrink-0 items-center justify-center rounded-lg border border-dfui-border/60 bg-dfui-bg/40 text-dfui-muted transition-colors hover:border-df-blue/45 hover:text-df-blue disabled:cursor-not-allowed disabled:opacity-45"
              >
                <Wand2 size={15} className={enhancePromptBusy ? "animate-pulse" : ""} />
              </motion.button>
            ) : null}
          </div>
          )}
          {isIdeogramModel && !isAgentMode && studioMode !== "upscale" ? (
            <IdeogramJsonPreview prompt={settings.prompt ?? ""} enabled={isIdeogramModel} />
          ) : null}
          <div className="df-prompt-action-row flex min-h-8 items-center justify-between gap-2">
            <p className="truncate text-[10px] text-dfui-muted xl:hidden">
              {agentHint ??
                (promptDragOver
                  ? "Drop to attach as reference image"
                  : "@mentions · drag history image to prompt bar")}
            </p>
            <div className="ml-auto flex shrink-0 flex-wrap justify-end gap-1.5">
              {isIdeogramModel && !isAgentMode && studioMode === "generate" ? (
                <>
                  <IdeogramCaptionTemplatesMenu
                    settings={settings}
                    onChange={onChange}
                    disabled={generating}
                  />
                  <button
                  type="button"
                  disabled={generating}
                  onClick={() => void openLayoutBuilder()}
                  className="inline-flex min-h-8 items-center gap-1 rounded-lg border border-dfui-border/50 px-2.5 text-xs text-dfui-fg transition-colors hover:border-dfui-accent/40 disabled:opacity-50"
                  title="Visual layout builder for Ideogram JSON"
                >
                  <LayoutGrid size={13} className="text-dfui-accent" />
                  Layout
                </button>
                </>
              ) : null}
              {!simpleExperience ? (
              <PromptToolsMenu
                settings={settings}
                onChange={onChange}
                disabled={generating || studioMode === "edit" || studioMode === "inpaint"}
              />
              ) : null}
              {!simpleExperience ? (
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                type="button"
                onClick={onDryRun}
                disabled={generating}
                className="inline-flex min-h-8 items-center gap-1.5 rounded-lg border border-dfui-border px-2.5 text-xs text-dfui-fg transition-colors hover:border-df-blue/40 disabled:opacity-50"
              >
                <Sparkles size={13} className="text-df-blue" />
                {isAgentMode ? "Ask" : "Dry run"}
              </motion.button>
              ) : null}
              {showPostUpscaleToggle ? (
                <label
                  className="inline-flex min-h-8 cursor-pointer items-center gap-1.5 rounded-lg border border-dfui-border/50 px-2.5 text-xs text-dfui-fg transition-colors hover:border-df-orange/40"
                  title="After edit or inpaint, run Ultimate SD Upscale"
                >
                  <input
                    type="checkbox"
                    className="accent-df-orange"
                    checked={Boolean(settings.post_upscale_enabled)}
                    disabled={generating}
                    onChange={(e) =>
                      onChange({ post_upscale_enabled: e.target.checked })
                    }
                  />
                  Sharpen 2×
                </label>
              ) : null}
              {generating ? (
                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  type="button"
                  onClick={onCancel}
                  className="inline-flex min-h-8 items-center gap-1.5 rounded-lg border border-red-500/50 bg-red-500/10 px-3 text-xs font-semibold text-red-300 transition-all hover:bg-red-500/20"
                >
                  <Square size={13} className="text-red-400" />
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
                      className="inline-flex min-h-8 items-center gap-1.5 rounded-lg border border-df-blue/50 bg-df-blue/15 px-2.5 text-xs font-semibold text-df-blue transition-colors hover:border-df-blue/70 hover:bg-df-blue/25 disabled:cursor-wait disabled:opacity-60"
                    >
                      <Download
                        size={13}
                        className={companionDownloadBusy ? "animate-pulse" : undefined}
                      />
                      {companionDownloadBusy
                        ? "Downloading"
                        : missingCompanionCount > 0
                          ? `Download ${missingCompanionCount}`
                          : "Download"}
                    </motion.button>
                  )}
                  {showSimpleBatch && (
                    <motion.button
                      whileHover={canRunPrimary ? { scale: 1.02 } : {}}
                      whileTap={canRunPrimary ? { scale: 0.98 } : {}}
                      type="button"
                      onClick={() => onGenerateVariants?.(simpleBatchCount)}
                      disabled={!canRunPrimary}
                      title={
                        canRunPrimary
                          ? `Generate ${simpleBatchCount} variants in one run`
                          : generateButtonTitle
                      }
                      className="inline-flex min-h-8 items-center gap-1.5 rounded-lg border border-dfui-border/60 bg-dfui-bg/40 px-2.5 text-xs font-medium text-dfui-fg transition-colors hover:border-df-orange/45 hover:text-df-orange disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      <LayoutGrid size={13} />
                      {simpleBatchCount} variants
                    </motion.button>
                  )}
                  <motion.button
                    whileHover={
                      canRunPrimary
                        ? { scale: 1.02, boxShadow: "0 0 15px rgba(247, 148, 30, 0.4)" }
                        : {}
                    }
                    whileTap={canRunPrimary ? { scale: 0.98 } : {}}
                    type="button"
                    onClick={onGenerate}
                    disabled={!canRunPrimary}
                    title={generateButtonTitle}
                    className="inline-flex min-h-8 items-center gap-1.5 rounded-lg bg-gradient-to-r from-df-orange to-df-orange-deep px-3.5 text-xs font-bold text-white transition-all disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <Play size={13} fill="currentColor" />
                    {primaryActionLabel}
                  </motion.button>
                </>
              )}
            </div>
          </div>
        </div>
      </div>
      <IdeogramLayoutModal
        open={ideogramLayoutOpen}
        settings={settings}
        onClose={() => setIdeogramLayoutOpen(false)}
        onApply={(caption) => onChange({ prompt: caption, ideogram4_prompt_mode: "structured" })}
      />
    </div>
  );
}
