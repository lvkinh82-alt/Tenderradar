import { router } from "expo-router";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useApp } from "../lib/store";

function Btn({ label, onPress }: { label: string; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} style={s.btn} hitSlop={8} accessibilityRole="button">
      <Text style={s.btnText}>{label}</Text>
    </Pressable>
  );
}

// Full-screen subtitles for presentations / meetings: latest sentence, big text.
export default function Caption() {
  const insets = useSafeAreaInsets();
  const { segments, settings, update } = useApp();
  const last = segments[segments.length - 1];
  const size = settings.captionSize;

  return (
    <View style={[s.root, { paddingTop: insets.top + 8, paddingBottom: insets.bottom + 24 }]}>
      <View style={s.bar}>
        <Btn label="A−" onPress={() => update({ captionSize: Math.max(20, size - 4) })} />
        <Btn label="A+" onPress={() => update({ captionSize: Math.min(80, size + 4) })} />
        <View style={{ flex: 1 }} />
        <Btn label="✕ 關閉" onPress={() => router.back()} />
      </View>
      <View style={{ flex: 1, justifyContent: "flex-end" }}>
        {settings.showSrc && !!last?.src && <Text style={s.src}>{last.src}</Text>}
        <Text style={[s.tgt, { fontSize: size, lineHeight: size * 1.3 }]} adjustsFontSizeToFit>
          {last ? last.tgt || "…" : "等待語音…（回到主畫面開始聆聽）"}
        </Text>
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: "#000", paddingHorizontal: 24 },
  bar: { flexDirection: "row", gap: 8 },
  btn: { backgroundColor: "#222", borderRadius: 8, paddingHorizontal: 12, paddingVertical: 8 },
  btnText: { color: "#fff", fontSize: 15 },
  src: { color: "#9aa1b2", fontSize: 20, marginBottom: 12 },
  tgt: { color: "#fff", fontWeight: "700" },
});
