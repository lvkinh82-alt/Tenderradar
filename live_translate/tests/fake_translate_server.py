# Simulated Claude for two-way translation with realistic latency.
import re, sys, time; import os; sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from types import SimpleNamespace as NS
import uvicorn, live_translate.server as srv
class FakeStream:
    def __init__(self, kw):
        c = kw["messages"][0]["content"]; seg = re.search(r"<segment>\n(.*)\n</segment>", c, re.S).group(1)
        cjk = re.search(r"[一-鿿]", seg)
        self.out = ["@@B\n", f"EN<{seg}>"] if cjk else ["@@A\n", f"中<{seg}>"]
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def __iter__(self):
        for t in self.out: time.sleep(0.35); yield NS(type="text", text=t)
    def get_final_message(self): return NS(stop_reason="end_turn", content=[], usage=NS(input_tokens=1, output_tokens=1, cache_creation_input_tokens=0, cache_read_input_tokens=0, server_tool_use=None))
srv._client = NS(messages=NS(stream=lambda **kw: FakeStream(kw)), beta=NS(messages=NS(stream=lambda **kw: FakeStream(kw))))
uvicorn.run(srv.app, host="127.0.0.1", port=8765, log_level="warning")
