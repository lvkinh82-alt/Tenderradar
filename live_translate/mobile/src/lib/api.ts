// Talks to the Muối Từ translation server (live_translate/server.py), which holds the
// Claude API key. The app never stores the API key itself.
import { fetch } from "expo/fetch";

export type ContextPair = { source: string; translation: string };

/** POST JSON and stream Server-Sent Events; calls onDelta for each text chunk. */
const base = (serverUrl: string) => serverUrl.trim().replace(/\/+$/, "");

export type Server = { url: string; invite: string };

const inviteHeader = (invite: string) => ({ "X-Invite-Code": invite.trim().toUpperCase() });

async function streamSSE(
  server: Server,
  path: string,
  payload: unknown,
  onDelta: (text: string) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${base(server.url)}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream", ...inviteHeader(server.invite) },
    body: JSON.stringify(payload),
    signal,
  });
  if (!res.ok) {
    let message = `伺服器回應 HTTP ${res.status}`;
    try {
      message = ((await res.json()) as { message?: string }).message ?? message;
    } catch {
      // not JSON: keep the HTTP status message
    }
    throw new Error(message);
  }
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

export function translate(
  server: Server,
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
  return streamSSE(server, "/api/translate", req, onDelta, signal);
}

export function explain(
  server: Server,
  req: { text: string; translation: string; target_lang: string; explain_lang: string },
  onDelta: (t: string) => void,
) {
  return streamSSE(server, "/api/explain", req, onDelta);
}

export type Health = {
  model: string;
  credentials: boolean;
  invite_required?: boolean;
  invite?: "ok" | "missing" | "invalid" | "disabled" | "limit";
  invite_name?: string;
  invite_message?: string;
  used_today?: number;
  daily_limit?: number;
};

export async function checkHealth(server: Server): Promise<Health> {
  const res = await fetch(`${base(server.url)}/api/health`, { headers: inviteHeader(server.invite) });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return (await res.json()) as Health;
}
