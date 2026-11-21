import { AlertTriangle, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import {
  resolveConfirmDialog,
  subscribeConfirmDialog,
  type ConfirmDialogRequest,
} from "../lib/confirmDialog";

type ActiveConfirm = ConfirmDialogRequest & { id: number };

export function ConfirmDialogModal() {
  const [active, setActive] = useState<ActiveConfirm | null>(null);
  const confirmBtnRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    return subscribeConfirmDialog((pending) => {
      setActive(pending ? { ...pending } : null);
    });
  }, []);

  useEffect(() => {
    if (!active) return;
    const focusTimer = window.setTimeout(() => confirmBtnRef.current?.focus(), 0);
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
        resolveConfirmDialog(active.id, false);
      }
    };
    window.addEventListener("keydown", onKeyDown, true);
    return () => {
      window.clearTimeout(focusTimer);
      window.removeEventListener("keydown", onKeyDown, true);
    };
  }, [active]);

  if (!active) return null;

  const destructive = Boolean(active.destructive);

  return (
    <div
      className="fixed inset-0 z-[300] flex items-center justify-center bg-black/65 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="df-confirm-title"
      aria-describedby="df-confirm-message"
      onClick={() => resolveConfirmDialog(active.id, false)}
    >
      <div
        className="w-full max-w-md rounded-2xl border border-dfui-border/80 bg-dfui-panel/95 p-5 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start gap-3">
          <div
            className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl border ${
              destructive
                ? "border-red-400/35 bg-red-500/15 text-red-300"
                : "border-dfui-accent/35 bg-dfui-accent/15 text-dfui-accent"
            }`}
          >
            <AlertTriangle size={16} />
          </div>
          <div className="min-w-0 flex-1">
            <h2
              id="df-confirm-title"
              className="text-sm font-semibold text-dfui-fg"
            >
              {active.title}
            </h2>
            <p
              id="df-confirm-message"
              className="mt-1.5 text-xs leading-relaxed text-dfui-secondary"
            >
              {active.message}
            </p>
            {active.detail && (
              <p className="mt-1.5 break-all rounded-md bg-dfui-bg/60 px-2 py-1 font-mono text-[10px] text-dfui-tertiary">
                {active.detail}
              </p>
            )}
          </div>
          <button
            type="button"
            aria-label="Close dialog"
            onClick={() => resolveConfirmDialog(active.id, false)}
            className="shrink-0 rounded-md p-1 text-dfui-tertiary hover:bg-dfui-bg/60 hover:text-dfui-fg"
          >
            <X size={14} />
          </button>
        </div>

        <div className="mt-5 flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={() => resolveConfirmDialog(active.id, false)}
            className="rounded-lg border border-dfui-border/70 bg-dfui-bg/50 px-3 py-1.5 text-xs font-medium text-dfui-secondary hover:border-dfui-border hover:text-dfui-fg"
          >
            {active.cancelLabel ?? "Cancel"}
          </button>
          <button
            ref={confirmBtnRef}
            type="button"
            onClick={() => resolveConfirmDialog(active.id, true)}
            className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition focus:outline-none focus:ring-2 ${
              destructive
                ? "border-red-400/50 bg-red-500/20 text-red-200 hover:bg-red-500/30 focus:ring-red-400/40"
                : "border-dfui-accent/50 bg-dfui-accent/20 text-dfui-fg hover:bg-dfui-accent/30 focus:ring-dfui-accent/40"
            }`}
          >
            {active.confirmLabel ?? "Confirm"}
          </button>
        </div>
      </div>
    </div>
  );
}
