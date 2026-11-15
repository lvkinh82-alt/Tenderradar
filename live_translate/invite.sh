#!/bin/bash
# Manage invite codes, e.g.:  ./invite.sh add "阿明" --code TUMUOI-1954   |   ./invite.sh list
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then echo "請先執行 ./setup-mac.sh"; exit 1; fi
cd .. && exec live_translate/.venv/bin/python -m live_translate.invites "$@"
