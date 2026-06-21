import { ShieldCheck, Tag } from "lucide-react";
import { useState } from "react";
import type { GenerationSettings } from "../lib/tauri-api";
import type { IdentityRecord, ReferencePack } from "../lib/studioBridge";
import { IdentitiesPanel } from "./IdentitiesPanel";
import { ReferencePacksPanel } from "./ReferencePacksPanel";

type RefsSection = "packs" | "identities";

type Props = {
  settings: GenerationSettings;
  referencePacks: ReferencePack[];
  identities: IdentityRecord[];
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
};

export function RefsInspectorPanel({
  settings,
  referencePacks,
  identities,
  sessionImagePaths = [],
  onAttachReferencePack,
  onReferencePackRoleChange,
  onCreateReferencePack,
  onDeleteReferencePack,
  onRefreshReferencePacks,
  onAttachIdentity,
  onIdentityRoleChange,
  onChange,
  onCreateIdentity,
  onDeleteIdentity,
  onRefreshIdentities,
}: Props) {
  const [section, setSection] = useState<RefsSection>("packs");

  const packAttached = Boolean(settings.reference_pack_id);
  const identityAttached = Boolean(settings.identity_id);

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-2">
      <div className="flex shrink-0 gap-1 rounded-lg border border-dfui-border/50 bg-dfui-bg/30 p-1">
        <button
          type="button"
          onClick={() => setSection("packs")}
          className={`flex min-w-0 flex-1 items-center justify-center gap-1.5 rounded-md px-2 py-1.5 text-[10px] font-medium transition ${
            section === "packs"
              ? "bg-dfui-accent/15 text-dfui-accent"
              : "text-dfui-secondary hover:bg-dfui-surface-hover/60"
          }`}
        >
          <Tag size={12} />
          Packs
          {packAttached && (
            <span className="rounded-full bg-dfui-accent/25 px-1 font-mono text-[9px]">1</span>
          )}
        </button>
        <button
          type="button"
          onClick={() => setSection("identities")}
          className={`flex min-w-0 flex-1 items-center justify-center gap-1.5 rounded-md px-2 py-1.5 text-[10px] font-medium transition ${
            section === "identities"
              ? "bg-dfui-accent/15 text-dfui-accent"
              : "text-dfui-secondary hover:bg-dfui-surface-hover/60"
          }`}
        >
          <ShieldCheck size={12} />
          Identities
          {identityAttached && (
            <span className="rounded-full bg-dfui-accent/25 px-1 font-mono text-[9px]">1</span>
          )}
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto pr-0.5">
        {section === "packs" ? (
          <ReferencePacksPanel
            settings={settings}
            referencePacks={referencePacks}
            sessionImagePaths={sessionImagePaths}
            onAttachReferencePack={onAttachReferencePack}
            onReferencePackRoleChange={onReferencePackRoleChange}
            onCreateReferencePack={onCreateReferencePack}
            onDeleteReferencePack={onDeleteReferencePack}
            onRefreshReferencePacks={onRefreshReferencePacks}
          />
        ) : (
          <IdentitiesPanel
            settings={settings}
            identities={identities}
            sessionImagePaths={sessionImagePaths}
            onAttachIdentity={onAttachIdentity}
            onIdentityRoleChange={onIdentityRoleChange}
            onChange={onChange}
            onCreateIdentity={onCreateIdentity}
            onDeleteIdentity={onDeleteIdentity}
            onRefreshIdentities={onRefreshIdentities}
          />
        )}
      </div>
    </div>
  );
}
