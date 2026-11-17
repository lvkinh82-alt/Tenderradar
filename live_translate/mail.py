"""Read-only Gmail for Muối Từ: each invite code can connect its owner's own Gmail.

How it works
- The owner taps "Connect Gmail" in the app, signs in on Google's own page and allows
  read-only access (scope gmail.readonly). The app never sees the Gmail password.
- Google gives a refresh token, stored encrypted (key derived from GOOGLE_CLIENT_SECRET,
  or MAIL_SECRET if set) in the same SQLite database as the invite codes.
- Every mail request needs the invite code AND the owner's personal PIN. The PIN is kept
  only as a salted PBKDF2 hash; 5 wrong tries lock the mailbox for 15 minutes.
- Optional LIVE_TRANSLATE_MAILBOXES="TUMUOI-1954=tumuoi1954@gmail.com, ..." pins a code to
  one Gmail address: signing in with any other account is refused.

Google settings (see RAILWAY.md): GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET and PUBLIC_BASE_URL
(the app's https address; the redirect URI is PUBLIC_BASE_URL + /api/mail/callback).
In Google's "Testing" mode a connection expires after 7 days; the app then asks to reconnect.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import html
import json
import os
import re
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from . import invites

SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
# Overridable so tests can run against a local fake of Google.
AUTH_URL = os.environ.get("GOOGLE_AUTH_URL", "https://accounts.google.com/o/oauth2/v2/auth")
TOKEN_URL = os.environ.get("GOOGLE_TOKEN_URL", "https://oauth2.googleapis.com/token")
REVOKE_URL = os.environ.get("GOOGLE_REVOKE_URL", "https://oauth2.googleapis.com/revoke")
GMAIL_API = os.environ.get("GMAIL_API_BASE", "https://gmail.googleapis.com/gmail/v1")

PIN_TRIES = 5
LOCK_SECONDS = 15 * 60

_lock = threading.Lock()
_states: dict[str, tuple[str, float]] = {}       # OAuth state -> (invite code, expiry)
_access: dict[str, tuple[str, float]] = {}       # invite code -> (access token, expiry)


def client_id() -> str:
    return os.environ.get("GOOGLE_CLIENT_ID", "").strip()


def client_secret() -> str:
    return os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()


def configured() -> bool:
    return bool(client_id() and client_secret())


def _fernet() -> Fernet:
    seed = os.environ.get("MAIL_SECRET") or client_secret()
    key = base64.urlsafe_b64encode(hashlib.sha256(("muoitu-mail:" + seed).encode()).digest())
    return Fernet(key)


def allowed_address(code: str) -> str | None:
    """The Gmail address this code is pinned to, if LIVE_TRANSLATE_MAILBOXES says so."""
    spec = os.environ.get("LIVE_TRANSLATE_MAILBOXES", "")
    for item in spec.replace("\n", ",").split(","):
        if "=" in item:
            c, addr = item.split("=", 1)
            if invites.normalize(c) == invites.normalize(code):
                return addr.strip().lower() or None
    return None


# ----------------------------------------------------------------------------- storage

def _db():
    conn = invites.db()
    conn.execute(
        """CREATE TABLE IF NOT EXISTS mailboxes (
               code          TEXT PRIMARY KEY,
               email         TEXT,
               refresh_enc   TEXT,
               pin_hash      TEXT,
               pin_salt      TEXT,
               fails         INTEGER NOT NULL DEFAULT 0,
               locked_until  REAL NOT NULL DEFAULT 0,
               connected_at  TEXT
           )"""
    )
    return conn


@dataclass
class Box:
    code: str
    email: str | None
    refresh_enc: str | None
    pin_hash: str | None
    pin_salt: str | None
    fails: int
    locked_until: float


def _get(code: str) -> Box | None:
    with invites._lock:
        row = _db().execute("SELECT * FROM mailboxes WHERE code = ?", (invites.normalize(code),)).fetchone()
    if not row:
        return None
    return Box(row["code"], row["email"], row["refresh_enc"], row["pin_hash"], row["pin_salt"], row["fails"], row["locked_until"])


def _save(code: str, **fields: Any) -> None:
    code = invites.normalize(code)
    with invites._lock:
        conn = _db()
        conn.execute("INSERT OR IGNORE INTO mailboxes (code) VALUES (?)", (code,))
        for k, v in fields.items():
            conn.execute(f"UPDATE mailboxes SET {k} = ? WHERE code = ?", (v, code))
        conn.commit()


def reset(code: str) -> bool:
    """Forget the connection and the PIN (used when an owner forgets their PIN)."""
    _access.pop(invites.normalize(code), None)
    with invites._lock:
        cur = _db().execute("DELETE FROM mailboxes WHERE code = ?", (invites.normalize(code),))
        invites.db().commit()
    return cur.rowcount > 0


def overview() -> dict[str, str]:
    with invites._lock:
        rows = _db().execute("SELECT code, email, refresh_enc FROM mailboxes").fetchall()
    return {r["code"]: (r["email"] or "") if r["refresh_enc"] else "" for r in rows}


# ----------------------------------------------------------------------------- PIN

class MailError(Exception):
    """An error with a bilingual message for the user and an HTTP status."""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def _hash_pin(pin: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, 200_000).hex()


def valid_pin_format(pin: str) -> bool:
    return bool(re.fullmatch(r"\d{4,8}", pin or ""))


def check_pin(code: str, pin: str, *, allow_set: bool = False) -> Box:
    """Verify the PIN (or set it the first time when allow_set). Raises MailError."""
    box = _get(code)
    now = time.time()
    if box and box.locked_until > now:
        mins = int((box.locked_until - now) // 60) + 1
        raise MailError(429, "locked", f"PIN 錯太多次，請 {mins} 分鐘後再試。 / Too many wrong PINs. Try again in {mins} min.")
    if not box or not box.pin_hash:
        if not allow_set:
            raise MailError(403, "no_pin", "請先設定 PIN 並連接 Gmail。 / Please set a PIN and connect Gmail first.")
        if not valid_pin_format(pin):
            raise MailError(400, "bad_pin", "PIN 要是 4 到 8 位數字。 / The PIN must be 4–8 digits.")
        salt = secrets.token_bytes(16)
        _save(code, pin_hash=_hash_pin(pin, salt), pin_salt=salt.hex(), fails=0, locked_until=0)
        return _get(code)  # type: ignore[return-value]
    if not hmac.compare_digest(_hash_pin(pin or "", bytes.fromhex(box.pin_salt or "")), box.pin_hash):
        fails = box.fails + 1
        if fails >= PIN_TRIES:
            _save(code, fails=0, locked_until=now + LOCK_SECONDS)
            raise MailError(429, "locked", "PIN 錯太多次，已鎖 15 分鐘。 / Too many wrong PINs, locked for 15 minutes.")
        _save(code, fails=fails)
        raise MailError(403, "wrong_pin", f"PIN 不對，還可以再試 {PIN_TRIES - fails} 次。 / Wrong PIN, {PIN_TRIES - fails} tries left.")
    if box.fails:
        _save(code, fails=0)
    return box


def status(code: str) -> dict[str, Any]:
    box = _get(code)
    return {
        "configured": configured(),
        "has_pin": bool(box and box.pin_hash),
        "connected": bool(box and box.refresh_enc),
        "email": (box.email if box and box.refresh_enc else "") or "",
        "locked": bool(box and box.locked_until > time.time()),
        "pinned_to": allowed_address(code) or "",
    }


# ----------------------------------------------------------------------------- OAuth

def _post_form(url: str, data: dict[str, str]) -> dict[str, Any]:
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode(),
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return {"error": json.loads(e.read() or b"{}").get("error", f"http_{e.code}")}
        except ValueError:
            return {"error": f"http_{e.code}"}


def start_url(code: str, redirect_uri: str) -> str:
    state = secrets.token_urlsafe(24)
    with _lock:
        now = time.time()
        for k in [k for k, (_, exp) in _states.items() if exp < now]:
            _states.pop(k, None)
        _states[state] = (invites.normalize(code), now + 600)
    params = {
        "client_id": client_id(), "redirect_uri": redirect_uri, "response_type": "code",
        "scope": SCOPE, "access_type": "offline", "prompt": "consent", "state": state,
        "include_granted_scopes": "true",
    }
    hint = allowed_address(code)
    if hint:
        params["login_hint"] = hint
    return AUTH_URL + "?" + urllib.parse.urlencode(params)


def finish(state: str, auth_code: str, redirect_uri: str) -> str:
    """Handle Google's redirect. Returns the connected address; raises MailError."""
    with _lock:
        entry = _states.pop(state, None)
    if not entry or entry[1] < time.time():
        raise MailError(400, "expired", "連接逾時，請回 App 再按一次「連接 Gmail」。 / The sign-in expired, please try again.")
    code = entry[0]
    tok = _post_form(TOKEN_URL, {
        "code": auth_code, "client_id": client_id(), "client_secret": client_secret(),
        "redirect_uri": redirect_uri, "grant_type": "authorization_code",
    })
    if "refresh_token" not in tok or "access_token" not in tok:
        raise MailError(400, "token", f"Google 沒有給授權（{tok.get('error', 'unknown')}）。 / Google did not grant access.")
    if SCOPE not in tok.get("scope", SCOPE):
        raise MailError(400, "scope", "需要勾選「讀取 Gmail」的權限。 / Please allow reading Gmail.")
    email = _api_get(tok["access_token"], "/users/me/profile").get("emailAddress", "").lower()
    pinned = allowed_address(code)
    if pinned and email != pinned:
        _post_form(REVOKE_URL, {"token": tok["refresh_token"]})
        raise MailError(403, "wrong_account", f"這個邀請碼只能連接 {pinned}，你登入的是 {email}。 / This code can only connect {pinned}.")
    _save(code, email=email, refresh_enc=_fernet().encrypt(tok["refresh_token"].encode()).decode(),
          connected_at=time.strftime("%Y-%m-%d %H:%M"))
    _access[code] = (tok["access_token"], time.time() + int(tok.get("expires_in", 3600)) - 60)
    return email


