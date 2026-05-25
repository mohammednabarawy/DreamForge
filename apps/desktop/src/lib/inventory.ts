export type ModelEntry = {
  name: string;
  stem?: string;
  family?: string;
  category?: string;
  size_mb?: number;
};

export type StyleItem = { id: string; label: string };
export type StyleGroup = { id: string; label: string; items: StyleItem[] };

const GENERATION_CATEGORIES = ["checkpoints", "diffusion_models", "unet"] as const;

export function mergeGenerationModels(
  categories: Record<string, ModelEntry[]>,
): ModelEntry[] {
  const seen = new Set<string>();
  const merged: ModelEntry[] = [];
  for (const key of GENERATION_CATEGORIES) {
    for (const m of categories[key] ?? []) {
      if (!m?.name || seen.has(m.name)) continue;
      seen.add(m.name);
      merged.push({
        ...m,
        category: m.category ?? key,
      });
    }
  }
  return merged.sort((a, b) => a.name.localeCompare(b.name));
}

export function parseInventoryResponse(raw: Record<string, unknown>) {
  const categories = (raw.categories ?? {}) as Record<string, ModelEntry[]>;
  const styleGroups = (raw.style_groups ?? []) as StyleGroup[];
  const styles = (raw.styles ?? []) as string[];
  return {
    checkpoints: mergeGenerationModels(categories),
    loras: (categories.loras ?? categories.lora ?? []) as ModelEntry[],
    styles: styles.length ? styles : styleGroups.flatMap((g) => g.items.map((i) => i.id)),
    styleGroups,
    presets: (raw.presets ?? []) as unknown[],
  };
}
