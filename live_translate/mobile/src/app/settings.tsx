import { File, Paths } from "expo-file-system";
import * as Sharing from "expo-sharing";
import { useState } from "react";
import { Alert, Pressable, ScrollView, StyleSheet, Switch, Text, TextInput, View } from "react-native";
import { checkHealth } from "../lib/api";
import { toSrt, toTxt } from "../lib/exporters";
import { useApp } from "../lib/store";
import { useTheme } from "../lib/theme";

function Row({ label, value, onChange }: { label: string; value: boolean; onChange: (v: boolean) => void }) {
  const c = useTheme();
  return (
    <View style={s.row}>
      <Text style={{ color: c.ink, fontSize: 16 }}>{label}</Text>
      <Switch value={value} onValueChange={onChange} trackColor={{ true: c.accent }} />
    </View>
  );
}

export default function Settings() {
  const c = useTheme();
  const { settings, update, segments, clear } = useApp();
  const [status, setStatus] = useState<string | null>(null);

  const test = async () => {
    setStatus("連線中…");
    try {
      const h = await checkHealth({ url: settings.serverUrl, invite: settings.invite });
      if (!h.credentials) setStatus("⚠️ 已連線，但伺服器沒有設定 ANTHROPIC_API_KEY");
      else if (h.invite_required && h.invite !== "ok") setStatus(`⚠️ ${h.invite_message ?? "邀請碼無法使用"}`);
      else {
        const who = h.invite_name ? `${h.invite_name}，` : "";
        const quota = h.daily_limit ? `（今天已用 ${h.used_today} / ${h.daily_limit} 次）` : "";
        setStatus(`✓ ${who}已連線，可以開始翻譯${quota}`);
      }
    } catch (e) {
      setStatus(`✕ 無法連線：${e instanceof Error ? e.message : String(e)}`);
    }
  };

  const exportFile = async (kind: "txt" | "srt") => {
    if (!segments.length) {
      Alert.alert("沒有內容", "目前沒有可匯出的逐字稿。");
      return;
    }
    const stamp = new Date().toISOString().slice(0, 16).replace(/[:T]/g, "-");
    const file = new File(Paths.cache, `muoitu-${stamp}.${kind}`);
    if (file.exists) file.delete();
    file.create();
    file.write(kind === "txt" ? toTxt(segments) : toSrt(segments));
    await Sharing.shareAsync(file.uri, { mimeType: kind === "txt" ? "text/plain" : "application/x-subrip" });
  };

  return (
    <ScrollView style={{ backgroundColor: c.bg }} contentContainerStyle={{ padding: 16, gap: 18 }}>
      <View style={[s.box, { backgroundColor: c.panel, borderColor: c.line }]}>
        <Text style={[s.h, { color: c.muted }]}>翻譯伺服器</Text>
        <TextInput
          value={settings.serverUrl}
          onChangeText={(v) => update({ serverUrl: v })}
          autoCapitalize="none"
          autoCorrect={false}
          keyboardType="url"
          placeholder="https://your-server.example.com"
          placeholderTextColor={c.muted}
          style={[s.input, { color: c.ink, borderColor: c.line, backgroundColor: c.bg }]}
        />
        <Text style={[s.h, { color: c.muted, marginTop: 14 }]}>邀請碼</Text>
        <TextInput
          value={settings.invite}
          onChangeText={(v) => update({ invite: v.toUpperCase() })}
          autoCapitalize="characters"
          autoCorrect={false}
          placeholder="MT-XXXX-XXXX"
          placeholderTextColor={c.muted}
          style={[s.input, { color: c.ink, borderColor: c.line, backgroundColor: c.bg, letterSpacing: 1 }]}
        />
        <Pressable onPress={test} style={[s.btn, { backgroundColor: c.accent }]}>
          <Text style={{ color: c.accentInk, fontWeight: "700" }}>測試連線</Text>
        </Pressable>
        {status && <Text style={{ color: c.ink, marginTop: 8 }}>{status}</Text>}
        <Text style={[s.hint, { color: c.muted }]}>
          伺服器網址和邀請碼由提供 App 的人給你。（架設者：同一個 Wi-Fi 下可用 http://電腦IP:8765，伺服器要用 HOST=0.0.0.0 啟動；正式使用請部署成 HTTPS。）
        </Text>
      </View>

      <View style={[s.box, { backgroundColor: c.panel, borderColor: c.line }]}>
        <Text style={[s.h, { color: c.muted }]}>顯示與朗讀</Text>
        <Row label="自動朗讀譯文" value={settings.tts} onChange={(v) => update({ tts: v })} />
        <Row label="顯示原文" value={settings.showSrc} onChange={(v) => update({ showSrc: v })} />
      </View>

      <View style={[s.box, { backgroundColor: c.panel, borderColor: c.line }]}>
        <Text style={[s.h, { color: c.muted }]}>專有名詞表</Text>
        <TextInput
          value={settings.glossary}
          onChangeText={(v) => update({ glossary: v })}
          multiline
          placeholder={"一行一條：原文 = 譯文\n例如：招標 = tender"}
          placeholderTextColor={c.muted}
          style={[s.input, { color: c.ink, borderColor: c.line, backgroundColor: c.bg, minHeight: 90, textAlignVertical: "top" }]}
        />
      </View>

      <View style={[s.box, { backgroundColor: c.panel, borderColor: c.line }]}>
        <Text style={[s.h, { color: c.muted }]}>逐字稿（{segments.length} 句）</Text>
        <View style={{ flexDirection: "row", gap: 8 }}>
          <Pressable onPress={() => exportFile("txt")} style={[s.btn2, { borderColor: c.line }]}>
            <Text style={{ color: c.ink }}>匯出 TXT</Text>
          </Pressable>
          <Pressable onPress={() => exportFile("srt")} style={[s.btn2, { borderColor: c.line }]}>
            <Text style={{ color: c.ink }}>匯出 SRT 字幕</Text>
          </Pressable>
        </View>
        <Pressable
          onPress={() =>
            Alert.alert("清除逐字稿？", "所有翻譯紀錄都會刪除。", [
              { text: "取消", style: "cancel" },
              { text: "清除", style: "destructive", onPress: clear },
            ])
          }
          style={[s.btn2, { borderColor: c.danger, marginTop: 8 }]}
        >
          <Text style={{ color: c.danger }}>清除全部</Text>
        </Pressable>
      </View>
    </ScrollView>
  );
}

const s = StyleSheet.create({
  box: { borderWidth: 1, borderRadius: 14, padding: 14 },
  h: { fontSize: 12, fontWeight: "700", marginBottom: 8, letterSpacing: 0.5 },
  input: { borderWidth: 1, borderRadius: 10, padding: 10, fontSize: 15 },
  btn: { marginTop: 10, borderRadius: 10, paddingVertical: 11, alignItems: "center" },
  btn2: { flex: 1, borderWidth: 1, borderRadius: 10, paddingVertical: 11, alignItems: "center" },
  hint: { fontSize: 12, marginTop: 10, lineHeight: 18 },
  row: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", paddingVertical: 8 },
});
