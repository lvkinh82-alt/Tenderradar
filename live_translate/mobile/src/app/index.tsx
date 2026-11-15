import { router, Stack } from "expo-router";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { LanguagePicker } from "../components/LanguagePicker";
import { SegmentCard } from "../components/SegmentCard";
import { langLabel, STYLES } from "../lib/languages";
import { useApp, type Segment, type Speaker } from "../lib/store";
import { useTheme } from "../lib/theme";
import { useRecognizer } from "../lib/useRecognizer";

type Mode = "speech" | "convo" | "text" | "compose";
const MODES: { value: Mode; label: string }[] = [
  { value: "speech", label: "🎙 語音" },
  { value: "convo", label: "💬 對話" },
  { value: "text", label: "⌨️ 文字" },
  { value: "compose", label: "✍️ 社群" },
];

export default function Home() {
  const c = useTheme();
  const insets = useSafeAreaInsets();
  const app = useApp();
  const { settings, update, segments } = app;
  const [mode, setMode] = useState<Mode>("speech");
  const [text, setText] = useState("");
  const [toast, setToast] = useState<string | null>(null);
  const listRef = useRef<FlatList<Segment>>(null);

  const showToast = useCallback((m: string) => {
    setToast(m);
    setTimeout(() => setToast(null), 2000);
  }, []);

  const rec = useRecognizer((sentence, tag) => {
    const speaker = tag as Speaker;
    const isB = speaker === "B";
    app.add(sentence, {
      speaker,
      from: isB ? settings.tgt : settings.src,
      to: isB ? settings.src : settings.tgt,
      conversation: mode === "convo",
      compose: false,
    });
  });

  // stop the mic when leaving a voice mode
  useEffect(() => {
    if (mode !== "speech" && mode !== "convo") rec.stop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode]);

  // newest sentence first, so it is always visible without scrolling
  const newestFirst = useMemo(() => [...segments].reverse(), [segments]);
  const last = segments[segments.length - 1];
  useEffect(() => {
    if (segments.length) requestAnimationFrame(() => listRef.current?.scrollToOffset({ offset: 0, animated: true }));
  }, [segments.length, last?.tgt]);

  const sendText = () => {
    const t = text.trim();
    if (!t) return;
    setText("");
    app.add(t, {
      speaker: "A",
      from: mode === "text" ? "auto" : settings.src,
      to: settings.tgt,
      conversation: false,
      compose: mode === "compose",
      onCopied: () => showToast("✓ 已複製譯文，直接貼到聊天或貼文即可"),
    });
  };

  const toggleMic = (tag: Speaker) => {
    if (rec.listening && rec.tag === tag) rec.stop();
    else rec.start(tag === "B" ? settings.tgt : settings.src, tag);
  };

  const swap = () => {
    update({ src: settings.tgt, tgt: settings.src });
    if (rec.listening) rec.stop();
  };

  if (!app.ready) {
    return (
      <View style={[s.center, { backgroundColor: c.bg }]}>
        <ActivityIndicator color={c.accent} />
      </View>
    );
  }

  const isConvo = mode === "convo";
  return (
    <KeyboardAvoidingView
      style={{ flex: 1, backgroundColor: c.bg }}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
      keyboardVerticalOffset={Platform.OS === "ios" ? 100 : 0}
    >
      <Stack.Screen
        options={{
          headerRight: () => (
            <View style={{ flexDirection: "row", gap: 18 }}>
              <Pressable accessibilityLabel="全螢幕字幕" hitSlop={10} onPress={() => router.push("/caption")}>
                <Text style={{ fontSize: 20 }}>🖥</Text>
              </Pressable>
              <Pressable accessibilityLabel="設定" hitSlop={10} onPress={() => router.push("/settings")}>
                <Text style={{ fontSize: 20 }}>⚙️</Text>
              </Pressable>
            </View>
          ),
        }}
      />

      {!settings.invite.trim() && (
        <Pressable
          onPress={() => router.push("/settings")}
          style={[s.banner, { backgroundColor: c.chip, borderColor: c.accent }]}
          accessibilityRole="button"
        >
          <Text style={{ color: c.ink, fontWeight: "600" }}>🔑 請先輸入邀請碼才能開始翻譯</Text>
          <Text style={{ color: c.accent, fontWeight: "700" }}>前往設定 ›</Text>
        </Pressable>
      )}

      {/* mode switch */}
      <View style={[s.seg, { backgroundColor: c.chip }]}>
        {MODES.map((m) => (
          <Pressable
            key={m.value}
            onPress={() => setMode(m.value)}
            style={[s.segBtn, mode === m.value && { backgroundColor: c.panel }]}
            accessibilityRole="tab"
            accessibilityState={{ selected: mode === m.value }}
          >
            <Text style={{ color: mode === m.value ? c.accent : c.muted, fontWeight: mode === m.value ? "700" : "500", fontSize: 13 }}>
              {m.label}
            </Text>
          </Pressable>
        ))}
      </View>

      {/* languages */}
      <View style={s.langRow}>
        <LanguagePicker
          caption={isConvo ? "A 的語言" : mode === "text" ? "我的語言" : "來源語言"}
          value={settings.src}
          onChange={(v) => update({ src: v })}
          color={isConvo ? c.a : undefined}
        />
        <Pressable onPress={swap} accessibilityLabel="交換語言" style={[s.swap, { borderColor: c.line, backgroundColor: c.panel }]}>
          <Text style={{ color: c.ink, fontSize: 18 }}>⇄</Text>
        </Pressable>
        <LanguagePicker
          caption={isConvo ? "B 的語言" : "目標語言"}
          value={settings.tgt}
          onChange={(v) => update({ tgt: v })}
          color={isConvo ? c.b : undefined}
        />
      </View>

      {/* style chips */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={s.chips} style={{ flexGrow: 0 }}>
        {STYLES.map((st) => {
          const on = settings.style === st.value;
          return (
            <Pressable
              key={st.value}
              onPress={() => update({ style: st.value })}
              style={[s.chip, { backgroundColor: on ? c.accent : c.chip }]}
            >
              <Text style={{ color: on ? c.accentInk : c.ink, fontSize: 13, fontWeight: on ? "700" : "500" }}>{st.label}</Text>
            </Pressable>
          );
        })}
      </ScrollView>

      {!!rec.interim && (
        <Text style={[s.interim, { color: c.muted }]} numberOfLines={2}>
          {rec.interim}
        </Text>
      )}
      {!!rec.error && <Text style={[s.interim, { color: c.danger }]}>{rec.error}</Text>}

      {/* transcript, newest on top */}
      <FlatList
        ref={listRef}
        data={newestFirst}
        keyExtractor={(x) => x.id}
        style={{ flex: 1 }}
        contentContainerStyle={{ padding: 12, flexGrow: 1 }}
        renderItem={({ item }) => (
          <SegmentCard
            seg={item}
            showSrc={settings.showSrc}
            onSpeak={(x) => app.speak(x.tgt, x.to)}
            onRetry={app.retry}
            onExplain={app.explain}
            onCopied={() => showToast("✓ 已複製")}
          />
        )}
        ListEmptyComponent={
          <View style={s.empty}>
            <Text style={{ color: c.muted, textAlign: "center", lineHeight: 22 }}>
              {mode === "speech" && "按下麥克風開始說話，\n每說完一句就會即時翻譯。"}
              {mode === "convo" && "兩個人輪流按自己的按鈕說話，\nMuối Từ 會雙向翻譯。"}
              {mode === "text" && "輸入任何語言的文字，\n自動偵測並翻譯。"}
              {mode === "compose" && "用你的語言寫訊息或貼文，\n翻譯好會自動複製，直接貼到 IG、TikTok、WhatsApp。"}
            </Text>
          </View>
        }
      />

      {/* bottom controls */}
      <View style={[s.bottom, { paddingBottom: Math.max(insets.bottom, 12), backgroundColor: c.panel, borderColor: c.line }]}>
        {mode === "speech" && (
          <Pressable
            onPress={() => toggleMic("A")}
            accessibilityLabel={rec.listening ? "停止聆聽" : "開始聆聽"}
            style={[s.mic, { backgroundColor: rec.listening ? c.danger : c.accent }]}
          >
            <Text style={s.micText}>{rec.listening ? "■  停止聆聽" : "🎙  開始聆聽"}</Text>
          </Pressable>
        )}
        {isConvo && (
          <View style={{ flexDirection: "row", gap: 10 }}>
            {(["A", "B"] as const).map((sp) => {
              const on = rec.listening && rec.tag === sp;
              const col = sp === "A" ? c.a : c.b;
              return (
                <Pressable
                  key={sp}
                  onPress={() => toggleMic(sp)}
                  style={[s.talk, { borderColor: col, backgroundColor: on ? col : "transparent" }]}
                >
                  <Text style={{ color: on ? "#fff" : col, fontWeight: "700", fontSize: 16 }}>
                    {on ? "■ 停止" : `🎙 ${sp}`}
                  </Text>
                  <Text style={{ color: on ? "#fff" : col, fontSize: 12, marginTop: 2 }} numberOfLines={1}>
                    {langLabel(sp === "A" ? settings.src : settings.tgt)}
                  </Text>
                </Pressable>
              );
            })}
          </View>
        )}
        {(mode === "text" || mode === "compose") && (
          <View style={{ flexDirection: "row", gap: 8, alignItems: "flex-end" }}>
            <TextInput
              value={text}
              onChangeText={setText}
              multiline
              placeholder={mode === "compose" ? "寫下要發的訊息…" : "輸入要翻譯的文字…"}
              placeholderTextColor={c.muted}
              style={[s.input, { color: c.ink, backgroundColor: c.bg, borderColor: c.line }]}
            />
            <Pressable onPress={sendText} style={[s.send, { backgroundColor: c.accent }]} accessibilityLabel="翻譯">
              <Text style={{ color: c.accentInk, fontWeight: "700" }}>翻譯</Text>
            </Pressable>
          </View>
        )}
      </View>

      {toast && (
        <View pointerEvents="none" style={[s.toast, { backgroundColor: c.ink, bottom: insets.bottom + 110 }]}>
          <Text style={{ color: c.bg }}>{toast}</Text>
        </View>
      )}
    </KeyboardAvoidingView>
  );
}

const s = StyleSheet.create({
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  banner: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginHorizontal: 12, marginTop: 12, padding: 12, borderRadius: 12, borderWidth: 1 },
  seg: { flexDirection: "row", margin: 12, marginBottom: 8, padding: 4, borderRadius: 12 },
  segBtn: { flex: 1, alignItems: "center", paddingVertical: 8, borderRadius: 9 },
  langRow: { flexDirection: "row", alignItems: "center", gap: 8, paddingHorizontal: 12 },
  swap: { width: 40, height: 40, borderRadius: 20, borderWidth: 1, alignItems: "center", justifyContent: "center" },
  chips: { gap: 8, paddingHorizontal: 12, paddingVertical: 10 },
  chip: { paddingHorizontal: 14, paddingVertical: 7, borderRadius: 16 },
  empty: { flex: 1, alignItems: "center", justifyContent: "center", padding: 32 },
  interim: { paddingHorizontal: 16, paddingTop: 4, paddingBottom: 2, fontStyle: "italic" },
  bottom: { paddingHorizontal: 12, paddingTop: 12, borderTopWidth: StyleSheet.hairlineWidth },
  mic: { borderRadius: 16, paddingVertical: 16, alignItems: "center" },
  micText: { color: "#fff", fontSize: 17, fontWeight: "700" },
  talk: { flex: 1, borderWidth: 2, borderRadius: 16, paddingVertical: 12, alignItems: "center" },
  input: { flex: 1, minHeight: 44, maxHeight: 120, borderWidth: 1, borderRadius: 12, paddingHorizontal: 12, paddingVertical: 10, fontSize: 16 },
  send: { height: 44, paddingHorizontal: 18, borderRadius: 12, alignItems: "center", justifyContent: "center" },
  toast: { position: "absolute", alignSelf: "center", paddingHorizontal: 16, paddingVertical: 10, borderRadius: 10, opacity: 0.95 },
});
