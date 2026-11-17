# Muối Từ · Phiên Dịch AI（即時 AI 翻譯）

瀏覽器即時語音辨識 + Claude 串流翻譯的即時口譯工具。

## 功能

| 功能 | 說明 |
|---|---|
| 🎙 演講字幕 | 連續聆聽，每句話說完後立即串流翻譯 |
| 💬 雙人對話 | A / B 兩人各用自己的語言輪流說話，雙向互譯 |
| ⌨️ 文字翻譯 | 輸入文字（自動偵測語言） |
| 🔎 問 AI（會上網查） | 開口問或打字問；需要最新資訊（天氣、新聞、價格、營業時間…）時 AI 會自己上網搜尋，回答會唸出來並附上資料來源 |
| 🌐 中英雙語介面 | 所有文字、按鈕、提示都有中文和英文；設定裡可選「雙語 / 只中文 / 只英文」 |
| 📹 視訊助手 | 打開鏡頭，開口問（或打字問）；AI 看當下畫面回答，並一句一句即時唸出來（可關閉），畫面上的外文也會翻譯。回答疊在鏡頭畫面上 |
| 🔗 讀網址 | 「拍給 AI 看」與「問 AI」可以讀網頁：貼上網址，或上傳印有網址的照片（AI 會先讀出圖上的網址），AI 會打開那個網頁再回答，並列出來源 |
| 🖼 上傳圖片 | 在視訊助手裡從相簿選圖或拍照：自動說明並翻譯圖上文字，之後可針對同一張圖繼續追問 |
| ✍️ 社群輸入 | 用母語寫訊息 / 貼文 → 翻譯後自動複製，直接貼到 IG、TikTok、X、WhatsApp、Discord |
| 🎨 翻譯風格 | 自然 / 輕鬆口語 / 社群道地（網路流行語）/ 正式 / 商務 |
| 📖 俚語解釋 | 每句可一鍵解釋俚語、梗、語氣與文化背景，並提供替代說法 |
| 📤 分享 | 手機上直接呼叫系統分享選單 |
| 📲 安裝成 App | PWA：可「加入主畫面」，像原生 App 一樣全螢幕開啟 |
| 🖥 全螢幕字幕 | 黑底大字幕，可調整字級，適合投影或會議 |
| 🔊 TTS 朗讀 | 自動或手動朗讀譯文 |
| 📖 專有名詞表 | 指定固定譯法，維持術語一致 |
| 🧠 上下文 | 參考最近 6 句譯文，讓代名詞、術語前後一致 |
| ⬇ 匯出 | TXT 逐字稿 / SRT 字幕檔 |
| 50 種語言 | 繁中、粵語、簡中、英、越、日、韓、泰、高棉、寮、緬甸、印尼、馬來、菲、印地、法、德、西、葡、義、俄、阿拉伯、希伯來、土耳其、斯瓦希里、沃洛夫… |

## 架構

```
麥克風 → Web Speech API（瀏覽器語音辨識）→ 每句定稿文字
      → POST /api/translate → FastAPI → Claude（串流）→ SSE → 即時顯示 / TTS
句子 + 譯文 → POST /api/explain → Claude → 俚語 / 語氣解釋
```

## 部署到 Railway（24 小時在線、固定網址）

請看 [RAILWAY.md](RAILWAY.md)。邀請碼在 Railway 的 Variables 用 `LIVE_TRANSLATE_INVITES=Mama:TUMUOI-1954, 阿明:TUMUOI-2024:200` 管理，用量在 `/admin?token=管理密碼` 查看。

## Mac 快速開始（最簡單）

在「終端機」裡執行（一行一行貼上，**不要貼 `#` 後面的說明文字**）：

```bash
cd ~/Downloads/live_translate
./setup-mac.sh
./invite.sh add "阿明" --code TUMUOI-1954
ANTHROPIC_API_KEY=sk-ant-你的金鑰 ./start.sh
```

- `cd` 那一行請換成你解壓縮 `live_translate` 資料夾的位置（可以打 `cd ` 加一個空格，再把資料夾拖進終端機視窗）。
- Mac 上的指令是 `python3`，不是 `python`；用上面的腳本就不用管這件事。
- 如果 `./setup-mac.sh` 說找不到 python3，先到 https://www.python.org/downloads/ 安裝。
- 之後每次要用，只要執行最後一行 `./start.sh`；管理邀請碼用 `./invite.sh list`、`./invite.sh disable 碼`。

