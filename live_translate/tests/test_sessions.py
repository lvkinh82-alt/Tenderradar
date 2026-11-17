"""Sign-in rules: one device per invite code, sign-out, remember-me is client-side. No network needed.

    python3 live_translate/tests/test_sessions.py
"""
import os, sys, tempfile
os.environ.update({"LIVE_TRANSLATE_DB": os.path.join(tempfile.mkdtemp(), "s.db"), "LIVE_TRANSLATE_ADMIN_TOKEN": "admintok"})
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from types import SimpleNamespace as NS
from fastapi.testclient import TestClient
import live_translate.invites as inv
import live_translate.server as srv

class FakeStream:
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def __iter__(self): return iter([NS(type="text", text="Hello")])
    def get_final_message(self): return NS(stop_reason="end_turn", content=[], usage=NS(input_tokens=1, output_tokens=1, cache_creation_input_tokens=0, cache_read_input_tokens=0, server_tool_use=None))
srv._client = NS(messages=NS(stream=lambda **kw: FakeStream()), beta=NS(messages=NS(stream=lambda **kw: FakeStream())))
c = TestClient(srv.app)
inv.add("Mama", code="TUMUOI-1954"); inv.add("Ming", code="LETAM-1972")
ok = []
def check(name, cond, detail=""):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  ({detail})"))
T = {"text": "你好", "target_lang": "English"}
login = lambda code, tok=None: c.post("/api/login", json={"code": code}, headers={"X-Session": tok} if tok else {})
tr = lambda tok: c.post("/api/translate", json=T, headers={"X-Session": tok})

r = login("nope-0000"); check("wrong code can't sign in", r.status_code == 401 and "不正確" in r.json()["message"])
r = login("tumuoi-1954"); a = r.json().get("token")
check("sign in (any letter case)", r.status_code == 200 and a and r.json()["name"] == "Mama", r.text)
check("signed-in device can translate", tr(a).status_code == 200 and "Hello" in tr(a).text)
check("bare invite code is refused (must sign in)", c.post("/api/translate", json=T, headers={"X-Invite-Code": "TUMUOI-1954"}).status_code == 401)
r = login("TUMUOI-1954"); check("second device refused while the first is in use", r.status_code == 409 and "另一部裝置" in r.json()["message"], r.text)
check("first device still works", tr(a).status_code == 200)
check("same device signing in again keeps its session", login("TUMUOI-1954", a).json().get("token") == a)
check("another code is independent", login("LETAM-1972").status_code == 200)
h = c.get("/api/health", headers={"X-Session": a}).json(); check("health says who is signed in", h["invite"] == "ok" and h["invite_name"] == "Mama", h)

c.post("/api/logout", headers={"X-Session": a})
r = tr(a); check("after sign-out the old session is refused", r.status_code == 401 and r.json()["error"] == "session_ended")
h = c.get("/api/health", headers={"X-Session": a}).json(); check("health tells the old device to sign in again", h["invite"] == "session_ended", h)
r = login("TUMUOI-1954"); b = r.json().get("token"); check("after sign-out another device can sign in", r.status_code == 200 and b)

# idle takeover
inv.db().execute("UPDATE sessions SET last_seen = last_seen - 3600"); inv.db().commit()
r = login("TUMUOI-1954"); d = r.json().get("token"); check("a device idle for over 10 min can be replaced", r.status_code == 200 and d)
check("the idle device is signed out", tr(b).status_code == 401)

# admin force sign-out
r = c.post("/admin/kick", content="token=admintok&code=TUMUOI-1954", headers={"Content-Type": "application/x-www-form-urlencoded"}, follow_redirects=False)
check("admin can force sign-out", r.status_code == 303 and tr(d).status_code == 401)
check("admin page shows devices column", "裝置" in c.get("/admin?token=admintok").text)

# disabling a code signs its device out
e = login("TUMUOI-1954").json()["token"]; inv.set_active("TUMUOI-1954", False)
check("disabled code: device signed out", tr(e).status_code == 401)
check("disabled code can't sign in", login("TUMUOI-1954").status_code == 403)
print(f"\n{sum(ok)}/{len(ok)} passed"); sys.exit(0 if all(ok) else 1)
