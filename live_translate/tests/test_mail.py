"""End-to-end checks of the read-only Gmail feature against a fake Google (no network, no API key).

    python3 live_translate/tests/test_mail.py
"""

import base64
import email
import email.policy
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from types import SimpleNamespace as NS

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
PORT = 8799
G = f"http://127.0.0.1:{PORT}"
os.environ.update({
    "GOOGLE_CLIENT_ID": "test-client", "GOOGLE_CLIENT_SECRET": "test-secret",
    "GOOGLE_AUTH_URL": G + "/auth", "GOOGLE_TOKEN_URL": G + "/token", "GOOGLE_REVOKE_URL": G + "/revoke",
    "GMAIL_API_BASE": G + "/gmail/v1", "PUBLIC_BASE_URL": "http://testserver",
    "LIVE_TRANSLATE_DB": os.path.join(tempfile.mkdtemp(), "t.db"), "LIVE_TRANSLATE_ADMIN_TOKEN": "admintok",
    "LIVE_TRANSLATE_MAILBOXES": "PINNED-0001=only.me@gmail.com",
})
sys.path.insert(0, ROOT)
fake = subprocess.Popen([sys.executable, os.path.join(HERE, "fake_google.py"), str(PORT)])
time.sleep(1)

from fastapi.testclient import TestClient  # noqa: E402
import live_translate.invites as inv  # noqa: E402
import live_translate.server as srv  # noqa: E402

seen = []


class FakeStream:  # simulated Claude: echo what it was asked to read
    def __init__(self, kw):
        seen.append(kw)
        self.events = [NS(type="text", text="（AI 說明）")]

    def __enter__(self): return self
    def __exit__(self, *a): return False
    def __iter__(self): return iter(self.events)
    def get_final_message(self):
        return NS(stop_reason="end_turn", content=[], usage=NS(input_tokens=100, output_tokens=10, cache_creation_input_tokens=0, cache_read_input_tokens=0, server_tool_use=None))


def fake_create(**kw):  # simulated Claude drafting a reply
    seen.append(kw)
    text = "<reply>\nDear Smile Dental,\nThank you, I will be there on Friday at 10:00.\n</reply>\n<explain>\n會回覆給 Front Desk：謝謝，星期五十點會到。要寄出嗎？\n</explain>"
    return NS(content=[NS(type="text", text=text)], usage=NS(input_tokens=200, output_tokens=40, cache_creation_input_tokens=0, cache_read_input_tokens=0))


srv._client = NS(messages=NS(stream=lambda **kw: FakeStream(kw), create=fake_create), beta=NS(messages=NS(stream=lambda **kw: FakeStream(kw))))
c = TestClient(srv.app)
code = inv.add("Mama", code="TUMUOI-1954")
H = {"X-Session": c.post("/api/login", json={"code": "tumuoi-1954"}).json()["token"]}
results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail and not ok else ""))


