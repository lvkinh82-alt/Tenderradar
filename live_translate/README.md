# LinguaLive · 即時 AI 翻譯

瀏覽器即時語音辨識 + Claude 串流翻譯的即時口譯工具。

## 功能

| 功能 | 說明 |
|---|---|
| 🎙 演講字幕 | 連續聆聽，每句話說完後立即串流翻譯 |
| 💬 雙人對話 | A / B 兩人各用自己的語言輪流說話，雙向互譯 |
| ⌨️ 文字翻譯 | 輸入文字（自動偵測語言） |
| 🖥 全螢幕字幕 | 黑底大字幕，可調整字級，適合投影或會議 |
| 🔊 TTS 朗讀 | 自動或手動朗讀譯文 |
| 📖 專有名詞表 | 指定固定譯法，維持術語一致 |
| 🧠 上下文 | 參考最近 6 句譯文，讓代名詞、術語前後一致 |
| ⬇ 匯出 | TXT 逐字稿 / SRT 字幕檔 |
| 21 種語言 | 繁中、粵語、簡中、英、越、日、韓、泰、印尼、馬來、菲、印地、法、德、西、葡、義、俄、阿、土 |

## 架構

```
麥克風 → Web Speech API（瀏覽器語音辨識）→ 每句定稿文字
      → POST /api/translate → FastAPI → Claude（串流）→ SSE → 即時顯示 / TTS
```

## 啟動

```bash
pip install -r live_translate/requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python -m live_translate.server
# 開啟 http://localhost:8765 （請用 Chrome / Edge / Safari）
```

環境變數：

| 變數 | 預設 | 說明 |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | 必填 |
| `LIVE_TRANSLATE_MODEL` | `claude-opus-5-5` | 翻譯模型 |
| `LIVE_TRANSLATE_EFFORT` | `low` | `low` 最快；`medium`/`high` 品質更高但較慢 |
| `HOST` / `PORT` | `127.0.0.1` / `8765` | 伺服器位址 |

> 麥克風需要 HTTPS 或 `localhost`。要讓手機在區網使用，請放在 HTTPS 反向代理之後。
> 伺服器端啟用了 Claude 的 server-side fallback：模型拒絕某段內容時自動改由備援模型翻譯。
