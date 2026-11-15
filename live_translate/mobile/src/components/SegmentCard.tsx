import * as Clipboard from "expo-clipboard";
import { memo } from "react";
import { ActivityIndicator, Pressable, Share, StyleSheet, Text, View } from "react-native";
import { langLabel } from "../lib/languages";
import type { Segment } from "../lib/store";
import { useTheme } from "../lib/theme";

type Props = {
  seg: Segment;
  showSrc: boolean;
  onSpeak: (s: Segment) => void;
  onRetry: (id: string) => void;
  onExplain: (id: string) => void;
  onCopied: () => void;
};

function Act({ label, a11y, onPress }: { label: string; a11y: string; onPress: () => void }) {
  const c = useTheme();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={a11y}
      onPress={onPress}
      hitSlop={6}
      style={({ pressed }) => [s.act, { borderColor: c.line, opacity: pressed ? 0.5 : 1 }]}
    >
      <Text style={{ fontSize: 15 }}>{label}</Text>
    </Pressable>
  );
}

function SegmentCardImpl({ seg, showSrc, onSpeak, onRetry, onExplain, onCopied }: Props) {
  const c = useTheme();
  const side = seg.speaker === "A" ? c.a : seg.speaker === "B" ? c.b : c.line;
  const time = new Date(seg.t).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

  return (
    <View style={[s.card, { backgroundColor: c.panel, borderColor: c.line, borderLeftColor: side }]}>
      <Text style={[s.meta, { color: c.muted }]}>
        {seg.speaker ? `${seg.speaker} · ` : ""}
        {langLabel(seg.from)} → {langLabel(seg.to)} · {time}
      </Text>
      {showSrc && <Text style={[s.src, { color: c.muted }]}>{seg.src}</Text>}
      {seg.state === "error" ? (
        <Text style={[s.err, { color: c.danger }]}>{seg.err}</Text>
      ) : (
        <Text style={[s.tgt, { color: c.ink }]} selectable>
          {seg.tgt}
          {seg.state === "pending" && <Text style={{ color: c.accent }}> ▍</Text>}
        </Text>
      )}
      {seg.explanation !== undefined && (
        <View style={[s.explain, { borderColor: c.line, backgroundColor: c.bg }]}>
          {seg.explaining && !seg.explanation ? (
            <ActivityIndicator color={c.accent} />
          ) : (
            <Text style={{ color: c.ink, fontSize: 14, lineHeight: 21 }}>{seg.explanation}</Text>
          )}
        </View>
      )}
      {seg.state !== "pending" && (
        <View style={s.acts}>
          {seg.state === "done" && (
            <>
              <Act label="🔊" a11y="朗讀" onPress={() => onSpeak(seg)} />
              <Act
                label="⧉"
                a11y="複製"
                onPress={async () => {
                  await Clipboard.setStringAsync(seg.tgt);
                  onCopied();
                }}
              />
              <Act label="📤" a11y="分享" onPress={() => Share.share({ message: seg.tgt }).catch(() => {})} />
              <Act label="📖" a11y="解釋俚語與語氣" onPress={() => onExplain(seg.id)} />
            </>
          )}
          <Act label="↻" a11y="重新翻譯" onPress={() => onRetry(seg.id)} />
        </View>
      )}
    </View>
  );
}

export const SegmentCard = memo(SegmentCardImpl);

const s = StyleSheet.create({
  card: { borderWidth: 1, borderLeftWidth: 4, borderRadius: 14, padding: 14, marginBottom: 10 },
  meta: { fontSize: 12 },
  src: { fontSize: 15, marginTop: 6 },
  tgt: { fontSize: 19, fontWeight: "500", marginTop: 6, lineHeight: 27 },
  err: { fontSize: 14, marginTop: 6 },
  explain: { marginTop: 10, padding: 10, borderRadius: 10, borderWidth: 1, borderStyle: "dashed" },
  acts: { flexDirection: "row", justifyContent: "flex-end", gap: 6, marginTop: 10 },
  act: { borderWidth: 1, borderRadius: 8, paddingHorizontal: 10, paddingVertical: 4 },
});
