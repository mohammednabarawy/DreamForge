/**
 * Cross-platform clipboard write helper for Tauri WebViews (WKWebView & WebView2).
 * Falls back to execCommand("copy") when navigator.clipboard rejects in packaged contexts.
 */
export async function copyTextToClipboard(text: string): Promise<void> {
  if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return;
    } catch {
      /* fall through to legacy textarea copy */
    }
  }
  if (typeof document === "undefined") {
    throw new Error("Clipboard unavailable");
  }
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.top = "-9999px";
  textarea.style.left = "-9999px";
  document.body.appendChild(textarea);
  textarea.select();
  textarea.setSelectionRange(0, text.length);
  const ok = document.execCommand("copy");
  document.body.removeChild(textarea);
  if (!ok) {
    throw new Error("Copy command rejected by browser");
  }
}
