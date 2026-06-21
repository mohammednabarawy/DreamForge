import { useEffect, useState } from "react";
import {
  clampLoraWeight,
  formatLoraToken,
  loraWeightFromToken,
  moveLoraInList,
  parseLoraList,
  removeLora,
  upsertLora,
} from "../lib/loraStack";
import { getLoraInfo } from "../lib/studioBridge";

type Props = {
  lora: string[];
  loraMin?: number;
  loraMax?: number;
  maxStack?: number;
  loraKeywords?: string;
  onLoraKeywordsChange?: (value: string) => void;
  onSyncKeywordsFromStack?: () => void | Promise<void>;
  onChange: (lora: string[]) => void;
};

export function LoraStackPanel({
  lora,
  loraMin = 0,
  loraMax = 2,
  maxStack = 5,
  loraKeywords = "",
  onLoraKeywordsChange,
  onSyncKeywordsFromStack,
  onChange,
}: Props) {
  const entries = parseLoraList(lora);
  const [keywords, setKeywords] = useState<Record<string, string>>({});

  useEffect(() => {
    let cancelled = false;
    for (const entry of entries) {
      void getLoraInfo(entry.name)
        .then((info) => {
          if (cancelled || !info.keywords) return;
          setKeywords((prev) => ({ ...prev, [entry.name]: info.keywords }));
        })
        .catch(() => {});
    }
    return () => {
      cancelled = true;
    };
  }, [entries.map((e) => e.name).join("|")]);

  if (entries.length === 0) return null;

  const atMax = entries.length >= maxStack;

  return (
    <div className="space-y-2 rounded-lg border border-dfui-border/50 bg-dfui-bg/30 p-2">
      <div className="flex items-center justify-between gap-2">
        <p className="text-[10px] font-medium uppercase tracking-wide text-dfui-muted">
          Active LoRA stack
        </p>
        <span className="text-[9px] text-dfui-tertiary">
          {entries.length}/{maxStack}
        </span>
      </div>
      {atMax && (
        <p className="text-[9px] text-amber-400/90">
          Web UI default limit is {maxStack} LoRAs — more may increase VRAM use and
          load time.
        </p>
      )}
      <ul className="space-y-2">
        {entries.map((entry, index) => {
          const weight = loraWeightFromToken(lora, entry.name, entry.weight);
          return (
            <li key={entry.name} className="space-y-1 rounded border border-dfui-border/30 p-1.5">
              <div className="flex items-center justify-between gap-2">
                <span className="truncate font-mono text-[10px] text-dfui-fg">
                  {entry.name.split(/[/\\]/).pop()}
                </span>
                <div className="flex shrink-0 items-center gap-1">
                  <button
                    type="button"
                    title="Move up"
                    disabled={index === 0}
                    className="text-[10px] text-dfui-tertiary hover:text-dfui-fg disabled:opacity-30"
                    onClick={() =>
                      onChange(moveLoraInList(lora, entry.name, "up"))
                    }
                  >
                    ↑
                  </button>
                  <button
                    type="button"
                    title="Move down"
                    disabled={index === entries.length - 1}
                    className="text-[10px] text-dfui-tertiary hover:text-dfui-fg disabled:opacity-30"
                    onClick={() =>
                      onChange(moveLoraInList(lora, entry.name, "down"))
                    }
                  >
                    ↓
                  </button>
                  <button
                    type="button"
                    className="text-[10px] text-dfui-tertiary hover:text-red-300"
                    onClick={() => onChange(removeLora(lora, entry.name))}
                  >
                    Remove
                  </button>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="range"
                  min={loraMin}
                  max={loraMax}
                  step={0.05}
                  value={weight}
                  onChange={(e) =>
                    onChange(
                      upsertLora(
                        lora,
                        entry.name,
                        clampLoraWeight(
                          Number(e.target.value),
                          loraMin,
                          loraMax,
                        ),
                      ),
                    )
                  }
                  className="flex-1 accent-dfui-accent"
                />
                <input
                  type="number"
                  min={loraMin}
                  max={loraMax}
                  step={0.05}
                  value={weight}
                  onChange={(e) => {
                    const n = Number(e.target.value);
                    if (!Number.isFinite(n)) return;
                    onChange(
                      upsertLora(
                        lora,
                        entry.name,
                        clampLoraWeight(n, loraMin, loraMax),
                      ),
                    );
                  }}
                  className="w-14 rounded border border-dfui-border/50 bg-dfui-bg px-1 py-0.5 text-right font-mono text-[10px] text-dfui-data"
                />
              </div>
              {keywords[entry.name] && (
                <p className="text-[9px] leading-snug text-dfui-tertiary line-clamp-2">
                  {keywords[entry.name]}
                </p>
              )}
            </li>
          );
        })}
      </ul>
      {(onLoraKeywordsChange || onSyncKeywordsFromStack) && (
        <div className="space-y-1 border-t border-dfui-border/30 pt-2">
          <div className="flex items-center justify-between gap-2">
            <span className="text-[9px] font-medium uppercase tracking-wide text-dfui-muted">
              LoRA trigger words
            </span>
            {onSyncKeywordsFromStack && (
              <button
                type="button"
                className="text-[9px] text-dfui-accent hover:underline"
                onClick={() => void onSyncKeywordsFromStack()}
              >
                Sync from stack
              </button>
            )}
          </div>
          <textarea
            rows={2}
            value={loraKeywords}
            onChange={(e) => onLoraKeywordsChange?.(e.target.value)}
            readOnly={!onLoraKeywordsChange}
            placeholder="Merged trigger words for styles (web UI field)"
            className="df-input w-full resize-none px-2 py-1 text-[10px]"
          />
          <p className="text-[9px] text-dfui-tertiary">
            Injected into styled prompts as {"{lora_keywords}"}. Leave empty to
            auto-merge from the stack at generate time.
          </p>
        </div>
      )}
      <p className="text-[9px] text-dfui-tertiary">
        Tokens: {entries.map((e) => formatLoraToken(e.name, e.weight)).join(" ")}
      </p>
    </div>
  );
}
