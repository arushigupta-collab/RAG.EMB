// Fetch-based SSE reader. The browser's native EventSource only supports GET,
// but /query is a POST, so we parse the event stream off the fetch body ourselves.
// Handles both POST (/query) and GET (/ingest/{job}/events) streams.

import { API_BASE } from "./api";

export interface SSEHandlers {
  [event: string]: (data: any) => void;
}

export async function streamSSE(
  path: string,
  init: RequestInit,
  handlers: SSEHandlers,
  signal?: AbortSignal
): Promise<void> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { Accept: "text/event-stream", ...(init.headers || {}) },
    signal,
  });
  if (!res.body) throw new Error("No response body for SSE stream");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    // Normalize CRLF -> LF so the frame split works regardless of whether the
    // server uses "\r\n\r\n" (sse-starlette default) or "\n\n" between events.
    buffer = buffer.replace(/\r\n/g, "\n");

    // SSE frames are separated by a blank line.
    let sep: number;
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);

      let event = "message";
      const dataLines: string[] = [];
      for (const line of frame.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
      }
      if (dataLines.length === 0) continue;
      const raw = dataLines.join("\n");
      let parsed: any = raw;
      try {
        parsed = JSON.parse(raw);
      } catch {
        /* keep raw string */
      }
      handlers[event]?.(parsed);
    }
  }
}
