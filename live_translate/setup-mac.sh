#!/bin/bash
# One-time setup on macOS: creates a private Python environment and installs the server's packages.
# Needs Python 3.10 or newer (the python3 that ships with macOS is often 3.9, which is too old).
cd "$(dirname "$0")"

new_enough() { "$1" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; }

PY=""
for cand in python3.14 python3.13 python3.12 python3.11 python3.10 \
            /Library/Frameworks/Python.framework/Versions/Current/bin/python3 \
            /opt/homebrew/bin/python3 /usr/local/bin/python3 python3; do
  if command -v "$cand" >/dev/null 2>&1 && new_enough "$cand"; then PY="$(command -v "$cand")"; break; fi
done

if [ -z "$PY" ]; then
  echo "✕ 找不到 Python 3.10 以上的版本。"
  command -v python3 >/dev/null 2>&1 && echo "  目前的 python3 是 $(python3 --version 2>&1)，太舊了。"
  echo
  echo "請這樣做："
  echo "  1. 打開 https://www.python.org/downloads/ ，按黃色的「Download Python 3.x」按鈕，安裝下載的 .pkg 檔。"
  echo "  2. 安裝完後，關掉這個終端機視窗，開一個新的。"
  echo "  3. 回到這個資料夾，再執行一次 ./setup-mac.sh"
  exit 1
fi
echo "使用 $("$PY" --version)（$PY）"

# A .venv made earlier with an old Python can't run the server: rebuild it.
if [ -x .venv/bin/python ] && ! new_enough .venv/bin/python; then
  echo "移除先前用舊版 Python 建立的環境…"
  rm -rf .venv
fi
[ -x .venv/bin/python ] || "$PY" -m venv .venv || { echo "✕ 建立環境失敗"; exit 1; }

.venv/bin/pip install --upgrade pip >/dev/null
if ! .venv/bin/pip install -r requirements.txt; then
  echo "✕ 安裝套件失敗，請把上面的錯誤訊息貼給 Claude。"
  exit 1
fi
echo
echo "✓ 安裝完成。接下來："
echo "  1. 建立邀請碼：  ./invite.sh add \"阿明\" --code TUMUOI-1954"
echo "  2. 啟動伺服器：  ANTHROPIC_API_KEY=你的金鑰 ./start.sh"
