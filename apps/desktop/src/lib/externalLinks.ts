export async function openExternalUrl(url: string): Promise<void> {
  const parsed = new URL(url);
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") throw new Error("Only HTTP(S) links can be opened");
  const { openUrl } = await import("@tauri-apps/plugin-opener");
  await openUrl(parsed.toString());
}
