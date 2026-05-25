/** Parse and format DreamForge LoRA tokens (`name:weight`). */

export type LoraEntry = { name: string; weight: number };

const DEFAULT_WEIGHT = 1;

/** Matches Gradio `default_max_lora_number` in config_modification_tutorial.txt */
export const DEFAULT_MAX_LORA_STACK = 5;

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

export function clampLoraWeight(
  weight: number,
  min: number,
  max: number,
): number {
  const lo = Math.min(min, max);
  const hi = Math.max(min, max);
  const step = 0.05;
  const clamped = Math.min(hi, Math.max(lo, weight));
  return Math.round(clamped / step) * step;
}

/** Move active LoRA up/down in stack order (affects backend load order). */
export function moveLoraInList(
  tokens: string[],
  name: string,
  direction: "up" | "down",
): string[] {
  const entries = parseLoraList(tokens);
  const idx = entries.findIndex((e) => e.name === name);
  if (idx < 0) return tokens;
  const swap = direction === "up" ? idx - 1 : idx + 1;
  if (swap < 0 || swap >= entries.length) return tokens;
  const next = [...entries];
  [next[idx], next[swap]] = [next[swap], next[idx]];
  return loraListToTokens(next);
}
