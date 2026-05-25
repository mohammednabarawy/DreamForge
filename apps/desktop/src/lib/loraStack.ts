/** Parse and format DreamForge LoRA tokens (`name:weight`). */

export type LoraEntry = { name: string; weight: number };

const DEFAULT_WEIGHT = 1;

export function parseLoraToken(token: string): LoraEntry | null {
  const trimmed = token.trim();
  if (!trimmed) return null;
  const colon = trimmed.lastIndexOf(":");
  if (colon <= 0) return { name: trimmed, weight: DEFAULT_WEIGHT };
  const name = trimmed.slice(0, colon).trim();
  const weight = Number.parseFloat(trimmed.slice(colon + 1));
  if (!name) return null;
  return {
    name,
    weight: Number.isFinite(weight) ? weight : DEFAULT_WEIGHT,
  };
}

export function formatLoraToken(name: string, weight: number): string {
  const w = Math.round(weight * 100) / 100;
  return `${name}:${w}`;
}

export function parseLoraList(tokens: string[] | undefined): LoraEntry[] {
  if (!tokens?.length) return [];
  const out: LoraEntry[] = [];
  for (const t of tokens) {
    const parsed = parseLoraToken(t);
    if (parsed) out.push(parsed);
  }
  return out;
}

export function loraListToTokens(entries: LoraEntry[]): string[] {
  return entries.map((e) => formatLoraToken(e.name, e.weight));
}

export function upsertLora(
  tokens: string[],
  name: string,
  weight: number,
): string[] {
  const entries = parseLoraList(tokens).filter((e) => e.name !== name);
  entries.push({ name, weight });
  return loraListToTokens(entries);
}

export function removeLora(tokens: string[], name: string): string[] {
  return parseLoraList(tokens)
    .filter((e) => e.name !== name)
    .map((e) => formatLoraToken(e.name, e.weight));
}

export function hasLora(tokens: string[], name: string): boolean {
  return parseLoraList(tokens).some((e) => e.name === name);
}

export function loraWeightFromToken(
  tokens: string[],
  name: string,
  fallback = DEFAULT_WEIGHT,
): number {
  const hit = parseLoraList(tokens).find((e) => e.name === name);
  return hit?.weight ?? fallback;
}
