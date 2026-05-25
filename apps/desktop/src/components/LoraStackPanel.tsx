import { useEffect, useState } from "react";
import {
  formatLoraToken,
  loraWeightFromToken,
  parseLoraList,
  removeLora,
  upsertLora,
} from "../lib/loraStack";
import { getLoraInfo } from "../lib/studioBridge";

type Props = {
  lora: string[];
  loraMin?: number;
  loraMax?: number;
  onChange: (lora: string[]) => void;
};

export function LoraStackPanel({ lora, loraMin = 0, loraMax = 2, onChange }: Props) {
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

  return (
    <div className="space-y-2 rounded-lg border border-dfui-border/50 bg-dfui-bg/30 p-2">
      <p className="text-[10px] font-medium uppercase tracking-wide text-dfui-muted">
        Active LoRA stack
      </p>
      <ul className="space-y-2">
        {entries.map((entry) => (
          <li key={entry.name} className="space-y-1">
            <div className="flex items-center justify-between gap-2">
              <span className="truncate font-mono text-[10px] text-dfui-fg">
                {entry.name.split(/[/\\]/).pop()}
              </span>
              <button
                type="button"
                className="text-[10px] text-dfui-tertiary hover:text-red-300"
                onClick={() => onChange(removeLora(lora, entry.name))}
              >
                Remove
              </button>
            </div>
            <div className="flex items-center gap-2">
              <input
                type="range"
                min={loraMin}
                max={loraMax}
                step={0.05}
                value={loraWeightFromToken(lora, entry.name, entry.weight)}
                onChange={(e) =>
                  onChange(
                    upsertLora(lora, entry.name, Number(e.target.value)),
                  )
                }
                className="flex-1 accent-dfui-accent"
              />
              <span className="w-8 text-right font-mono text-[10px] text-dfui-data">
                {entry.weight.toFixed(2)}
              </span>
            </div>
            {keywords[entry.name] && (
              <p className="text-[9px] leading-snug text-dfui-tertiary line-clamp-2">
                {keywords[entry.name]}
              </p>
            )}
          </li>
        ))}
      </ul>
      <p className="text-[9px] text-dfui-tertiary">
        Tokens: {entries.map((e) => formatLoraToken(e.name, e.weight)).join(" ")}
      </p>
    </div>
  );
}
