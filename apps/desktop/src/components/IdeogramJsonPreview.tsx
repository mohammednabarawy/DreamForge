import { AlertCircle, CheckCircle2, ChevronDown, ChevronUp } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { looksLikeIdeogramJson } from "../lib/ideogram4Ui";
import { validateIdeogram4Caption } from "../lib/studioBridge";

type Props = {
  prompt: string;
  enabled: boolean;
};

export function IdeogramJsonPreview({ prompt, enabled }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [ok, setOk] = useState<boolean | null>(null);
  const [errors, setErrors] = useState<string[]>([]);
  const [normalized, setNormalized] = useState<string | null>(null);

  const shouldValidate = enabled && looksLikeIdeogramJson(prompt);

  useEffect(() => {
    if (!shouldValidate) {
      setOk(null);
      setErrors([]);
      setNormalized(null);
      return;
    }
    const handle = window.setTimeout(() => {
      setBusy(true);
      void validateIdeogram4Caption(prompt)
        .then((res) => {
          setOk(res.ok);
          setErrors(res.errors ?? []);
          setNormalized(res.normalized ?? null);
        })
        .catch((err) => {
          setOk(false);
          setErrors([String(err)]);
          setNormalized(null);
        })
        .finally(() => setBusy(false));
    }, 350);
    return () => window.clearTimeout(handle);
  }, [prompt, shouldValidate]);

  const pretty = useMemo(() => {
    if (!normalized) return "";
    try {
      return JSON.stringify(JSON.parse(normalized), null, 2);
    } catch {
      return normalized;
    }
  }, [normalized]);

  if (!shouldValidate) return null;

  return (
    <div className="rounded-lg border border-dfui-border/45 bg-dfui-bg/25 px-2 py-1.5">
      <div className="flex items-center gap-2">
        {busy ? (
          <span className="text-[10px] text-dfui-muted">Validating caption…</span>
        ) : ok ? (
          <>
            <CheckCircle2 size={12} className="shrink-0 text-emerald-400" />
            <span className="text-[10px] text-emerald-300/90">Valid Ideogram JSON</span>
          </>
        ) : (
          <>
            <AlertCircle size={12} className="shrink-0 text-amber-400" />
            <span className="min-w-0 truncate text-[10px] text-amber-200/90">
              {errors[0] ?? "Invalid caption"}
            </span>
          </>
        )}
        {normalized ? (
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            className="ml-auto inline-flex items-center gap-0.5 text-[10px] text-dfui-muted hover:text-dfui-fg"
          >
            {expanded ? "Hide" : "Preview"}
            {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
          </button>
        ) : null}
      </div>
      {expanded && pretty ? (
        <pre className="mt-1.5 max-h-36 overflow-auto rounded border border-dfui-border/30 bg-dfui-panel/80 p-2 font-mono text-[9px] leading-relaxed text-dfui-secondary">
          {pretty}
        </pre>
      ) : null}
      {!busy && !ok && errors.length > 1 ? (
        <ul className="mt-1 list-inside list-disc text-[9px] text-amber-200/80">
          {errors.slice(1).map((err) => (
            <li key={err}>{err}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
