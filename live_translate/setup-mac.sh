#!/bin/bash
# One-time setup on macOS: creates a private Python environment and installs the server's packages.
set -e
cd "$(dirname "$0")"
if ! command -v python3 >/dev/null 2>&1; then
  echo "找不到 python3。請先安裝 Python：https://www.python.org/downloads/ （下載 macOS 版並安裝），然後重新執行這個腳本。"
  exit 1
fi
echo "使用 $(python3 --version)"
python3 -m venv .venv
.venv/bin/pip install --upgrade pip >/dev/null
.venv/bin/pip install -r requirements.txt
echo
echo "✓ 安裝完成。接下來："
echo "  1. 建立邀請碼：  ./invite.sh add \"阿明\" --code TUMUOI-1954"
echo "  2. 啟動伺服器：  ANTHROPIC_API_KEY=你的金鑰 ./start.sh"
