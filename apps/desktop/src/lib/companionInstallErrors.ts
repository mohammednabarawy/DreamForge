export type InstallErrorLike = {
  pack_id?: string;
  error?: string;
  code?: string;
  hint?: string;
};

export function isManagerSecurityBlocked(error: InstallErrorLike | string | undefined): boolean {
  if (!error) return false;
  if (typeof error === "string") {
    const text = error.toLowerCase();
    return text.includes("security policy") || text.includes("403") || text.includes("manager_security_blocked");
  }
  if (error.code === "manager_security_blocked") return true;
  return isManagerSecurityBlocked(error.error);
}

export function formatCompanionInstallError(error: InstallErrorLike): string {
  const label = error.pack_id ?? "install";
  if (isManagerSecurityBlocked(error)) {
    const hint =
      error.hint ??
      "Open ComfyUI → Manager → Settings → Security and allow the repository, or use the pinned DreamForge pack when offered.";
    return `${label}: blocked by ComfyUI-Manager security policy. ${hint}`;
  }
  return `${label}: ${error.error ?? "unknown error"}`;
}
