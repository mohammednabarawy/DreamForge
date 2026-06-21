import { ImagePlus, RefreshCw, Tag, X } from "lucide-react";
import { useMemo, useState } from "react";
import {
  REFERENCE_PACK_ROLE_HINTS,
  REFERENCE_PACK_TYPES,
  formatAttachedReferencePackLine,
} from "../lib/referencePackUi";
import type { GenerationSettings } from "../lib/tauri-api";
import type { ReferencePack } from "../lib/studioBridge";
import {
  RegistryImagePicker,
  mergeRegistryImagePaths,
} from "./RegistryImagePicker";

type Props = {
  settings: GenerationSettings;
  referencePacks: ReferencePack[];
  sessionImagePaths?: string[];
  onAttachReferencePack?: (packId: string) => void;
  onReferencePackRoleChange?: (role: ReferencePack["type"]) => void;
  onCreateReferencePack?: (
    name: string,
    type: ReferencePack["type"],
    meta?: { tags?: string[]; notes?: string; imagePaths?: string[] },
  ) => void | Promise<void>;
  onDeleteReferencePack?: (packId: string) => void | Promise<void>;
  onRefreshReferencePacks?: () => void | Promise<void>;
  compact?: boolean;
};

export function ReferencePacksPanel({
  settings,
  referencePacks,
  sessionImagePaths = [],
  onAttachReferencePack,
  onReferencePackRoleChange,
  onCreateReferencePack,
  onDeleteReferencePack,
  onRefreshReferencePacks,
  compact = false,
}: Props) {
  const [newPackName, setNewPackName] = useState("");
  const [newPackType, setNewPackType] = useState<ReferencePack["type"]>("style");
  const [newPackTags, setNewPackTags] = useState("");
  const [newPackNotes, setNewPackNotes] = useState("");
  const [stagingPaths, setStagingPaths] = useState<string[]>([]);
  const [includeSession, setIncludeSession] = useState(true);

  const createImagePaths = useMemo(
    () => mergeRegistryImagePaths(stagingPaths, sessionImagePaths, includeSession),
    [includeSession, sessionImagePaths, stagingPaths],
  );

  const attached = useMemo(
    () => referencePacks.find((pack) => pack.id === settings.reference_pack_id),
    [referencePacks, settings.reference_pack_id],
  );

  const attachedRole = (settings.reference_pack_role ??
    attached?.type ??
    "style") as ReferencePack["type"];

  const attachedLine = formatAttachedReferencePackLine(attached, attachedRole);

  return (
    <div
      className={`flex min-h-0 flex-col gap-2 ${compact ? "max-h-[420px] overflow-y-auto" : ""}`}
    >
      <div className="flex shrink-0 items-start justify-between gap-2 rounded-lg border border-dfui-border/45 bg-dfui-bg/30 px-2.5 py-2">
        <div className="min-w-0">
          <p className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide text-dfui-muted">
            <Tag size={12} className="text-dfui-accent" />
            Reference packs
          </p>
          <p className="mt-0.5 text-[10px] text-dfui-tertiary">
            Named local images for identity, product, brand, or style guidance across Generate,
            Edit, and Agent.
          </p>
        </div>
        {onRefreshReferencePacks && (
          <button
            type="button"
            onClick={() => void onRefreshReferencePacks()}
            className="inline-flex shrink-0 items-center gap-1 rounded-md border border-dfui-border/60 px-2 py-1 text-[10px] text-dfui-secondary hover:border-dfui-accent/40"
          >
            <RefreshCw size={11} />
            Refresh
          </button>
        )}
      </div>

      {attached && onAttachReferencePack && (
        <div className="shrink-0 space-y-2 rounded-lg border border-dfui-accent/30 bg-dfui-accent/5 px-2.5 py-2">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <p className="text-[10px] uppercase tracking-wide text-dfui-muted">Attached</p>
              <p className="truncate text-xs font-medium text-dfui-fg">{attached.name}</p>
              {attachedLine && (
                <p className="mt-0.5 text-[9px] text-dfui-secondary">{attachedLine}</p>
              )}
              <p className="mt-1 text-[9px] text-dfui-tertiary">
                {attached.image_paths?.length ?? 0} image
                {(attached.image_paths?.length ?? 0) === 1 ? "" : "s"}
                {(attached.tags?.length ?? 0) > 0
                  ? ` · ${attached.tags!.slice(0, 4).join(", ")}`
                  : ""}
              </p>
            </div>
            <button
              type="button"
              onClick={() => onAttachReferencePack("")}
              className="shrink-0 rounded p-1 text-dfui-muted hover:bg-dfui-surface-hover hover:text-dfui-fg"
              title="Detach reference pack"
            >
              <X size={14} />
            </button>
          </div>
          {onReferencePackRoleChange && (
            <label className="block">
              <span className="text-[9px] text-dfui-tertiary">Planner role</span>
              <select
                value={attachedRole}
                onChange={(e) =>
                  onReferencePackRoleChange(e.target.value as ReferencePack["type"])
                }
                className="df-select mt-0.5 w-full px-2 py-1.5 text-xs"
              >
                {REFERENCE_PACK_TYPES.map((type) => (
                  <option key={type} value={type}>
                    {type} — {REFERENCE_PACK_ROLE_HINTS[type]}
                  </option>
                ))}
              </select>
            </label>
          )}
        </div>
      )}

      {onCreateReferencePack && (
        <div className="shrink-0 space-y-1.5 rounded-lg border border-dfui-border/45 bg-dfui-bg/25 p-2.5">
          <p className="flex items-center gap-1 text-[10px] font-medium uppercase tracking-wide text-dfui-muted">
            <ImagePlus size={12} className="text-df-blue" />
            New reference pack
          </p>
          <RegistryImagePicker
            stagingPaths={stagingPaths}
            onStagingChange={setStagingPaths}
            sessionPaths={sessionImagePaths}
            includeSession={includeSession}
            onIncludeSessionChange={setIncludeSession}
          />
          <div className="grid grid-cols-[1fr_auto] gap-1.5">
            <input
              value={newPackName}
              onChange={(e) => setNewPackName(e.target.value)}
              placeholder="Pack name"
              className="df-input px-2 py-1.5 text-xs"
            />
            <select
              value={newPackType}
              onChange={(e) => setNewPackType(e.target.value as ReferencePack["type"])}
              className="df-select px-2 py-1.5 text-xs"
            >
              {REFERENCE_PACK_TYPES.map((type) => (
                <option key={type} value={type}>
                  {type}
                </option>
              ))}
            </select>
            <input
              value={newPackTags}
              onChange={(e) => setNewPackTags(e.target.value)}
              placeholder="Tags (comma separated)"
              className="df-input col-span-2 px-2 py-1.5 text-xs"
            />
            <textarea
              value={newPackNotes}
              onChange={(e) => setNewPackNotes(e.target.value)}
              placeholder="Notes for planner and future you"
              rows={2}
              className="df-input col-span-2 resize-none px-2 py-1.5 text-xs"
            />
            <button
              type="button"
              onClick={() => {
                const name = newPackName.trim();
                if (!name || createImagePaths.length === 0) return;
                const tags = newPackTags
                  .split(",")
                  .map((t) => t.trim())
                  .filter(Boolean);
                void Promise.resolve(
                  onCreateReferencePack(name, newPackType, {
                    tags,
                    notes: newPackNotes.trim(),
                    imagePaths: createImagePaths,
                  }),
                ).then(() => {
                  setNewPackName("");
                  setNewPackTags("");
                  setNewPackNotes("");
                  setStagingPaths([]);
                });
              }}
              disabled={!newPackName.trim() || createImagePaths.length === 0}
              className="col-span-2 rounded-md border border-dfui-accent/40 bg-dfui-accent/10 px-2 py-1.5 text-[10px] font-medium text-dfui-accent disabled:opacity-50"
            >
              Save pack ({createImagePaths.length} image
              {createImagePaths.length === 1 ? "" : "s"})
            </button>
          </div>
        </div>
      )}

      <div className={`df-gallery-pane min-h-0 ${compact ? "max-h-48" : ""}`}>
        {referencePacks.length === 0 ? (
          <p className="rounded-lg border border-dashed border-dfui-border/50 px-3 py-6 text-center text-[11px] text-dfui-muted">
            No packs yet. Add images below, name the pack, and save.
          </p>
        ) : (
          <ul className="space-y-1.5">
            {referencePacks.map((pack) => {
              const selected = pack.id === settings.reference_pack_id;
              return (
                <li
                  key={pack.id}
                  className={`rounded-lg border px-2 py-1.5 transition ${
                    selected
                      ? "border-dfui-accent/45 bg-dfui-accent/10"
                      : "border-dfui-border/45 bg-dfui-bg/25 hover:border-df-blue/35"
                  }`}
                >
                  <div className="flex items-start gap-2">
                    <button
                      type="button"
                      disabled={!onAttachReferencePack}
                      onClick={() => onAttachReferencePack?.(pack.id)}
                      className="min-w-0 flex-1 text-left disabled:opacity-50"
                    >
                      <p className="truncate text-xs font-medium text-dfui-fg">{pack.name}</p>
                      <p className="mt-0.5 text-[9px] text-dfui-muted">
                        {pack.type} · {pack.image_paths?.length ?? 0} image
                        {(pack.image_paths?.length ?? 0) === 1 ? "" : "s"}
                      </p>
                      {(pack.preferred_use_cases?.length ?? 0) > 0 && (
                        <p className="mt-0.5 text-[9px] text-dfui-tertiary">
                          {pack.preferred_use_cases!.slice(0, 3).join(" · ")}
                        </p>
                      )}
                      {pack.notes?.trim() && (
                        <p className="mt-0.5 line-clamp-2 text-[9px] text-dfui-tertiary">
                          {pack.notes}
                        </p>
                      )}
                    </button>
                    {onDeleteReferencePack && (
                      <button
                        type="button"
                        onClick={() => void onDeleteReferencePack(pack.id)}
                        className="shrink-0 rounded border border-red-400/25 px-1.5 py-0.5 text-[9px] text-red-300 hover:border-red-400/50"
                        title="Delete pack (keeps source image files)"
                      >
                        Delete
                      </button>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