def disconnect(code: str) -> None:
    box = _get(code)
    if box and box.refresh_enc:
        try:
            _post_form(REVOKE_URL, {"token": _fernet().decrypt(box.refresh_enc.encode()).decode()})
        except InvalidToken:
            pass
    _access.pop(invites.normalize(code), None)
    _save(code, email=None, refresh_enc=None)


def _access_token(code: str) -> str:
    code = invites.normalize(code)
    cached = _access.get(code)
    if cached and cached[1] > time.time():
        return cached[0]
    box = _get(code)
    if not box or not box.refresh_enc:
        raise MailError(409, "not_connected", "還沒連接 Gmail。 / Gmail isn't connected yet.")
    try:
        refresh = _fernet().decrypt(box.refresh_enc.encode()).decode()
    except InvalidToken:
        _save(code, refresh_enc=None)
        raise MailError(409, "reconnect", "Gmail 連接已失效，請重新連接。 / Please reconnect Gmail.")
    tok = _post_form(TOKEN_URL, {
        "client_id": client_id(), "client_secret": client_secret(),
        "refresh_token": refresh, "grant_type": "refresh_token",
    })
    if "access_token" not in tok:
        # invalid_grant: revoked, password changed, or the 7-day limit of Google's testing mode
        _save(code, refresh_enc=None)
        raise MailError(409, "reconnect", "Gmail 連接已到期（Google 測試模式每 7 天要重新登入），請重新連接。 / The Gmail connection expired, please reconnect.")
    _access[code] = (tok["access_token"], time.time() + int(tok.get("expires_in", 3600)) - 60)
    return tok["access_token"]


