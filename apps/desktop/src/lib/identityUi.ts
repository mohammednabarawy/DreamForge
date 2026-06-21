import type { AttachedIdentityReference, IdentityRecord } from "./studioBridge";
import { formatPlanReferencePackSuffix } from "./referencePackUi";

export const IDENTITY_TYPES: IdentityRecord["type"][] = [
  "person",
  "character",
  "product",
  "brand",
  "style",
  "location",
];

export const IDENTITY_ROLE_HINTS: Record<IdentityRecord["type"], string> = {
  person: "Face and likeness across edits",
  character: "Character consistency (face, outfit, props)",
  product: "Product shape, materials, and labeling",
  brand: "Brand palette, logo, and visual system",
  style: "Art direction and composition language",
  location: "Place, architecture, and environment",
};

export function identityRoleLabel(
  role: string | undefined,
  fallbackType?: string,
): string {
  const key = (role || fallbackType || "style").toLowerCase();
  return IDENTITY_ROLE_HINTS[key as IdentityRecord["type"]] ?? key;
}

export function formatAttachedIdentityLine(
  identity: Pick<IdentityRecord, "name" | "type" | "embedding_status"> | undefined,
  role?: string,
): string | undefined {
  if (!identity?.name) return undefined;
  const roleKey = (role || identity.type || "style").toLowerCase();
  const embedding =
    identity.embedding_status && identity.embedding_status !== "not_extracted"
      ? ` · ${identity.embedding_status}`
      : "";
  return `${identity.name} · ${roleKey} — ${identityRoleLabel(roleKey, identity.type)}${embedding}`;
}

export function formatPlanIdentitySuffix(
  identity: AttachedIdentityReference | undefined,
  roleOverride?: string,
): string {
  if (!identity?.name && !identity?.id) return "";
  const name = identity.name ?? identity.id ?? "identity";
  const role = (roleOverride || identity.type || "style").toLowerCase();
  const embedding =
    identity.embedding_status && identity.embedding_status !== "not_extracted"
      ? ` · ${identity.embedding_status}`
      : "";
  return `Identity «${name}» as ${role}${embedding}.`;
}

export function formatPlanReferenceContext(args: {
  pack?: Parameters<typeof formatPlanReferencePackSuffix>[0];
  packRole?: string;
  identity?: AttachedIdentityReference;
  identityRole?: string;
}): string {
  const parts = [
    formatPlanReferencePackSuffix(args.pack, args.packRole),
    formatPlanIdentitySuffix(args.identity, args.identityRole),
  ].filter(Boolean);
  return parts.join(" ");
}
