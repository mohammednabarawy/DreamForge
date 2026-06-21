/** One-line status for the canvas footer; full text lives in FullLogModal. */
export function summarizeGenerationLog(log: string): string {
  const lines = log
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  if (!lines.length) return "";
  const last = lines[lines.length - 1];
  const prefixed = last.match(/^(?:started|progress|error|finished|warning):\s*(.+)$/i);
  return prefixed ? prefixed[1] : last;
}
