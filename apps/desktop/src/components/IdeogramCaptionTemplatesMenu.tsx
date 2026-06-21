import { FileJson } from "lucide-react";
import { useEffect, useState } from "react";
import type { GenerationSettings } from "../lib/tauri-api";
import { ideogramAspectLabel } from "../lib/ideogram4Ui";
import {
  listIdeogram4CaptionTemplates,
  renderIdeogram4CaptionTemplate,
  type Ideogram4CaptionTemplate,
} from "../lib/studioBridge";

type Props = {
  settings: GenerationSettings;
  onChange: (patch: Partial<GenerationSettings>) => void;
  disabled?: boolean;
};

export function IdeogramCaptionTemplatesMenu({ settings, onChange, disabled }: Props) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [templates, setTemplates] = useState<Ideogram4CaptionTemplate[]>([]);

  useEffect(() => {
    if (!open || templates.length) return;
    void listIdeogram4CaptionTemplates().then(setTemplates).catch(() => setTemplates([]));
  }, [open, templates.length]);

  const applyTemplate = async (templateId: string) => {
    setBusy(true);
    try {
      const res = await renderIdeogram4CaptionTemplate({
        template_id: templateId,
        aspect_ratio: ideogramAspectLabel(settings),
      });
      if (!res.ok || !res.caption) return;
      const patch: Partial<GenerationSettings> = {
        prompt: res.caption,
        ideogram4_prompt_mode: "structured",
      };
      const ratio = res.template?.aspect_ratio;
      if (ratio && ratio.includes(":")) {
        const aspectMap: Record<string, string> = {
          "1:1": "768x768",
          "4:5": "704x880",
          "9:16": "576x1024",
          "16:9": "1024x576",
          "2:3": "704x1056",
        };
        const aspectRatio = aspectMap[ratio];
        if (aspectRatio) patch.aspect_ratio = aspectRatio;
      }
      onChange(patch);
      setOpen(false);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="relative">
      <button
        type="button"
        disabled={disabled || busy}
        onClick={() => setOpen((v) => !v)}
        className="flex min-h-8 items-center gap-1 rounded-md border border-dfui-border/50 px-2 text-[10px] text-dfui-muted hover:border-dfui-accent/40 hover:text-dfui-fg disabled:opacity-40"
        title="Insert a structured caption starter template"
      >
        <FileJson size={12} />
        Templates
      </button>
      {open ? (
        <div className="absolute bottom-full right-0 z-20 mb-1 w-64 rounded-lg border border-dfui-border/60 bg-dfui-panel py-1 shadow-xl">
          {templates.length === 0 ? (
            <p className="px-3 py-2 text-[10px] text-dfui-muted">Loading templates…</p>
          ) : (
            templates.map((tpl) => (
              <button
                key={tpl.id}
                type="button"
                className="flex w-full flex-col items-start gap-0.5 px-3 py-2 text-left hover:bg-dfui-accent/10"
                onClick={() => void applyTemplate(tpl.id)}
              >
                <span className="text-xs text-dfui-fg">{tpl.label}</span>
                {tpl.description ? (
                  <span className="text-[10px] text-dfui-muted">{tpl.description}</span>
                ) : null}
              </button>
            ))
          )}
        </div>
      ) : null}
    </div>
  );
}
