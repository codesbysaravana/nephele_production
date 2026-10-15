/** VITE_WS_URL is the backend origin (https://host or wss://host), not /ws/voice. */
export function voiceUrl(
  configured: string | undefined,
  page: Location,
): string {
  const local = page.hostname === "localhost" || page.hostname === "127.0.0.1";
  const base = configured?.trim() || (local ? "http://localhost:8000" : "");
  if (!base)
    throw new Error(
      "Voice is not configured. The site owner needs to set VITE_WS_URL.",
    );
  const url = new URL(base);
  if (
    !["http:", "https:", "ws:", "wss:"].includes(url.protocol) ||
    url.username ||
    url.password ||
    url.search ||
    url.hash
  ) {
    throw new Error("The voice service URL is invalid.");
  }
  url.protocol =
    url.protocol === "https:" || url.protocol === "wss:" ? "wss:" : "ws:";
  if (page.protocol === "https:" && url.protocol !== "wss:") {
    throw new Error(
      "The voice service must use a secure connection on this site.",
    );
  }
  url.pathname = `${url.pathname.replace(/\/$/, "")}/ws/voice`;
  return url.toString();
}