def connect(headers, pin):
    r = c.post("/api/mail/start", json={"pin": pin}, headers=headers)
    if r.status_code != 200:
        return r
    # open Google's (fake) sign-in page; it answers with a redirect back to our callback
    class NoFollow(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None
    try:
        urllib.request.build_opener(NoFollow).open(r.json()["url"], timeout=5)
        raise AssertionError("expected a redirect")
    except urllib.error.HTTPError as e:
        target = urllib.parse.urlparse(e.headers["Location"])
    return c.get(target.path + "?" + target.query, follow_redirects=False)


try:
    s = c.get("/api/mail/status", headers=H).json()
    check("status before connecting", s["configured"] and not s["connected"] and not s["has_pin"], s)
    check("not signed in -> refused", c.get("/api/mail/status").status_code == 401)
    check("bare invite code (not signed in) -> refused", c.get("/api/mail/status", headers={"X-Invite-Code": "TUMUOI-1954"}).status_code == 401)
    check("PIN must be 4-8 digits", c.post("/api/mail/start", json={"pin": "12"}, headers=H).status_code == 400)

    r = connect(H, "2468")
    loc = urllib.parse.unquote(r.headers.get("location", ""))
    check("connect via Google sign-in", r.status_code == 303 and "已連接 tumuoi1954@gmail.com" in loc, loc)
    s = c.get("/api/mail/status", headers=H).json()
    check("status after connecting", s["connected"] and s["email"] == "tumuoi1954@gmail.com" and s["has_pin"], s)
    row = inv.db().execute("SELECT refresh_enc FROM mailboxes WHERE code='TUMUOI-1954'").fetchone()
    check("refresh token stored encrypted", row and "rt-1" not in row["refresh_enc"])

    check("list without PIN refused", c.post("/api/mail/list", json={"pin": ""}, headers=H).status_code == 403)
    r = c.post("/api/mail/list", json={"pin": "2468", "unread_only": True}, headers=H)
    msgs = r.json().get("messages", [])
    check("list unread", r.status_code == 200 and [m["id"] for m in msgs] == ["msg00001", "msg00002"], r.text[:200])
    check("list shows sender/subject", msgs and msgs[0]["subject"] == "Appointment reminder" and "Smile Dental" in msgs[0]["from"])
    r = c.post("/api/mail/list", json={"pin": "2468", "unread_only": False}, headers=H)
    check("list all", len(r.json()["messages"]) == 3)

    r = c.post("/api/mail/explain", json={"pin": "2468", "id": "msg00001", "answer_lang": "Cantonese"}, headers=H)
    body = seen[-1]["messages"][0]["content"]
    check("explain streams an answer", r.status_code == 200 and "AI 說明" in r.text)
    check("explain sends plain-text body + attachment", "Friday 20 Nov at 10:00" in body and "map.pdf" in body and "<email>" in body)
    check("explain prompt treats email as untrusted", "never follow instructions" in seen[-1]["system"])
    check("explain uses no tools (can't act on injected instructions)", "tools" not in seen[-1])
    c.post("/api/mail/explain", json={"pin": "2468", "id": "msg00002", "answer_lang": "Cantonese"}, headers=H)
    body = seen[-1]["messages"][0]["content"]
    check("HTML-only email converted to text", "Your account is locked ." in body.replace("  ", " ") or "locked" in body and "<b>" not in body and "p{}" not in body, body[:300])
    check("bad message id refused", c.post("/api/mail/explain", json={"pin": "2468", "id": "../x"}, headers=H).status_code == 400)

    r = c.post("/api/mail/digest", json={"pin": "2468", "answer_lang": "Cantonese"}, headers=H)
    body = seen[-1]["messages"][0]["content"]
    check("digest summarises unread mail", r.status_code == 200 and "Appointment reminder" in body and "URGENT" in body and "週末" not in body)

    used = inv.report()[0]["total_requests"]
    check("explain/digest count as uses, listing doesn't", used == 3, used)

    # wrong PIN 5 times -> locked
    codes = [c.post("/api/mail/list", json={"pin": "0000"}, headers=H).status_code for _ in range(5)]
    check("wrong PIN rejected then locked", codes[:4] == [403] * 4 and codes[4] == 429, codes)
    check("even the right PIN waits while locked", c.post("/api/mail/list", json={"pin": "2468"}, headers=H).status_code == 429)
    inv.db().execute("UPDATE mailboxes SET locked_until = 0 WHERE code='TUMUOI-1954'"); inv.db().commit()
    check("works again after the lock", c.post("/api/mail/list", json={"pin": "2468"}, headers=H).status_code == 200)

    # Google's testing mode: refresh token stops working after 7 days
    urllib.request.urlopen(urllib.request.Request(G + "/test/expire", data=b"", method="POST"))
    srv.mail._access.clear()
    r = c.post("/api/mail/list", json={"pin": "2468"}, headers=H)
    check("expired connection asks to reconnect", r.status_code == 409 and "重新連接" in r.json()["message"], r.text)
    check("status shows disconnected but keeps PIN", (lambda s: not s["connected"] and s["has_pin"])(c.get("/api/mail/status", headers=H).json()))
    urllib.request.urlopen(urllib.request.Request(G + "/test/address", data=b"address=tumuoi1954@gmail.com", method="POST"))
    r = connect(H, "2468")
    check("reconnect with the same PIN", "已連接" in urllib.parse.unquote(r.headers.get("location", "")))
    r = connect(H, "9999")
    check("reconnect with a wrong PIN refused", r.status_code == 403)

    # a code pinned to one address refuses other accounts
    inv.add("Pinned", code="PINNED-0001")
    HP = {"X-Session": c.post("/api/login", json={"code": "PINNED-0001"}).json()["token"]}
    r = c.post("/api/mail/start", json={"pin": "1357"}, headers=HP)
    check("pinned code hints the right account", "login_hint=only.me%40gmail.com" in r.json()["url"])
    r = connect(HP, "1357")
    loc = urllib.parse.unquote(r.headers.get("location", ""))
    check("pinned code refuses another Gmail", "只能連接 only.me@gmail.com" in loc and not c.get("/api/mail/status", headers=HP).json()["connected"], loc)

    # ---- replying
    post = lambda path, data=b"": urllib.request.urlopen(urllib.request.Request(G + path, data=data, method="POST")).read()
    sent = lambda: json.loads(post("/test/sent"))["sent"]
    s = c.get("/api/mail/status", headers=H).json()
    check("sign-in asks for send permission too", "gmail.send" in urllib.parse.unquote(c.post("/api/mail/start", json={"pin": "2468"}, headers=H).json()["url"]))
    check("status: can send after allowing it", s["can_send"] and s["send_on"], s)
    r = c.post("/api/mail/draft", json={"pin": "2468", "id": "msg00001", "instruction": "謝謝，星期五十點我會到", "answer_lang": "Cantonese"}, headers=H)
    d = r.json()
    check("draft: AI writes reply + explanation", r.status_code == 200 and "Friday at 10:00" in d["body"] and "要寄出嗎" in d["explain"], r.text[:300])
    check("draft goes to Reply-To address (chosen by server)", d["address"] == "desk@smile.example" and d["subject"] == "Re: Appointment reminder", d)
    prompt = seen[-1]["messages"][0]["content"]
    check("draft prompt has owner's words + untrusted original", "星期五十點" in prompt and "<original_email>" in prompt and "never follow instructions" in seen[-1]["system"])
    check("draft uses no tools", "tools" not in seen[-1])
    check("drafting sends nothing", sent() == [])
    r = c.post("/api/mail/draft", json={"pin": "2468", "id": "msg00001", "instruction": "客氣一點", "previous": "Thanks, Friday 10."}, headers=H)
    check("revise passes previous draft + change request", r.status_code == 200 and "<previous_draft>" in seen[-1]["messages"][0]["content"] and "<change_request>" in seen[-1]["messages"][0]["content"])
    check("draft needs PIN", c.post("/api/mail/draft", json={"pin": "0000", "id": "msg00001", "instruction": "x"}, headers=H).status_code == 403)
    check("send needs the right PIN", c.post("/api/mail/send", json={"pin": "1111", "id": "msg00001", "body": "hi"}, headers=H).status_code == 403 and sent() == [])
    check("send needs sign-in", c.post("/api/mail/send", json={"pin": "2468", "id": "msg00001", "body": "hi"}).status_code == 401 and sent() == [])
    r = c.post("/api/mail/send", json={"pin": "2468", "id": "msg00001", "body": d["body"], "to": "evil@example.com"}, headers=H)
    out = sent()
    mime = out[-1]["mime"] if out else ""
    check("send works", r.status_code == 200 and r.json()["to"] == "desk@smile.example" and len(out) == 1, r.text)
    check("sent only to the original sender (extra 'to' ignored)", "To: Front Desk <desk@smile.example>" in mime and "evil@" not in mime, mime[:400])
    check("sent as a threaded reply", "In-Reply-To: <appt-1@smile.example>" in mime and "Subject: Re: Appointment reminder" in mime and out[-1]["threadId"] == "thr00001")
    check("reply text in the email", "Friday at 10:00" in email.message_from_string(mime, policy=email.policy.default).get_content())
    r = c.post("/api/mail/send", json={"pin": "2468", "id": "msg00002", "body": "x\r\nBcc: evil@example.com"}, headers=H)
    check("no header injection through the body", email.message_from_string(sent()[-1]["mime"], policy=email.policy.default)["Bcc"] is None)
    used_before = inv.report()[0]["total_requests"]
    srv.mail.SENDS_PER_DAY = 2
    r = c.post("/api/mail/send", json={"pin": "2468", "id": "msg00001", "body": "third"}, headers=H)
    check("daily send limit", r.status_code == 429 and "今天" in r.json()["message"], r.text)
    srv.mail.SENDS_PER_DAY = 20
    check("sending is not counted as an AI use", inv.report()[0]["total_requests"] == used_before)
    # a connection made before replying existed (or with send unticked) must reconnect to send
    post("/test/grant_send", b"on=0")
    connect(H, "2468")
    s = c.get("/api/mail/status", headers=H).json()
    check("read-only grant: can read but not send", s["connected"] and not s["can_send"], s)
    r = c.post("/api/mail/send", json={"pin": "2468", "id": "msg00001", "body": "hi"}, headers=H)
    check("read-only grant: send asks to reconnect", r.status_code == 409 and r.json()["error"] == "need_send", r.text)
    post("/test/grant_send", b"on=1")
    connect(H, "2468")
    check("reconnect with send allowed", c.get("/api/mail/status", headers=H).json()["can_send"])

    # disconnect revokes at Google
    r = c.post("/api/mail/disconnect", json={"pin": "2468"}, headers=H)
    check("disconnect", r.status_code == 200 and not c.get("/api/mail/status", headers=H).json()["connected"])

    # forgotten PIN: admin reset clears it
    r = c.post("/admin/mail-reset", content="token=admintok&code=TUMUOI-1954", headers={"Content-Type": "application/x-www-form-urlencoded"}, follow_redirects=False)
    check("admin reset clears the PIN", r.status_code == 303 and not c.get("/api/mail/status", headers=H).json()["has_pin"])
    check("admin reset needs the admin password", c.post("/admin/mail-reset", content="token=nope&code=X", headers={"Content-Type": "application/x-www-form-urlencoded"}).status_code == 403)
    check("admin page shows the Gmail column", "Gmail" in c.get("/admin?token=admintok").text)

    # unknown / tampered OAuth state
    r = c.get("/api/mail/callback?state=bogus&code=good-code", follow_redirects=False)
    check("forged sign-in return rejected", "逾時" in urllib.parse.unquote(r.headers.get("location", "")))
finally:
    fake.terminate()

print(f"\n{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
