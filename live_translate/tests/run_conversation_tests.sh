#!/bin/bash
# Browser tests for the "two-person conversation" screen, run against the real server with a
# simulated Claude (no API key or cost). Needs Node with Playwright and the server's Python packages.
#   live_translate/tests/run_conversation_tests.sh
set -u
cd "$(dirname "$0")"
LIVE_TRANSLATE_REQUIRE_INVITE=0 ANTHROPIC_API_KEY=test python3 fake_translate_server.py > /dev/null 2>&1 &
SERVER=$!; trap 'kill $SERVER 2>/dev/null' EXIT; sleep 3
fail=0
# every combination of: final text only after stop (iPhone) / a read-aloud that never reports its end / the other person starting early
for F in 0 1; do for D in 0 1 2 4; do for E in 0 1; do
  out=$(FINAL_AFTER_STOP=$F DROP_TTS_END=$D EARLY_B=$E node conversation_rounds.test.js 2>&1); echo "$out" | head -1
  echo "$out" | grep -q PASS || fail=1
done; done; done
out=$(node conversation_edge_cases.test.js 2>&1); echo "$out"
echo "$out" | grep -q "false\|errors \[$" && { echo "$out" | grep -q "errors \[\]" || fail=1; echo "$out" | grep -q ": false" && fail=1; }
[ $fail = 0 ] && echo "ALL CONVERSATION TESTS PASSED" || { echo "SOME TESTS FAILED"; exit 1; }
