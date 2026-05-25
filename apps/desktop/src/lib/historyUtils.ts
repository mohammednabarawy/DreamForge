export const HISTORY_PAGE_SIZE = 50;

export function formatRelativeTime(iso: string): string {
  try {
    const d = new Date(iso);
    const now = Date.now();
    const diff = now - d.getTime();
    const sec = Math.floor(diff / 1000);
    if (sec < 60) return "just now";
    const min = Math.floor(sec / 60);
    if (min < 60) return `${min}m ago`;
    const hr = Math.floor(min / 60);
    if (hr < 24) return `${hr}h ago`;
    const day = Math.floor(hr / 24);
    if (day < 7) return `${day}d ago`;
    return d.toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
    });
  } catch {
    return iso;
  }
}

export function excerptPrompt(prompt: string, max = 72): string {
  const t = prompt.replace(/\s+/g, " ").trim();
  if (!t) return "";
  if (t.length <= max) return t;
  return `${t.slice(0, max - 1)}…`;
}

export function modelBadgeLabel(stem: string, family: string): string {
  const s = stem?.trim();
  if (s && s !== "unknown") return s;
  const f = family?.trim();
  if (f && f !== "unknown") return f;
  return "model";
}