def _api_get(token: str, path: str, params: list[tuple[str, str]] | None = None) -> dict[str, Any]:
    url = GMAIL_API + path + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise MailError(409, "reconnect", "Gmail 連接已失效，請重新連接。 / Please reconnect Gmail.")
        raise MailError(502, "gmail", f"Gmail 暫時無法讀取（{e.code}）。 / Gmail is unavailable ({e.code}).")
    except urllib.error.URLError:
        raise MailError(502, "gmail", "連不上 Gmail，請稍後再試。 / Can't reach Gmail right now.")


def _gmail(code: str, path: str, params: list[tuple[str, str]] | None = None) -> dict[str, Any]:
    try:
        return _api_get(_access_token(code), path, params)
    except MailError as e:
        if e.code == "reconnect":
            _access.pop(invites.normalize(code), None)
        raise


# ----------------------------------------------------------------------------- reading mail

def _header(msg: dict[str, Any], name: str) -> str:
    for h in msg.get("payload", {}).get("headers", []):
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def list_messages(code: str, unread_only: bool, limit: int = 15) -> list[dict[str, Any]]:
    q = "in:inbox is:unread" if unread_only else "in:inbox"
    ids = _gmail(code, "/users/me/messages", [("q", q), ("maxResults", str(limit))]).get("messages", [])
    out = []
    for m in ids:
        msg = _gmail(code, f"/users/me/messages/{m['id']}",
                     [("format", "metadata"), ("metadataHeaders", "From"), ("metadataHeaders", "Subject"), ("metadataHeaders", "Date")])
        out.append({
            "id": msg.get("id", m["id"]),
            "from": _header(msg, "From"),
            "subject": _header(msg, "Subject"),
            "date": _header(msg, "Date"),
            "snippet": html.unescape(msg.get("snippet", "")),
            "unread": "UNREAD" in msg.get("labelIds", []),
        })
    return out


