# LinguaLive App（iPhone + Android）

用 Expo（React Native）寫的原生 App：手機內建語音辨識 → 你的 LinguaLive 伺服器 → Claude 串流翻譯。

## 功能

- 🎙 **語音**：一句一句即時聆聽、即時翻譯
- 💬 **對話**：A / B 兩人各按自己的按鈕說話，雙向互譯
- ⌨️ **文字**：自動偵測語言
- ✍️ **社群**：用母語寫訊息 → 翻譯後自動複製，直接貼到 IG、TikTok、WhatsApp、Discord
- 🎨 翻譯風格：自然 / 口語 / 社群道地 / 正式 / 商務
- 📖 一鍵解釋俚語、梗、語氣，並提供替代說法
- 🔊 朗讀（手機內建 TTS）、⧉ 複製、📤 系統分享
- 🖥 全螢幕大字幕（會議、簡報用）
- 匯出 TXT 逐字稿 / SRT 字幕、專有名詞表、50 種語言、深色模式

## 架構

```
手機 App ──(語音辨識：iOS Speech / Android SpeechRecognizer)──► 文字
        ──POST /api/translate (SSE 串流)──► live_translate/server.py ──► Claude
```

API 金鑰只放在伺服器，不會打包進 App。

## 1. 啟動翻譯伺服器

```bash
pip install -r live_translate/requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
HOST=0.0.0.0 python -m live_translate.server      # 手機要連，所以用 0.0.0.0
```

在 App 的 ⚙️ 設定 → 翻譯伺服器，填入 `http://電腦的區網IP:8765`，按「測試連線」。
正式發佈請把伺服器部署到雲端並使用 HTTPS（例如 `https://translate.example.com`）。

## 2. 在手機上執行（開發版）

語音辨識是原生模組，**不能用 Expo Go**，要用開發版（development build）：

```bash
cd live_translate/mobile
npm install
npx eas-cli@latest login
npx eas-cli@latest build --profile development --platform android   # 或 ios
# 安裝 build 出來的 App 後：
npx expo start --dev-client
```

有 Mac + Xcode 也可以直接：`npx expo run:ios`；有 Android Studio：`npx expo run:android`。

## 3. 打包給別人安裝 / 上架

| 目的 | 指令 |
|---|---|
| Android APK（直接傳給朋友安裝） | `npx eas-cli@latest build --profile preview --platform android` |
| iPhone 內部測試（TestFlight） | `npx eas-cli@latest build --profile production --platform ios` 然後 `npx eas-cli@latest submit -p ios` |
| 上架 Google Play | `npx eas-cli@latest build --profile production --platform android` 然後 `npx eas-cli@latest submit -p android` |

iPhone 需要 Apple Developer 帳號（每年 US$99）；Google Play 需要開發者帳號（一次 US$25）。

## 開發

```bash
npm run typecheck     # TypeScript
npm run lint          # ESLint
npx expo start --web  # 用瀏覽器預覽介面（語音功能以手機為準）
```

程式結構：

```
src/app/_layout.tsx        導覽（Expo Router）
src/app/index.tsx          主畫面：模式、語言、風格、逐字稿、麥克風
src/app/settings.tsx       伺服器、朗讀、名詞表、匯出
src/app/caption.tsx        全螢幕字幕
src/lib/useRecognizer.ts   逐句語音辨識（自動重新聆聽）
src/lib/store.tsx          狀態、翻譯流程、本機儲存
src/lib/api.ts             SSE 串流呼叫伺服器
```

## 限制

- 沒有「系統鍵盤」：iOS 鍵盤擴充無法用 Expo 製作，請用 ✍️ 社群模式（自動複製後貼上）。
- 翻譯需要網路；語音辨識在多數裝置上也需要網路。
