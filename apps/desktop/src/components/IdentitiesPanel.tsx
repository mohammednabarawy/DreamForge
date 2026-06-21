import { ImagePlus, RefreshCw, ShieldCheck, X } from "lucide-react";
import { useMemo, useState } from "react";
import {
  IDENTITY_TYPES,
  IDENTITY_ROLE_HINTS,
  formatAttachedIdentityLine,
} from "../lib/identityUi";
import type { GenerationSettings } from "../lib/tauri-api";
import type { IdentityRecord } from "../lib/studioBridge";
import {
  RegistryImagePicker,
  mergeRegistryImagePaths,
} from "./RegistryImagePicker";

type Props = {
  settings: GenerationSettings;
  identities: IdentityRecord[];
  sessionImagePaths?: string[];
  onAttachIdentity?: (identityId: string) => void;
  onIdentityRoleChange?: (role: IdentityRecord["type"]) => void;
  onChange?: (patch: Partial<GenerationSettings>) => void;
  onCreateIdentity?: (
    name: string,
    type: IdentityRecord["type"],
    imagePaths?: string[],
  ) => void | Promise<void>;
  onDeleteIdentity?: (identityId: string) => void | Promise<void>;
  onRefreshIdentities?: () => void | Promise<void>;
  compact?: boolean;
};

