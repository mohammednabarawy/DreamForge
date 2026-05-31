import { Bot, Check, Trash2, User } from "lucide-react";
import type { AgentTranscriptMessage } from "../lib/studioBridge";

type Props = {
  messages: AgentTranscriptMessage[];
  runtimeLabel?: string;
  onClear?: () => void;
};

function timeLabel(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function AgentTranscriptPanel({ messages, runtimeLabel, onClear }: Props) {
  return (
    <div className="absolute bottom-4 left-4 z-20 flex max-h-[42%] w-[min(24rem,92vw)] flex-col overflow-hidden rounded-lg border border-dfui-border/70 bg-dfui-bg/90 shadow-lg backdrop-blur-sm">
      <div className="flex items-center justify-between gap-2 border-b border-dfui-border/50 px-3 py-2">
        <div className="min-w-0">
          <p className="font-mono text-[9px] uppercase tracking-wider text-dfui-tertiary">
            Agent Studio
          </p>
          <p className="truncate text-[11px] text-dfui-secondary">
            {runtimeLabel ?? "Local reasoning runtime"}
          </p>
        </div>
        {onClear && messages.length > 0 && (
          <button
            type="button"
            onClick={onClear}
            className="rounded p-1 text-dfui-tertiary hover:bg-dfui-surface hover:text-dfui-fg"
            title="Clear transcript"
          >
            <Trash2 size={13} />
          </button>
        )}
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-3 py-2">
        {messages.length === 0 ? (
          <p className="text-[11px] leading-relaxed text-dfui-tertiary">
            Ask the agent what you want. Generate applies the route to Settings and runs it.
          </p>
        ) : (
          <div className="space-y-2">
            {messages.slice(-8).map((message) => {
              const isUser = message.role === "user";
              return (
                <div
                  key={message.id}
                  className={`rounded-md border px-2 py-1.5 ${
                    isUser
                      ? "border-dfui-accent/25 bg-dfui-accent/5"
                      : message.status === "error"
                        ? "border-red-400/30 bg-red-500/10"
                        : "border-dfui-border/60 bg-dfui-surface/40"
                  }`}
                >
                  <div className="mb-1 flex items-center gap-1.5 text-[9px] text-dfui-tertiary">
                    {isUser ? <User size={10} /> : <Bot size={10} />}
                    <span className="font-mono uppercase">
                      {isUser ? "You" : "Agent"}
                    </span>
                    {message.mode && <span>· {message.mode}</span>}
                    {message.status === "applied" && (
                      <span className="inline-flex items-center gap-0.5 text-dfui-accent">
                        <Check size={10} />
                        applied
                      </span>
                    )}
                    <span className="ml-auto">{timeLabel(message.created_at)}</span>
                  </div>
                  <p className="whitespace-pre-wrap text-[11px] leading-snug text-dfui-secondary">
                    {message.text}
                  </p>
                  {(message.actions?.length ?? 0) > 0 && (
                    <p className="mt-1 truncate font-mono text-[9px] text-dfui-tertiary">
                      Actions: {message.actions!.slice(0, 4).join(", ")}
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
