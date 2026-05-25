import { ChevronDown, Dices, Sparkles, Wand2 } from "lucide-react";
import { useState } from "react";
import type { GenerationSettings } from "../lib/tauri-api";
import {
  applyStylesToPrompt,
  evolvePrompts,
  interrogateImage,
  randomOnebuttonPrompt,
} from "../lib/studioBridge";

type Props = {
  settings: GenerationSettings;
  onChange: (patch: Partial<GenerationSettings>) => void;
  disabled?: boolean;
};

export function PromptToolsMenu({ settings, onChange, disabled }: Props) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [evolveOpen, setEvolveOpen] = useState(false);
  const [variants, setVariants] = useState<string[]>([]);

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    try {
      await fn();
    } finally {
      setBusy(false);
      setOpen(false);
    }
  };

  return (
    <div className="relative">
      <button
        type="button"
        disabled={disabled || busy}
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1 rounded-md border border-dfui-border/50 px-2 py-1.5 text-[10px] text-dfui-muted hover:border-dfui-accent/40 hover:text-dfui-fg disabled:opacity-40"
      >
        <Wand2 size={12} />
        Tools
        <ChevronDown size={10} />
      </button>
      {open && (
        <div className="absolute bottom-full left-0 z-20 mb-1 min-w-[180px] rounded-lg border border-dfui-border/60 bg-dfui-panel py-1 shadow-xl">
          <button
            type="button"
            className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs hover:bg-dfui-accent/10"
            onClick={() =>
              void run(async () => {
                const p = await randomOnebuttonPrompt();
                if (p) onChange({ prompt: p });
              })
            }
          >
            <Dices size={14} />
            Random prompt (OBP)
          </button>
          <button
            type="button"
            className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs hover:bg-dfui-accent/10"
            onClick={() =>
              void run(async () => {
                const res = await applyStylesToPrompt({
                  styles: settings.styles ?? [],
                  prompt: settings.prompt ?? "",
                  negative_prompt: settings.negative_prompt ?? "",
                });
                onChange({
                  prompt: res.prompt,
                  negative_prompt: res.negative_prompt,
                  styles: [],
                });
              })
            }
          >
            <Sparkles size={14} />
            Apply styles to prompt
          </button>
          <button
            type="button"
            className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs hover:bg-dfui-accent/10"
            onClick={() => {
              setEvolveOpen(true);
              setOpen(false);
            }}
          >
            <Wand2 size={14} />
            Evolve prompt…
          </button>
          {settings.input_image && (
            <button
              type="button"
              className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs hover:bg-dfui-accent/10"
              onClick={() =>
                void run(async () => {
                  const res = await interrogateImage(
                    settings.input_image!,
                    settings.prompt,
                  );
                  if (res.prompt) onChange({ prompt: res.prompt });
                })
              }
            >
              Interrogate image
            </button>
          )}
        </div>
      )}
      {evolveOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-md rounded-xl border border-dfui-border/60 bg-dfui-panel p-3">
            <p className="text-sm font-medium text-dfui-fg">Evolve variants</p>
            <p className="mt-1 text-[10px] text-dfui-tertiary">
              Pick a variant or close to cancel.
            </p>
            <div className="mt-2 flex gap-2">
              <button
                type="button"
                className="rounded border border-dfui-border/50 px-2 py-1 text-[10px]"
                onClick={() =>
                  void evolvePrompts({
                    prompt: settings.prompt ?? "",
                    mode: "Tokens",
                    strength: 35,
                  }).then(setVariants)
                }
              >
                Tokens
              </button>
              <button
                type="button"
                className="rounded border border-dfui-border/50 px-2 py-1 text-[10px]"
                onClick={() =>
                  void evolvePrompts({
                    prompt: settings.prompt ?? "",
                    mode: "Words",
                    strength: 35,
                  }).then(setVariants)
                }
              >
                Words
              </button>
              <button
                type="button"
                className="rounded border border-dfui-border/50 px-2 py-1 text-[10px]"
                onClick={() =>
                  void evolvePrompts({
                    prompt: settings.prompt ?? "",
                    mode: "OBP Variant",
                    strength: 35,
                  }).then(setVariants)
                }
              >
                OBP
              </button>
            </div>
            <ul className="mt-2 max-h-48 space-y-1 overflow-y-auto">
              {variants.map((v, i) => (
                <li key={i}>
                  <button
                    type="button"
                    className="w-full rounded border border-dfui-border/30 px-2 py-1.5 text-left text-[10px] hover:border-dfui-accent/40"
                    onClick={() => {
                      onChange({ prompt: v });
                      setEvolveOpen(false);
                      setVariants([]);
                    }}
                  >
                    {v}
                  </button>
                </li>
              ))}
            </ul>
            <button
              type="button"
              className="mt-2 w-full text-center text-[10px] text-dfui-muted"
              onClick={() => {
                setEvolveOpen(false);
                setVariants([]);
              }}
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
