// Talks to the LinguaLive server (live_translate/server.py), which holds the
// Claude API key. The app never stores the API key itself.
import { fetch } from "expo/fetch";

export type ContextPair = { source: string; translation: string };

/** POST JSON and stream Server-Sent Events; calls onDelta for each text chunk. */
async function streamSSE(
  url: string,
  payload: unknown,
  onDelta: (text: string) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(payload),
    signal,
  });
  if (!res.ok) throw new Error(`伺服器回應 HTTP ${res.status}`);
  if (!res.body) throw new Error("伺服器沒有回傳內容");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let i: number;
    while ((i = buf.indexOf("\n\n")) >= 0) {
      const block = buf.slice(0, i);
      buf = buf.slice(i + 2);
      const event = block.match(/^event: (.*)$/m)?.[1];
      const raw = block.match(/^data: (.*)$/m)?.[1];
      if (!event || !raw) continue;
      const data = JSON.parse(raw) as { text?: string; message?: string };
      if (event === "delta" && data.text) onDelta(data.text);
      else if (event === "error") throw new Error(data.message ?? "翻譯失敗");
    }
  }
}

const base = (serverUrl: string) => serverUrl.trim().replace(/\/+$/, "");

export function translate(
  serverUrl: string,
  req: {
    text: string;
    source_lang: string;
    target_lang: string;
    context: ContextPair[];
    glossary: string;
    style: string;
  },
  onDelta: (t: string) => void,
  signal?: AbortSignal,
) {
  return streamSSE(`${base(serverUrl)}/api/translate`, req, onDelta, signal);
}

export function explain(
  serverUrl: string,
  req: { text: string; translation: string; target_lang: string; explain_lang: string },
  onDelta: (t: string) => void,
) {
  return streamSSE(`${base(serverUrl)}/api/explain`, req, onDelta);
}

export async function checkHealth(serverUrl: string): Promise<{ model: string; credentials: boolean }> {
  const res = await fetch(`${base(serverUrl)}/api/health`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return (await res.json()) as { model: string; credentials: boolean };
}
