import { useState } from "react";
import { ChevronDown, ChevronRight, Eye, Sparkles, Wand2 } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

export type TraceItem = {
  stage: string;
  action: "appended" | "prepended" | "modified" | "none" | string;
  added_text?: string;
  reason: string;
};

export type PromptTracePanelProps = {
  rawPrompt?: string;
  finalPrompt?: string;
  trace?: TraceItem[];
};

export function PromptTracePanel({
  rawPrompt,
  finalPrompt,
  trace,
}: PromptTracePanelProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [showRaw, setShowRaw] = useState(false);

  if (!trace || trace.length === 0) return null;

  const modifiedItems = trace.filter((t) => t.action !== "none");
  const hasModifications = modifiedItems.length > 0;

  return (
    <div className="rounded-lg border border-dfui-border/40 bg-dfui-panel/60 backdrop-blur-sm text-xs">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="flex w-full items-center justify-between px-3 py-2 text-left hover:bg-dfui-accent/5 transition-colors rounded-lg"
      >
        <div className="flex items-center gap-2">
          <Wand2 size={13} className="text-dfui-accent" />
          <span className="font-medium text-dfui-fg">
            Prompt Pipeline Transparency
          </span>
          <span
            className={`rounded px-1.5 py-0.5 text-[9px] font-mono ${
              hasModifications
                ? "bg-amber-500/15 text-amber-300 border border-amber-500/30"
                : "bg-emerald-500/15 text-emerald-300 border border-emerald-500/30"
            }`}
          >
            {hasModifications
              ? `${modifiedItems.length} auto-adjustment${modifiedItems.length > 1 ? "s" : ""}`
              : "Direct Pass (Unmodified)"}
          </span>
        </div>
        <div className="flex items-center gap-1 text-dfui-muted">
          {isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </div>
      </button>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden border-t border-dfui-border/30 px-3 py-2.5 space-y-2.5"
          >
            <div className="flex items-center justify-between text-[10px]">
              <span className="text-dfui-muted">Pipeline Stage Breakdown</span>
              <button
                type="button"
                onClick={() => setShowRaw(!showRaw)}
                className="flex items-center gap-1 text-dfui-accent hover:underline"
              >
                <Eye size={11} />
                {showRaw ? "Show Stages" : "Show Full Compiled Prompt"}
              </button>
            </div>

            {showRaw ? (
              <div className="space-y-1.5">
                {rawPrompt && (
                  <div>
                    <p className="text-[10px] text-dfui-muted uppercase tracking-wider">
                      Original Input:
                    </p>
                    <p className="rounded bg-dfui-bg/80 p-2 font-mono text-[11px] text-dfui-data border border-dfui-border/40">
                      {rawPrompt}
                    </p>
                  </div>
                )}
                {finalPrompt && (
                  <div>
                    <p className="text-[10px] text-dfui-muted uppercase tracking-wider">
                      Sent to Model:
                    </p>
                    <p className="rounded bg-dfui-bg/80 p-2 font-mono text-[11px] text-dfui-fg border border-dfui-border/40">
                      {finalPrompt}
                    </p>
                  </div>
                )}
              </div>
            ) : (
              <div className="space-y-1.5">
                {trace.map((item, idx) => (
                  <div
                    key={idx}
                    className="flex items-start gap-2 rounded bg-dfui-bg/40 p-2 border border-dfui-border/20 text-[11px]"
                  >
                    <Sparkles
                      size={12}
                      className={`mt-0.5 shrink-0 ${
                        item.action !== "none"
                          ? "text-amber-400"
                          : "text-dfui-muted"
                      }`}
                    />
                    <div className="min-w-0 flex-1 space-y-0.5">
                      <div className="flex items-center gap-1.5">
                        <span className="font-mono text-[10px] font-semibold text-dfui-accent uppercase">
                          {item.stage.replace(/_/g, " ")}
                        </span>
                        <span className="text-[9px] text-dfui-muted">
                          ({item.action})
                        </span>
                      </div>
                      <p className="text-dfui-secondary">{item.reason}</p>
                      {item.added_text && (
                        <p className="font-mono text-[10px] text-amber-200/90 bg-amber-500/10 rounded px-1.5 py-0.5 inline-block">
                          + {item.added_text}
                        </p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
