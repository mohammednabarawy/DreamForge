import type { AttachedReferencePack, ReferencePack } from "./studioBridge";

export const REFERENCE_PACK_TYPES: ReferencePack["type"][] = [
  "person",
  "character",
  "product",
  "brand",
  "style",
];

export const REFERENCE_PACK_ROLE_HINTS: Record<ReferencePack["type"], string> = {
  person: "Face and likeness guidance",
  character: "Character consistency across edits",
  product: "Product shape, label, and packaging",
  brand: "Brand colors, logo, and visual identity",
  style: "Palette, composition, and art direction",
};

export function referencePackRoleLabel(
  role: string | undefined,
  fallbackType?: string,
): string {
  const key = (role || fallbackType || "style").toLowerCase();
  return REFERENCE_PACK_ROLE_HINTS[key as ReferencePack["type"]] ?? key;
}

export function formatAttachedReferencePackLine(
  pack: Pick<ReferencePack, "name" | "type"> | undefined,
  role?: string,
): string | undefined {
  if (!pack?.name) return undefined;
  const roleKey = (role || pack.type || "style").toLowerCase();
  return `${pack.name} · ${roleKey} — ${referencePackRoleLabel(roleKey, pack.type)}`;
}

export function formatPlanReferencePackSuffix(
  pack: AttachedReferencePack | undefined,
  roleOverride?: string,
): string {
  if (!pack?.name && !pack?.id) return "";
  const name = pack.name ?? pack.id ?? "pack";
  const role = (roleOverride || pack.type || "style").toLowerCase();
  const uses =
    pack.preferred_use_cases?.length && pack.preferred_use_cases.length > 0
      ? ` (${pack.preferred_use_cases.slice(0, 2).join(", ")})`
      : "";
  return `Reference pack «${name}» as ${role}${uses}.`;
}