def _decode(data: str) -> str:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", "replace")


def _html_to_text(s: str) -> str:
    s = re.sub(r"(?is)<(script|style|head)[^>]*>.*?</\1>", " ", s)
    s = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>|</li>", "\n", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    return re.sub(r"[ \t\r\f\v]+", " ", re.sub(r"\n\s*\n+", "\n\n", s)).strip()


def _body_text(part: dict[str, Any]) -> tuple[str, str]:
    """(plain, html) text found in a MIME part tree."""
    plain, rich = "", ""
    mime = part.get("mimeType", "")
    data = part.get("body", {}).get("data")
    if data and mime == "text/plain":
        plain = _decode(data)
    elif data and mime == "text/html":
        rich = _decode(data)
    for p in part.get("parts", []) or []:
        a, b = _body_text(p)
        plain, rich = plain or a, rich or b
    return plain, rich


def read_message(code: str, msg_id: str, max_chars: int = 15000) -> dict[str, Any]:
    if not re.fullmatch(r"[A-Za-z0-9_-]{6,64}", msg_id or ""):
        raise MailError(400, "bad_id", "郵件編號不正確。 / Invalid message id.")
    msg = _gmail(code, f"/users/me/messages/{msg_id}", [("format", "full")])
    plain, rich = _body_text(msg.get("payload", {}))
    body = plain.strip() or _html_to_text(rich) or html.unescape(msg.get("snippet", ""))
    attachments = []
    def walk(p: dict[str, Any]) -> None:
        if p.get("filename"):
            attachments.append(p["filename"])
        for c in p.get("parts", []) or []:
            walk(c)
    walk(msg.get("payload", {}))
    return {
        "from": _header(msg, "From"), "to": _header(msg, "To"), "subject": _header(msg, "Subject"),
        "date": _header(msg, "Date"), "body": body[:max_chars], "truncated": len(body) > max_chars,
        "attachments": attachments,
    }
