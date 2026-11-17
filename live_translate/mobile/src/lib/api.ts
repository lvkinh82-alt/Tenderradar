// Talks to the Muối Từ translation server (live_translate/server.py), which holds the
// Claude API key. The app never stores the API key itself.
import AsyncStorage from "@react-native-async-storage/async-storage";
import { fetch } from "expo/fetch";

export type ContextPair = { source: string; translation: string };

/** POST JSON and stream Server-Sent Events; calls onDelta for each text chunk. */
const base = (serverUrl: string) => serverUrl.trim().replace(/\/+$/, "");

export type Server = { url: string; invite: string };

// The server allows one device per invite code: sign in once to get a session token and send
// that with every request. Tokens are kept per server + code in AsyncStorage.
const sessionKey = (server: Server) => `ll_session:${base(server.url)}:${server.invite.trim().toUpperCase()}`;
const tokens = new Map<string, string>();

async function storedToken(server: Server): Promise<string | null> {
  const k = sessionKey(server);
  if (tokens.has(k)) return tokens.get(k) ?? null;
  const t = await AsyncStorage.getItem(k);
  if (t) tokens.set(k, t);
  return t;
}

// a random id this phone keeps, so it can always sign back in even if its session was lost
async function deviceId(): Promise<string> {
  let d = await AsyncStorage.getItem("ll_device");
  if (!d) {
    d = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`;
    await AsyncStorage.setItem("ll_device", d);
  }
  return d;
}

async function signIn(server: Server): Promise<string> {
  const k = sessionKey(server);
  const current = await storedToken(server);
  const res = await fetch(`${base(server.url)}/api/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Device": await deviceId(), ...(current ? { "X-Session": current } : {}) },
    body: JSON.stringify({ code: server.invite.trim().toUpperCase() }),
  });
  const data = (await res.json().catch(() => ({}))) as { token?: string; message?: string };
  if (!res.ok || !data.token) throw new Error(data.message ?? `伺服器回應 HTTP ${res.status}`);
  tokens.set(k, data.token);
  await AsyncStorage.setItem(k, data.token);
  return data.token;
}

export async function signOut(server: Server): Promise<void> {
  const k = sessionKey(server);
  const t = await storedToken(server);
  tokens.delete(k);
  await AsyncStorage.removeItem(k);
  if (t) await fetch(`${base(server.url)}/api/logout`, { method: "POST", headers: { "X-Session": t } }).catch(() => {});
}

async function forget(server: Server) {
  const k = sessionKey(server);
  tokens.delete(k);
  await AsyncStorage.removeItem(k);
}

/** fetch with this device's session; signs in when needed and once more if the session ended */
async function authedFetch(server: Server, path: string, init: { method?: string; headers?: Record<string, string>; body?: string; signal?: AbortSignal } = {}) {
  for (let attempt = 0; attempt < 2; attempt++) {
    const token = (await storedToken(server)) ?? (await signIn(server));
    const res = await fetch(`${base(server.url)}${path}`, { ...init, headers: { ...(init.headers ?? {}), "X-Session": token } });
    if (res.status !== 401 || attempt === 1) return res;
    await forget(server); // signed out or taken over: try signing in again (fails clearly if another device has it)
  }
  throw new Error("unreachable");
}

async function streamSSE(
  server: Server,
  path: string,
  payload: unknown,
  onDelta: (text: string) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await authedFetch(server, path, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
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
  const res = await authedFetch(server, "/api/health");
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return (await res.json()) as Health;
}
