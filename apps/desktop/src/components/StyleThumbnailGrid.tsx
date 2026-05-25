import type { StyleGroup } from "../lib/inventory";

/** Stable accent for style cards (Gradio uses text dropdown; desktop uses visual tiles). */
function styleAccent(id: string): string {
  let hash = 0;
  for (let i = 0; i < id.length; i++) {
    hash = (hash * 31 + id.charCodeAt(i)) >>> 0;
  }
  const hue = hash % 360;
  return `hsl(${hue} 42% 38%)`;
}

type Props = {
  groups: StyleGroup[];
  selected: string[];
  filter: string;
  onFilterChange: (value: string) => void;
  onToggle: (styleId: string) => void;
};

export function StyleThumbnailGrid({
  groups,
  selected,
  filter,
  onFilterChange,
  onToggle,
}: Props) {
  const q = filter.trim().toLowerCase();
  const filtered = groups
    .map((g) => ({
      ...g,
      items: g.items.filter(
        (i) =>
          !q ||
          i.label.toLowerCase().includes(q) ||
          i.id.toLowerCase().includes(q),
      ),
    }))
    .filter((g) => g.items.length > 0);

  return (
    <div className="space-y-2">
      <input
        value={filter}
        onChange={(e) => onFilterChange(e.target.value)}
        placeholder="Search styles…"
        className="w-full rounded-lg border border-dfui-border bg-dfui-bg/60 px-2 py-1.5 text-xs placeholder:text-dfui-tertiary"
      />
      {filtered.length === 0 ? (
        <p className="py-6 text-center text-xs text-dfui-muted">
          No styles match your search.
        </p>
      ) : (
        <div className="max-h-[calc(100vh-240px)] space-y-3 overflow-y-auto pr-0.5">
          {filtered.map((group) => (
            <div key={group.id}>
              <p className="mb-1 px-0.5 font-mono text-[10px] font-semibold uppercase tracking-wide text-dfui-data">
                {group.label}
              </p>
              <div className="grid grid-cols-2 gap-1.5">
                {group.items.map((item) => {
                  const checked = selected.includes(item.id);
                  return (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => onToggle(item.id)}
                      className={`relative overflow-hidden rounded-lg border px-2 py-2 text-left transition ${
                        checked
                          ? "border-dfui-accent ring-1 ring-dfui-accent/50"
                          : "border-dfui-border/50 hover:border-dfui-accent/30"
                      }`}
                      style={{
                        background: `linear-gradient(135deg, ${styleAccent(item.id)}22, transparent 70%)`,
                      }}
                    >
                      <p className="line-clamp-2 text-[10px] leading-snug text-dfui-fg">
                        {item.label}
                      </p>
                      {checked && (
                        <span className="absolute right-1 top-1 text-[10px] text-dfui-accent">
                          ✓
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