## 啟動（手動）

```bash
pip3 install -r live_translate/requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python3 -m live_translate.invites add "我自己"   # 先建立一個邀請碼
python3 -m live_translate.server
# 開啟 http://localhost:8765 （請用 Chrome / Edge / Safari）
```

## 邀請碼（只給親友使用，費用由你負擔）

所有翻譯都要有效的邀請碼，伺服器才會呼叫 Claude；沒有碼的人就算知道網址也用不了你的 API 額度。

```bash
python3 -m live_translate.invites add "阿明"                  # 建立邀請碼（不限次數）
python3 -m live_translate.invites add "小美" --daily-limit 300  # 每天最多 300 次
python3 -m live_translate.invites add "阿明" --code TUMUOI-1954  # 自己指定邀請碼
python3 -m live_translate.invites list                          # 每個碼的用量與估計費用
python3 -m live_translate.invites disable MT-XXXX-XXXX          # 停用（例如手機遺失）
python3 -m live_translate.invites enable  MT-XXXX-XXXX          # 重新啟用
python3 -m live_translate.invites limit   MT-XXXX-XXXX 500      # 修改每日上限（0 = 不限）
python3 -m live_translate.invites delete  MT-XXXX-XXXX          # 刪除
```

- 朋友在網頁版左側「邀請碼」欄位，或 App 的「⚙️ 設定 → 邀請碼」輸入一次即可，之後會記住。
- 邀請碼存在 `live_translate/data/invites.db`（不會進 Git）。伺服器失敗的請求不會扣次數。
- 建議另外在 Anthropic Console 設定每月花費上限。
- 純自己本機使用、不想要邀請碼：`LIVE_TRANSLATE_REQUIRE_INVITE=0`。

環境變數：

| 變數 | 預設 | 說明 |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | 必填 |
| `LIVE_TRANSLATE_MODEL` | `claude-opus-5-5` | 翻譯模型；省錢可用 `claude-haiku-5-5`（約便宜 40 倍），折衷可用 `claude-sonnet-5-5` |
| `LIVE_TRANSLATE_EFFORT` | `low` | `low` 最快；`medium`/`high` 品質更高但較慢 |
| `HOST` / `PORT` | `127.0.0.1` / `8765` | 伺服器位址 |
| `LIVE_TRANSLATE_REQUIRE_INVITE` | `1` | `0` = 不檢查邀請碼 |
| `LIVE_TRANSLATE_DB` | `live_translate/data/invites.db` | 邀請碼資料庫位置 |
| `LIVE_TRANSLATE_INVITES` | — | 用變數管理邀請碼：`名字:碼[:每日上限]`，逗號分隔；沒列出的碼會停用 |
| `LIVE_TRANSLATE_WEB_SEARCH` | `1` | `0` = 關閉 AI 上網搜尋（問 AI、拍給 AI 看） |
| `LIVE_TRANSLATE_PRICE_SEARCH` | `0.01` | 估計費用用的每次搜尋單價（美元） |
| `LIVE_TRANSLATE_ADMIN_TOKEN` | — | 設定後可開 `/admin?token=…` 看用量 |
| `LIVE_TRANSLATE_PRICE_IN` / `_OUT` | 依模型自動 | 估計費用用的單價（美元 / 百萬 token） |

> 麥克風需要 HTTPS 或 `localhost`。要讓手機在區網使用，請放在 HTTPS 反向代理之後。
> 伺服器端啟用了 Claude 的 server-side fallback：模型拒絕某段內容時自動改由備援模型翻譯。

### 與原生翻譯 App 的差異

- 手機原生 App（iPhone + Android）在 [`mobile/`](mobile/README.md)，網頁版與 App 共用同一個伺服器。
- 網頁版不能做成「系統鍵盤」；改用「✍️ 社群」模式：寫好 → 自動複製 → 貼上。
- 翻譯需要網路（由 Claude 處理），沒有離線翻譯；介面本身可離線開啟。
