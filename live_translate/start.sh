#!/bin/bash
# Start the Muối Từ translation server (run ./setup-mac.sh once first).
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then echo "請先執行 ./setup-mac.sh"; exit 1; fi
if [ -z "$ANTHROPIC_API_KEY" ]; then echo "請設定 API 金鑰，例如：ANTHROPIC_API_KEY=sk-ant-... ./start.sh"; exit 1; fi
export HOST="${HOST:-0.0.0.0}"   # 0.0.0.0 so phones on the same Wi-Fi can connect
IP=$(ipconfig getifaddr en0 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}')
echo "伺服器啟動中…  電腦本機：http://localhost:${PORT:-8765}   手機（同一個 Wi-Fi）：http://${IP:-電腦IP}:${PORT:-8765}"
cd .. && exec live_translate/.venv/bin/python -m live_translate.server
