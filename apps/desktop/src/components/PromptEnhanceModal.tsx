import { Sparkles, Loader2, Check, X, RotateCcw, AlertCircle } from "lucide-react";
import { useState, useEffect } from "react";

type Props = {
  open: boolean;
  onClose: () => void;
  originalPrompt: string;
  onApply: (prompt: string, negativePrompt?: string) => void;
  onEnhance: () => Promise<{ prompt: string; negative_prompt?: string; error?: string }>;
};

type Step = {
  id: string;
  label: string;
  status: "pending" | "running" | "done" | "failed";
};

export function PromptEnhanceModal({
  open,
  onClose,
  originalPrompt,
  onApply,
  onEnhance,
}: Props) {
  if (!open) return null;

  const [status, setStatus] = useState<"idle" | "enhancing" | "success" | "error">("idle");
  const [steps, setSteps] = useState<Step[]>([
    { id: "connect", label: "Connecting to local LLM server", status: "pending" },
    { id: "think", label: "AI brain generating structured expansion", status: "pending" },
    { id: "validate", label: "Running prompt guardrails and normalization", status: "pending" },
  ]);
  const [enhancedPrompt, setEnhancedPrompt] = useState("");
  const [negativePrompt, setNegativePrompt] = useState("");
  const [errorMsg, setErrorMsg] = useState("");

  const runEnhancement = async () => {
    setStatus("enhancing");
    setErrorMsg("");
    setEnhancedPrompt("");
    setNegativePrompt("");
    
    // Reset steps
    const currentSteps: Step[] = [
      { id: "connect", label: "Connecting to local LLM server", status: "running" },
      { id: "think", label: "AI brain generating structured expansion", status: "pending" },
      { id: "validate", label: "Running prompt guardrails and normalization", status: "pending" },
    ];
    setSteps([...currentSteps]);

    try {
      // Step 1: Connect & initiate
      await new Promise((r) => setTimeout(r, 600));
      currentSteps[0].status = "done";
      currentSteps[1].status = "running";
      setSteps([...currentSteps]);

      // Step 2: Query AI Brain
      const result = await onEnhance();
      
      if (result.error) {
        throw new Error(result.error);
      }

      currentSteps[1].status = "done";
      currentSteps[2].status = "running";
      setSteps([...currentSteps]);

      // Step 3: Validate & finalize
      await new Promise((r) => setTimeout(r, 400));
      currentSteps[2].status = "done";
      setSteps([...currentSteps]);

      setEnhancedPrompt(result.prompt);
      setNegativePrompt(result.negative_prompt ?? "");
      setStatus("success");
    } catch (err: any) {
      // Mark active step as failed
      const activeIdx = currentSteps.findIndex((s) => s.status === "running" || s.status === "pending");
      if (activeIdx !== -1) {
        currentSteps[activeIdx].status = "failed";
      } else {
        currentSteps[currentSteps.length - 1].status = "failed";
      }
      setSteps([...currentSteps]);
      const rawMsg = err?.message || (typeof err === "string" ? err : null) || err?.toString() || "";
      setErrorMsg(rawMsg || "Failed to enhance prompt. Make sure your local LLM server (LM Studio or Ollama) is running and accessible.");
      setStatus("error");
    }
  };

  useEffect(() => {
    if (open) {
      void runEnhancement();
    }
  }, [open]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="enhance-modal-title"
    >
      <div className="flex max-h-[85vh] w-full max-w-xl flex-col rounded-xl border border-purple-500/20 bg-dfui-panel shadow-2xl overflow-hidden animate-fadeIn">
        {/* Header */}
        <div className="flex shrink-0 items-center justify-between border-b border-dfui-border/50 px-4 py-3 bg-purple-950/20">
          <div className="flex items-center gap-2">
            <Sparkles size={16} className="text-purple-400 animate-pulse" />
            <h2 id="enhance-modal-title" className="text-sm font-semibold text-dfui-fg">
              AI Prompt Expansion
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md p-1 text-dfui-tertiary transition hover:bg-dfui-surface hover:text-dfui-fg"
            aria-label="Close modal"
          >
            <X size={18} />
          </button>
        </div>

        {/* Content */}
        <div className="min-h-0 flex-1 overflow-y-auto p-5 space-y-4">
          {/* Progress Steps (while loading or error) */}
          {(status === "enhancing" || status === "error") && (
            <div className="rounded-lg border border-dfui-border/40 bg-dfui-surface/30 p-4 space-y-3">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-dfui-muted">
                Enhancement Progress
              </p>
              <div className="space-y-2.5">
                {steps.map((step) => (
                  <div key={step.id} className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                      {step.status === "running" && (
                        <Loader2 size={12} className="animate-spin text-purple-400" />
                      )}
                      {step.status === "done" && (
                        <Check size={12} className="text-emerald-400 font-bold" />
                      )}
                      {step.status === "failed" && (
                        <X size={12} className="text-rose-400 font-bold" />
                      )}
                      {step.status === "pending" && (
                        <div className="h-1.5 w-1.5 rounded-full bg-dfui-muted/50 ml-1" />
                      )}
                      <span
                        className={`text-xs ${
                          step.status === "running"
                            ? "text-dfui-fg font-medium"
                            : step.status === "done"
                            ? "text-dfui-secondary"
                            : "text-dfui-muted"
                        }`}
                      >
                        {step.label}
                      </span>
                    </div>
                    {step.status === "running" && (
                      <span className="text-[9px] text-purple-400/80 animate-pulse font-medium bg-purple-500/10 px-1.5 py-0.5 rounded">
                        Active
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Error Message */}
          {status === "error" && (
            <div className="flex items-start gap-2.5 rounded-lg border border-rose-500/30 bg-rose-500/5 p-4 text-xs text-rose-300">
              <AlertCircle size={14} className="shrink-0 mt-0.5 text-rose-400" />
              <div className="space-y-1">
                <p className="font-semibold text-rose-200">Expansion Interrupted</p>
                <p className="leading-relaxed text-rose-300/90">{errorMsg}</p>
              </div>
            </div>
          )}

          {/* Original Prompt Comparison */}
          <div className="space-y-1">
            <span className="text-[10px] text-dfui-tertiary font-semibold uppercase tracking-wider">Original prompt</span>
            <div className="rounded-md border border-dfui-border/40 bg-dfui-bg/30 px-3 py-2 text-xs text-dfui-secondary italic">
              {originalPrompt || "(Empty Prompt)"}
            </div>
          </div>

          {/* Success Results (Editable textareas) */}
          {status === "success" && (
            <div className="space-y-4">
              <div className="space-y-1">
                <label className="text-[10px] text-purple-300 font-semibold uppercase tracking-wider flex items-center gap-1">
                  <Sparkles size={10} className="text-purple-400" />
                  Enhanced prompt
                </label>
                <textarea
                  value={enhancedPrompt}
                  onChange={(e) => setEnhancedPrompt(e.target.value)}
                  rows={6}
                  className="w-full rounded-md border border-purple-500/30 bg-purple-950/5 px-3 py-2 text-xs text-dfui-fg outline-none focus:border-purple-500/60 focus:ring-1 focus:ring-purple-500/35 transition-all font-mono leading-relaxed"
                />
              </div>

              {negativePrompt && (
                <div className="space-y-1">
                  <label className="text-[10px] text-dfui-tertiary font-semibold uppercase tracking-wider">
                    Negative prompt
                  </label>
                  <textarea
                    value={negativePrompt}
                    onChange={(e) => setNegativePrompt(e.target.value)}
                    rows={2}
                    className="w-full rounded-md border border-dfui-border/40 bg-dfui-bg/25 px-3 py-2 text-xs text-dfui-fg outline-none focus:border-dfui-border/70 focus:ring-1 focus:ring-dfui-border/30 transition-all font-mono"
                  />
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex shrink-0 items-center justify-between border-t border-dfui-border/50 px-4 py-3 bg-dfui-surface/30">
          <div>
            {status === "error" && (
              <button
                type="button"
                onClick={() => void runEnhancement()}
                className="inline-flex items-center gap-1 rounded-md border border-purple-500/40 bg-purple-500/10 px-3 py-1.5 text-xs font-semibold text-purple-300 hover:bg-purple-500/20 transition-all"
              >
                <RotateCcw size={12} />
                Retry
              </button>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onClose}
              className="df-btn df-btn-secondary px-4 py-1.5 text-xs"
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={status !== "success"}
              onClick={() => onApply(enhancedPrompt, negativePrompt)}
              className="inline-flex items-center gap-1.5 rounded-md bg-purple-600 hover:bg-purple-500 px-4 py-1.5 text-xs font-semibold text-white shadow-lg shadow-purple-500/10 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <Check size={12} />
              Use expansion
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
