import { AtSign, Brain, Download, Focus, LayoutGrid, Maximize2, Minimize2, Play, Sparkles, Square, Wand2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import type { GenerationSettings } from "../lib/tauri-api";
import type { StudioMode } from "../lib/model-selection";
import { easyRouteSummary } from "../lib/easyModeRouting";
import {
  isSimpleExperience,
  studioModesForExperience,
  type UiExperience,
} from "../lib/experienceUi";
import { sanitizeSettingsForStudioMode } from "../lib/routeResolution";
import { detectAgentPromptHint } from "../lib/parseAgentPrompt";
import {
  handleImagePathDragOver,
  readImagePathFromDrop,
} from "../lib/referenceImage";
import { SIMPLE_ASPECT_PRESETS } from "../lib/aspectPresets";
import { resolveDescribeImagePath } from "../lib/describeImage";
import { isTypingTarget } from "../lib/keyboard";
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
  onDescribeImage?: () => void;
  describeImageBusy?: boolean;
  describeImagePath?: string;
  onImportImageMetadata?: (path: string) => void;
  onGenerate: () => void;
  onGenerateVariants?: (count: number) => void;
  imageNumberMax?: number;
  onCancel: () => void;
  onAttachReferenceImage: (path: string) => void;
  onAttachExtraReferenceImage?: (path: string) => void;
  onRemoveExtraReferenceImage?: (index: number) => void;
  onClearReferenceImage: () => void;
  onOpenInpaintMask?: () => void;
  /** Leave inline mask editor while the user types in the prompt. */
  onInpaintCanvasFocusChange?: (focused: boolean) => void;
  activeModelLabel: string;
  referenceModelFamily?: string;
  experience?: UiExperience;
  focusMode?: boolean;
  onToggleFocusMode?: () => void;
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
  onDescribeImage,
  describeImageBusy = false,
  describeImagePath,
  onImportImageMetadata,
  onGenerate,
  onGenerateVariants,
  imageNumberMax = 8,
  onCancel,
  onAttachReferenceImage,
  onAttachExtraReferenceImage,
  onRemoveExtraReferenceImage,
  onClearReferenceImage,
  onOpenInpaintMask,
  onInpaintCanvasFocusChange,
  activeModelLabel,
  referenceModelFamily,
  experience = "pro",
  focusMode = false,
  onToggleFocusMode,
}: Props) {
  const simpleExperience = isSimpleExperience(experience);
  const [mentionQuery, setMentionQuery] = useState<string | null>(null);
  const [promptDragOver, setPromptDragOver] = useState(false);
  const [ideogramLayoutOpen, setIdeogramLayoutOpen] = useState(false);
  const [promptExpanded, setPromptExpanded] = useState(false);
  const isAgentMode = studioMode === "agent";
  const isIdeogramModel = activeModelLabel.toLowerCase().includes("ideogram");
  const promptText = (settings.prompt ?? "").trim();
  const canEnhancePrompt =
    !isAgentMode &&
    studioMode === "generate" &&
    Boolean(promptText) &&
    !generating &&
    !enhancePromptBusy;
  const effectiveDescribePath =
    describeImagePath?.trim() ||
    resolveDescribeImagePath(settings, { studioMode });
  const canDescribeImage =
    !isAgentMode &&
    Boolean(effectiveDescribePath) &&
    !generating &&
    !describeImageBusy &&
    Boolean(onDescribeImage);
  const rawImageCount = Number(settings.image_number ?? 1);
  const requestedImageCount = Math.min(
    imageNumberMax,
    Math.max(1, Math.round(Number.isFinite(rawImageCount) ? rawImageCount : 1)),
  );
  const primaryActionLabel =
    studioMode === "generate" && requestedImageCount > 1
      ? `Generate ${requestedImageCount}`
      : "Generate";
  const simpleBatchCount = Math.min(4, Math.max(2, imageNumberMax >= 4 ? 4 : imageNumberMax));
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
        // Allow Ctrl/Cmd+Enter in the prompt; ignore when typing elsewhere (settings, search, etc.).
        if (isTypingTarget(e.target) && !(e.target instanceof HTMLTextAreaElement)) {
          return;
        }
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
      : simpleExperience
        ? easyRouteSummary(
            settings,
            studioMode,
            referenceModelFamily,
            activeModelLabel,
          )
        : studioMode === "generate"
          ? activeModelLabel
          : `Selected: ${activeModelLabel}`;
  const modes = studioModesForExperience(experience);
  const promptLabel = isAgentMode
    ? "Instruction"
    : studioMode === "upscale"
      ? "Enhancement prompt"
      : "Prompt";

  const isArabic = useMemo(
    () => /[\u0600-\u06FF]/.test(settings.prompt ?? ""),
    [settings.prompt]
  );

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

  const promptPlaceholder = useMemo(() => {
    if (isAgentMode) {
      return "Tell the agent what you want. Example: edit this poster, preserve Arabic text, make it cinematic";
    }
    const isQwenEdit = referenceModelFamily === "qwen_image_edit";
    const hasRefs = (settings.reference_images ?? []).some((path) => path.trim());
    if (isQwenEdit || hasRefs) {
      return "Describe the edit… Use 'image 1', 'image 2' to refer to your attached reference images.";
    }
    return "Describe the shot… Type @ to pick a model or style";
  }, [isAgentMode, referenceModelFamily, settings.reference_images]);

  return (
    <div
      className={`df-command-deck relative shrink-0 border-t border-dfui-border/70 bg-gradient-to-b from-dfui-panel/95 to-dfui-bg/95 px-3 py-2.5 shadow-[0_-12px_36px_rgba(0,0,0,0.28)] backdrop-blur-glass transition-colors ${
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
        if (!path) return;
        if (event.shiftKey && onImportImageMetadata) {
          void onImportImageMetadata(path);
          return;
        }
        onAttachReferenceImage(path);
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
      <motion.div className="df-command-route-row mb-2 flex min-w-0 items-center gap-2">
        <div className="flex min-w-0 shrink-0 items-center gap-1 overflow-x-auto rounded-xl border border-dfui-border/55 bg-dfui-bg/45 p-1" role="group" aria-label="Creation mode">
          {modes.map((mode) => (
            <button
              key={mode.id}
              type="button"
              onClick={() => onStudioModeChange(mode.id)}
              disabled={generating}
              aria-pressed={studioMode === mode.id}
              className={`min-h-8 shrink-0 rounded-lg border px-3 text-[10px] font-semibold transition-all ${
                studioMode === mode.id
                  ? "border-dfui-accent/45 bg-dfui-accent/15 text-dfui-accent shadow-[0_0_16px_rgba(247,148,30,0.08)]"
                  : "border-transparent text-dfui-muted hover:border-dfui-border/60 hover:bg-dfui-surface hover:text-dfui-fg"
              } disabled:opacity-60`}
            >
              {mode.label}
            </button>
          ))}
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <button type="button" onClick={() => setPromptExpanded((value) => !value)} aria-pressed={promptExpanded} className="rounded-lg border border-dfui-border/45 p-2 text-dfui-muted hover:border-dfui-accent/40 hover:text-dfui-fg" title={promptExpanded ? "Collapse prompt editor" : "Expand prompt editor"} aria-label={promptExpanded ? "Collapse prompt editor" : "Expand prompt editor"}>
            {promptExpanded ? <Minimize2 size={13} /> : <Maximize2 size={13} />}
          </button>
          {onToggleFocusMode ? <button type="button" onClick={onToggleFocusMode} aria-pressed={focusMode} className={`rounded-lg border p-2 ${focusMode ? "border-dfui-accent/50 bg-dfui-accent/10 text-dfui-accent" : "border-dfui-border/45 text-dfui-muted hover:border-dfui-accent/40 hover:text-dfui-fg"}`} title={focusMode ? "Show History and Inspector" : "Focus on canvas and command area"} aria-label={focusMode ? "Exit focus mode" : "Enter focus mode"}>
            {focusMode ? <Minimize2 size={13} /> : <Focus size={13} />}
          </button> : null}
        </div>
        {!simpleExperience ? (
        <div className="flex min-h-8 min-w-0 flex-1 items-center gap-2 rounded-xl border border-dfui-border/45 bg-dfui-bg/30 px-2.5">
          <p className="shrink-0 text-[9px] uppercase tracking-wide text-dfui-muted">
            {studioMode === "generate" ? "Model" : "Route"}
          </p>
          <p className="truncate font-mono text-[10px] font-medium text-df-blue" title={activeRouteLabel}>
            {activeRouteLabel}
          </p>
        </div>
        ) : (
        <div className="hidden min-h-8 min-w-0 flex-1 items-center px-2 md:flex">
          <p
            className="truncate text-[10px] font-medium text-df-blue/90"
            title={activeRouteLabel}
          >
            {activeRouteLabel}
          </p>
        </div>
        )}
        <div className="hidden shrink-0 items-center justify-end text-[10px] text-dfui-muted 2xl:flex">
          {agentHint ??
            (promptDragOver
              ? onImportImageMetadata
                ? "Drop attach · Shift+drop import settings"
                : "Drop image to attach"
              : "@mentions · drag images in")}
        </div>
      </motion.div>
      {simpleExperience && studioMode === "generate" && !isAgentMode && (
        <div className="mb-1.5 flex flex-wrap items-center gap-1">
          {(["Speed", "Quality"] as const).map((perf) => (
            <button
              key={perf}
              type="button"
              disabled={generating}
              onClick={() => onChange({ performance: perf })}
              className={`rounded-md border px-2 py-0.5 text-[10px] transition ${
                (settings.performance ?? "Speed") === perf
                  ? "border-df-blue/50 bg-df-blue/10 text-df-blue"
                  : "border-dfui-border/45 text-dfui-muted hover:border-df-blue/30 hover:text-dfui-fg"
              }`}
            >
              {perf}
            </button>
          ))}
          <span className="mx-0.5 text-dfui-border">|</span>
          {SIMPLE_ASPECT_PRESETS.map((ratio) => (
            <button
              key={ratio}
              type="button"
              disabled={generating}
              onClick={() => onChange({ aspect_ratio: ratio })}
              className={`rounded-md border px-2 py-0.5 font-mono text-[10px] transition ${
                (settings.aspect_ratio ?? "").replace("×", "x") === ratio
                  ? "border-df-blue/50 bg-df-blue/10 text-df-blue"
                  : "border-dfui-border/45 text-dfui-muted hover:border-df-blue/30 hover:text-dfui-fg"
              }`}
            >
              {ratio.replace("x", "×")}
            </button>
          ))}
        </div>
      )}
      <div className="df-command-main-grid">
        <div className="df-reference-panel min-w-0 self-stretch">
          <ReferenceImageControl
            settings={settings}
            modelFamily={referenceModelFamily}
            studioMode={studioMode}
            simpleExperience={simpleExperience}
            onAttach={onAttachReferenceImage}
            onAttachExtra={onAttachExtraReferenceImage}
            onRemoveExtra={onRemoveExtraReferenceImage}
            onClear={onClearReferenceImage}
            onOpenInpaintMask={onOpenInpaintMask}
            onEditStrengthChange={(edit_strength) => onChange({ edit_strength })}
            onPatchSettings={(patch) =>
              onChange(
                sanitizeSettingsForStudioMode(studioMode, {
                  ...settings,
                  ...patch,
                }),
              )
            }
            disabled={generating}
            compact
          />
        </div>
        <div className="df-prompt-panel flex min-w-0 flex-col gap-1.5">
          <div className="flex min-h-4 items-center justify-between gap-2 px-0.5">
            <label htmlFor="df-generation-prompt" className="text-[10px] font-semibold uppercase tracking-[0.12em] text-dfui-secondary">
              {promptLabel}
            </label>
            <div className="flex items-center gap-2 text-[9px] text-dfui-muted">
              <span>{(settings.prompt ?? "").length.toLocaleString()} characters</span>
              <kbd className="hidden rounded border border-dfui-border/60 bg-dfui-bg/50 px-1.5 py-0.5 font-mono text-[8px] text-dfui-tertiary lg:inline-flex">Ctrl ↵</kbd>
            </div>
          </div>
          {studioMode === "upscale" ? (
            <textarea
              id="df-generation-prompt"
              aria-label={promptLabel}
              value={settings.prompt ?? ""}
              onChange={(e) => onPromptChange(e.target.value)}
              onFocus={() => onInpaintCanvasFocusChange?.(false)}
              rows={promptExpanded ? 7 : 2}
              dir={isArabic ? "rtl" : "ltr"}
              placeholder="Optional enhancement — leave empty for auto restoration prompt"
              className={`df-textarea-glowing flex-1 py-1.5 text-xs leading-snug ${promptExpanded ? "min-h-[150px]" : "min-h-[48px]"}`}
              data-df-prompt-input
            />
          ) : (
          <div className="flex min-w-0 items-stretch gap-1.5">
            <textarea
              id="df-generation-prompt"
              aria-label={promptLabel}
              value={settings.prompt ?? ""}
              onChange={(e) => onPromptChange(e.target.value)}
              onFocus={() => onInpaintCanvasFocusChange?.(false)}
              rows={promptExpanded ? 7 : 2}
              dir={isArabic ? "rtl" : "ltr"}
              placeholder={promptPlaceholder}
              className={`df-textarea-glowing flex-1 py-1.5 text-xs leading-snug ${promptExpanded ? "min-h-[150px]" : "min-h-[48px]"}`}
              data-df-prompt-input
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
                className="inline-flex h-[48px] shrink-0 items-center justify-center gap-1.5 rounded-lg border border-dfui-border/60 bg-dfui-bg/40 px-2 text-dfui-muted transition-colors hover:border-df-blue/45 hover:bg-df-blue/5 hover:text-df-blue disabled:cursor-not-allowed disabled:opacity-45"
              >
                <Wand2 size={15} className={enhancePromptBusy ? "animate-pulse" : ""} />
                <span className="df-enhance-label text-[10px] font-semibold">{enhancePromptBusy ? "Enhancing" : "Enhance"}</span>
              </motion.button>
            ) : null}
          </div>
          )}
          {isIdeogramModel && !isAgentMode && studioMode !== "upscale" ? (
            <IdeogramJsonPreview prompt={settings.prompt ?? ""} enabled={isIdeogramModel} />
          ) : null}
          <div className="df-prompt-action-row flex min-h-8 items-center justify-between gap-2">
            <p className={`min-w-0 truncate text-[10px] ${!canRunPrimary && generateBlockReason ? "text-amber-200" : "text-dfui-muted"}`} role={!canRunPrimary && generateBlockReason ? "status" : undefined}>
              {!canRunPrimary && generateBlockReason
                ? generateBlockReason
                : agentHint ??
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
              {canDescribeImage ? (
                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  type="button"
                  onClick={() => onDescribeImage?.()}
                  disabled={generating || describeImageBusy}
                  className="inline-flex min-h-8 items-center gap-1.5 rounded-lg border border-dfui-border/50 px-2.5 text-xs text-dfui-fg transition-colors hover:border-df-blue/40 disabled:opacity-50"
                  title="Describe image → fill prompt (Fooocus-style)"
                >
                  <Brain size={13} className="text-df-blue" />
                  {describeImageBusy ? "Describing…" : "Describe"}
                </motion.button>
              ) : null}
              {!simpleExperience ? (
              <PromptToolsMenu
                settings={settings}
                onChange={onChange}
                disabled={generating || studioMode === "edit" || studioMode === "inpaint"}
                describeImagePath={effectiveDescribePath}
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
                    className="inline-flex min-h-9 min-w-[108px] items-center justify-center gap-1.5 rounded-lg bg-gradient-to-r from-df-orange to-df-orange-deep px-4 text-xs font-bold text-white shadow-[0_8px_22px_rgba(247,148,30,0.18)] transition-all disabled:cursor-not-allowed disabled:shadow-none disabled:opacity-50"
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
