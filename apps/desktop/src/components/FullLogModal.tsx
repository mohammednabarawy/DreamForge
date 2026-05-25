import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";
import { readFullWorkerLog } from "../lib/tauri-api";

type Props = {
  open: boolean;
  onClose: () => void;
};

export function FullLogModal({ open, onClose }: Props) {
  const [log, setLog] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const autoScrollRef = useRef(true);

  useEffect(() => {
    if (!open) return;
    setLog("");
    const poll = async () => {
      try {
        const { tail } = await readFullWorkerLog();
        setLog(tail);
      } catch {
        /* not ready */
      }
    };
    void poll();
    const id = setInterval(poll, 1000);
    return () => clearInterval(id);
  }, [open]);

  useEffect(() => {
    if (autoScrollRef.current) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [log]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="flex h-[80vh] w-[90vw] max-w-5xl flex-col rounded-xl border border-dfui-border bg-dfui-panel shadow-2xl">
        <div className="flex items-center justify-between border-b border-dfui-border/50 px-4 py-3">
          <h2 className="text-sm font-semibold text-dfui-fg">Backend log</h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md p-1 text-dfui-tertiary transition hover:bg-dfui-surface hover:text-dfui-fg"
          >
            <X size={18} />
          </button>
        </div>
        <div className="relative flex-1 overflow-hidden">
          <pre
            className="h-full overflow-auto whitespace-pre-wrap break-all bg-dfui-bg p-4 font-mono text-[11px] leading-relaxed text-dfui-secondary"
            onScroll={(e) => {
              const el = e.currentTarget;
              const atBottom =
                el.scrollHeight - el.scrollTop - el.clientHeight < 60;
              autoScrollRef.current = atBottom;
            }}
          >
            {log || (
              <span className="text-dfui-muted">Waiting for log output…</span>
            )}
            <div ref={bottomRef} />
          </pre>
        </div>
      </div>
    </div>
  );
}
