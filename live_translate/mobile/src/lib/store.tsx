import AsyncStorage from "@react-native-async-storage/async-storage";
import * as Clipboard from "expo-clipboard";
import * as Speech from "expo-speech";
import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from "react";
import * as api from "./api";
import { langName, type Style } from "./languages";

export type Speaker = "A" | "B";
export type Segment = {
  id: string;
  t: number;
  speaker: Speaker | null;
  from: string; // BCP-47 or "auto"
  to: string;
  src: string;
  tgt: string;
  state: "pending" | "done" | "error";
  err?: string;
  explanation?: string;
  explaining?: boolean;
  compose?: boolean;
};

export type Settings = {
  serverUrl: string;
  invite: string;
  src: string;
  tgt: string;
  style: Style;
  tts: boolean;
  showSrc: boolean;
  glossary: string;
  captionSize: number;
};

const DEFAULTS: Settings = {
  serverUrl: "http://192.168.1.10:8765",
  invite: "",
  src: "zh-TW",
  tgt: "en-US",
  style: "natural",
  tts: false,
  showSrc: true,
  glossary: "",
  captionSize: 40,
};

type Ctx = {
  ready: boolean;
  settings: Settings;
  update: (patch: Partial<Settings>) => void;
  segments: Segment[];
  add: (
    text: string,
    opts: { speaker: Speaker; from: string; to: string; conversation: boolean; compose: boolean; onCopied?: () => void },
  ) => void;
  retry: (id: string) => void;
  explain: (id: string) => void;
  clear: () => void;
  speak: (text: string, lang: string) => void;
};

const AppContext = createContext<Ctx | null>(null);
const K_SETTINGS = "ll_settings";
const K_SEGMENTS = "ll_segments";

export function AppProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [settings, setSettings] = useState<Settings>(DEFAULTS);
  const [segments, setSegments] = useState<Segment[]>([]);
  // refs give async callbacks the latest values without re-creating them
  const settingsRef = useRef(settings);
  const segmentsRef = useRef(segments);
  useLayoutEffect(() => {
    settingsRef.current = settings;
    segmentsRef.current = segments;
  });

  useEffect(() => {
    (async () => {
      try {
        const [s, g] = await Promise.all([AsyncStorage.getItem(K_SETTINGS), AsyncStorage.getItem(K_SEGMENTS)]);
        if (s) setSettings({ ...DEFAULTS, ...(JSON.parse(s) as Partial<Settings>) });
        if (g) {
          const saved = JSON.parse(g) as Segment[];
          setSegments(saved.map((x) => (x.state === "pending" ? { ...x, state: "error", err: "已中斷，按 ↻ 重新翻譯" } : x)));
        }
      } catch {
        // corrupted storage: start fresh
      }
      setReady(true);
    })();
  }, []);

  useEffect(() => {
    if (ready) AsyncStorage.setItem(K_SETTINGS, JSON.stringify(settings)).catch(() => {});
  }, [settings, ready]);

  useEffect(() => {
    if (!ready || segments.some((s) => s.state === "pending")) return;
    const h = setTimeout(() => {
      AsyncStorage.setItem(K_SEGMENTS, JSON.stringify(segments.slice(-300))).catch(() => {});
    }, 500);
    return () => clearTimeout(h);
  }, [segments, ready]);

  const patch = useCallback((id: string, p: Partial<Segment> | ((s: Segment) => Partial<Segment>)) => {
    setSegments((all) => all.map((s) => (s.id === id ? { ...s, ...(typeof p === "function" ? p(s) : p) } : s)));
  }, []);

  const speak = useCallback((text: string, lang: string) => {
    if (text) Speech.speak(text, { language: lang });
  }, []);

  const run = useCallback(
    async (seg: Segment, onCopied?: () => void) => {
      const st = settingsRef.current;
      const context = segmentsRef.current
        .filter((s) => s.state === "done" && s.id !== seg.id)
        .slice(-6)
        .map((s) => ({ source: s.src, translation: s.tgt }));
      patch(seg.id, { tgt: "", state: "pending", err: undefined, explanation: undefined });
      let out = "";
      try {
        await api.translate(
          { url: st.serverUrl, invite: st.invite },
          {
            text: seg.src,
            source_lang: langName(seg.from),
            target_lang: langName(seg.to),
            context,
            glossary: st.glossary,
            style: st.style,
          },
          (t) => {
            out += t;
            patch(seg.id, { tgt: out });
          },
        );
        patch(seg.id, { state: "done" });
        if (settingsRef.current.tts) speak(out, seg.to);
        if (seg.compose && out) {
          await Clipboard.setStringAsync(out);
          onCopied?.();
        }
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        patch(seg.id, { state: "error", err: `翻譯失敗：${msg}` });
      }
    },
    [patch, speak],
  );

  const add: Ctx["add"] = useCallback(
    (text, o) => {
      const seg: Segment = {
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
        t: Date.now(),
        speaker: o.conversation ? o.speaker : null,
        from: o.from,
        to: o.to,
        src: text,
        tgt: "",
        state: "pending",
        compose: o.compose,
      };
      setSegments((all) => [...all, seg]);
      // segmentsRef must include seg before run() reads it
      segmentsRef.current = [...segmentsRef.current, seg];
      run(seg, o.onCopied);
    },
    [run],
  );

  const retry = useCallback(
    (id: string) => {
      const seg = segmentsRef.current.find((s) => s.id === id);
      if (seg) run(seg);
    },
    [run],
  );

  const explain = useCallback(
    async (id: string) => {
      const seg = segmentsRef.current.find((s) => s.id === id);
      if (!seg || seg.explaining) return;
      if (seg.explanation) {
        patch(id, { explanation: undefined }); // toggle off
        return;
      }
      let out = "";
      patch(id, { explaining: true, explanation: "" });
      try {
        await api.explain(
          { url: settingsRef.current.serverUrl, invite: settingsRef.current.invite },
          {
            text: seg.src,
            translation: seg.tgt,
            target_lang: langName(seg.to),
            explain_lang: langName(settingsRef.current.src),
          },
          (t) => {
            out += t;
            patch(id, { explanation: out });
          },
        );
      } catch (e) {
        patch(id, { explanation: `解釋失敗：${e instanceof Error ? e.message : String(e)}` });
      }
      patch(id, { explaining: false });
    },
    [patch],
  );

  const clear = useCallback(() => {
    Speech.stop();
    setSegments([]);
    AsyncStorage.removeItem(K_SEGMENTS).catch(() => {});
  }, []);

  const update = useCallback((p: Partial<Settings>) => setSettings((s) => ({ ...s, ...p })), []);

  const value = useMemo(
    () => ({ ready, settings, update, segments, add, retry, explain, clear, speak }),
    [ready, settings, update, segments, add, retry, explain, clear, speak],
  );
  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp(): Ctx {
  const c = useContext(AppContext);
  if (!c) throw new Error("useApp must be used inside AppProvider");
  return c;
}
