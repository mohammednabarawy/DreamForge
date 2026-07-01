import { AlertTriangle, X } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import type { FriendlyError } from "../lib/errors";

type Props = {
  warnings: FriendlyError[];
  onDismissWarning: (code: string) => void;
  onDismissAllWarnings: () => void;
};

export function ReliabilityBanner({
  warnings,
  onDismissWarning,
  onDismissAllWarnings,
}: Props) {
  const hasWarnings = warnings.length > 0;
  if (!hasWarnings) return null;

  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-[55] flex w-[min(22rem,calc(100vw-2rem))] flex-col gap-2">
      <AnimatePresence mode="popLayout">
        {warnings.map((warning) => (
          <motion.div
            key={warning.code}
            initial={{ opacity: 0, y: 12, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8, scale: 0.98 }}
            transition={{ duration: 0.18 }}
            className="pointer-events-auto rounded-xl border border-amber-500/35 bg-dfui-panel/95 px-3 py-2.5 shadow-2xl backdrop-blur-md"
          >
            <div className="flex items-start gap-2">
              <AlertTriangle size={14} className="mt-0.5 shrink-0 text-amber-400" />
              <div className="min-w-0 flex-1">
                <p className="text-xs font-medium text-amber-100">{warning.title}</p>
                <p className="mt-0.5 text-[11px] leading-snug text-dfui-secondary">
                  {warning.message}
                </p>
              </div>
              <button
                type="button"
                onClick={() => onDismissWarning(warning.code)}
                className="shrink-0 rounded p-0.5 text-dfui-tertiary transition hover:bg-dfui-surface hover:text-dfui-fg"
                aria-label="Dismiss warning"
              >
                <X size={14} />
              </button>
            </div>
          </motion.div>
        ))}
      </AnimatePresence>
      {warnings.length > 1 && (
        <button
          type="button"
          onClick={onDismissAllWarnings}
          className="pointer-events-auto self-end rounded-md border border-dfui-border/50 bg-dfui-panel/90 px-2 py-1 text-[10px] text-dfui-muted transition hover:text-dfui-fg"
        >
          Dismiss all warnings
        </button>
      )}
    </div>
  );
}