export function IdentitiesPanel({
  settings,
  identities,
  sessionImagePaths = [],
  onAttachIdentity,
  onIdentityRoleChange,
  onChange,
  onCreateIdentity,
  onDeleteIdentity,
  onRefreshIdentities,
  compact = false,
}: Props) {
  const [newIdentityName, setNewIdentityName] = useState("");
  const [newIdentityType, setNewIdentityType] = useState<IdentityRecord["type"]>("person");
  const [stagingPaths, setStagingPaths] = useState<string[]>([]);
  const [includeSession, setIncludeSession] = useState(true);

  const isQwenModel = String(settings.model ?? "").toLowerCase().includes("qwen");

  const createImagePaths = useMemo(
    () => mergeRegistryImagePaths(stagingPaths, sessionImagePaths, includeSession),
    [includeSession, sessionImagePaths, stagingPaths],
  );

  const attached = useMemo(
    () => identities.find((identity) => identity.id === settings.identity_id),
    [identities, settings.identity_id],
  );

  const attachedRole = (settings.identity_role ??
    attached?.type ??
    "style") as IdentityRecord["type"];

  const attachedLine = formatAttachedIdentityLine(attached, attachedRole);

  return (
    <div
      className={`flex min-h-0 flex-col gap-2 ${compact ? "max-h-[420px] overflow-y-auto" : ""}`}
    >
      <div className="flex shrink-0 items-start justify-between gap-2 rounded-lg border border-dfui-border/45 bg-dfui-bg/30 px-2.5 py-2">
        <div className="min-w-0">
          <p className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide text-dfui-muted">
            <ShieldCheck size={12} className="text-dfui-accent" />
            Identity registry
          </p>
          <p className="mt-0.5 text-[10px] text-dfui-tertiary">
            Named local identities for people, products, brands, styles, and places — with optional
            FaceID preservation.
          </p>
        </div>
        {onRefreshIdentities && (
          <button
            type="button"
            onClick={() => void onRefreshIdentities()}
            className="inline-flex shrink-0 items-center gap-1 rounded-md border border-dfui-border/60 px-2 py-1 text-[10px] text-dfui-secondary hover:border-dfui-accent/40"
          >
            <RefreshCw size={11} />
            Refresh
          </button>
        )}
      </div>

      {attached && onAttachIdentity && (
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
              onClick={() => onAttachIdentity("")}
              className="shrink-0 rounded p-1 text-dfui-muted hover:bg-dfui-surface-hover hover:text-dfui-fg"
              title="Detach identity"
            >
              <X size={14} />
            </button>
          </div>
          {onIdentityRoleChange && (
            <label className="block">
              <span className="text-[9px] text-dfui-tertiary">Planner role</span>
              <select
                value={attachedRole}
                onChange={(e) =>
                  onIdentityRoleChange(e.target.value as IdentityRecord["type"])
                }
                className="df-select mt-0.5 w-full px-2 py-1.5 text-xs"
              >
                {IDENTITY_TYPES.map((type) => (
                  <option key={type} value={type}>
                    {type} — {IDENTITY_ROLE_HINTS[type]}
                  </option>
                ))}
              </select>
            </label>
          )}
          {onChange && (
            isQwenModel ? (
              <div className="text-[10px] text-dfui-secondary italic bg-dfui-bg-subtle p-1.5 rounded border border-dfui-border-subtle/50 w-full mt-1">
                Face guidance for Qwen Edit uses prompt guards; verify identity match in the output.
              </div>
            ) : (
              <label className="inline-flex items-center gap-1.5 text-[10px] text-dfui-secondary mt-1">
                <input
                  type="checkbox"
                  checked={Boolean(settings.face_preservation)}
                  onChange={(e) =>
                    onChange({
                      face_preservation: e.target.checked,
                      identity_mode: e.target.checked ? "faceid" : undefined,
                    })
                  }
                  className="accent-dfui-accent"
                />
                Require local FaceID preservation
              </label>
            )
          )}
        </div>
      )}

      {onCreateIdentity && (
        <div className="shrink-0 space-y-1.5 rounded-lg border border-dfui-border/45 bg-dfui-bg/25 p-2.5">
          <p className="flex items-center gap-1 text-[10px] font-medium uppercase tracking-wide text-dfui-muted">
            <ImagePlus size={12} className="text-df-blue" />
            New identity
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
              value={newIdentityName}
              onChange={(e) => setNewIdentityName(e.target.value)}
              placeholder="Identity name"
              className="df-input px-2 py-1.5 text-xs"
            />
            <select
              value={newIdentityType}
              onChange={(e) => setNewIdentityType(e.target.value as IdentityRecord["type"])}
              className="df-select px-2 py-1.5 text-xs"
            >
              {IDENTITY_TYPES.map((type) => (
                <option key={type} value={type}>
                  {type}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={() => {
                const name = newIdentityName.trim();
                if (!name || createImagePaths.length === 0) return;
                void Promise.resolve(onCreateIdentity(name, newIdentityType, createImagePaths)).then(
                  () => {
                    setNewIdentityName("");
                    setStagingPaths([]);
                  },
                );
              }}
              disabled={!newIdentityName.trim() || createImagePaths.length === 0}
              className="col-span-2 rounded-md border border-dfui-accent/40 bg-dfui-accent/10 px-2 py-1.5 text-[10px] font-medium text-dfui-accent disabled:opacity-50"
            >
              Save identity ({createImagePaths.length} image
              {createImagePaths.length === 1 ? "" : "s"})
            </button>
          </div>
        </div>
      )}

      <div className={`df-gallery-pane min-h-0 ${compact ? "max-h-48" : ""}`}>
        {identities.length === 0 ? (
          <p className="rounded-lg border border-dashed border-dfui-border/50 px-3 py-6 text-center text-[11px] text-dfui-muted">
            No identities yet. Add images below, name the identity, and save.
          </p>
        ) : (
          <ul className="space-y-1.5">
            {identities.map((identity) => {
              const selected = identity.id === settings.identity_id;
              return (
                <li
                  key={identity.id}
                  className={`rounded-lg border px-2 py-1.5 transition ${
                    selected
                      ? "border-dfui-accent/45 bg-dfui-accent/10"
                      : "border-dfui-border/45 bg-dfui-bg/25 hover:border-df-blue/35"
                  }`}
                >
                  <div className="flex items-start gap-2">
                    <button
                      type="button"
                      disabled={!onAttachIdentity}
                      onClick={() => onAttachIdentity?.(identity.id)}
                      className="min-w-0 flex-1 text-left disabled:opacity-50"
                    >
                      <p className="truncate text-xs font-medium text-dfui-fg">{identity.name}</p>
                      <p className="mt-0.5 text-[9px] text-dfui-muted">
                        {identity.type} · {identity.image_paths?.length ?? 0} image
                        {(identity.image_paths?.length ?? 0) === 1 ? "" : "s"}
                        {identity.embedding_status !== "not_extracted"
                          ? ` · ${identity.embedding_status}`
                          : ""}
                      </p>
                      {identity.notes?.trim() && (
                        <p className="mt-0.5 line-clamp-2 text-[9px] text-dfui-tertiary">
                          {identity.notes}
                        </p>
                      )}
                    </button>
                    {onDeleteIdentity && (
                      <button
                        type="button"
                        onClick={() => void onDeleteIdentity(identity.id)}
                        className="shrink-0 rounded border border-red-400/25 px-1.5 py-0.5 text-[9px] text-red-300 hover:border-red-400/50"
                        title="Delete identity from registry"
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
