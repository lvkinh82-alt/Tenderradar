import { useMemo, useState } from "react";
import { FlatList, Modal, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { LANGS, langLabel } from "../lib/languages";
import { useTheme } from "../lib/theme";

type Props = { caption: string; value: string; onChange: (code: string) => void; color?: string };

export function LanguagePicker({ caption, value, onChange, color }: Props) {
  const c = useTheme();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const list = useMemo(() => {
    const k = q.trim().toLowerCase();
    return k ? LANGS.filter((l) => (l[0] + l[1] + l[2]).toLowerCase().includes(k)) : LANGS;
  }, [q]);

  return (
    <>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`${caption}：${langLabel(value)}`}
        onPress={() => setOpen(true)}
        style={[s.btn, { backgroundColor: c.panel, borderColor: color ?? c.line }]}
      >
        <Text style={[s.cap, { color: color ?? c.muted }]}>{caption}</Text>
        <Text style={[s.val, { color: c.ink }]} numberOfLines={1}>
          {langLabel(value)} ▾
        </Text>
      </Pressable>
      <Modal visible={open} animationType="slide" presentationStyle="pageSheet" onRequestClose={() => setOpen(false)}>
        <SafeAreaView style={{ flex: 1, backgroundColor: c.bg }}>
          <View style={s.head}>
            <Text style={[s.title, { color: c.ink }]}>{caption}</Text>
            <Pressable onPress={() => setOpen(false)} hitSlop={12}>
              <Text style={{ color: c.accent, fontSize: 16 }}>完成</Text>
            </Pressable>
          </View>
          <TextInput
            value={q}
            onChangeText={setQ}
            placeholder="搜尋語言 / Search"
            placeholderTextColor={c.muted}
            style={[s.search, { backgroundColor: c.panel, color: c.ink, borderColor: c.line }]}
          />
          <FlatList
            data={list}
            keyExtractor={(l) => l[0]}
            renderItem={({ item }) => (
              <Pressable
                onPress={() => {
                  onChange(item[0]);
                  setOpen(false);
                  setQ("");
                }}
                style={[s.row, { borderColor: c.line }]}
              >
                <Text style={{ color: c.ink, fontSize: 16 }}>{item[1]}</Text>
                <Text style={{ color: c.muted }}>{item[0] === value ? "✓" : item[2]}</Text>
              </Pressable>
            )}
          />
        </SafeAreaView>
      </Modal>
    </>
  );
}

const s = StyleSheet.create({
  btn: { flex: 1, borderWidth: 1, borderRadius: 12, paddingVertical: 8, paddingHorizontal: 12 },
  cap: { fontSize: 11, fontWeight: "600" },
  val: { fontSize: 15, fontWeight: "600", marginTop: 2 },
  head: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", padding: 16 },
  title: { fontSize: 18, fontWeight: "700" },
  search: { marginHorizontal: 16, marginBottom: 8, borderWidth: 1, borderRadius: 10, padding: 10, fontSize: 16 },
  row: { flexDirection: "row", justifyContent: "space-between", paddingHorizontal: 20, paddingVertical: 14, borderBottomWidth: StyleSheet.hairlineWidth },
});
