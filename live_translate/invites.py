"""Invite codes for Muối Từ: only people you give a code to can use your API credit.

Codes and usage live in a small SQLite file (default: live_translate/data/invites.db,
override with LIVE_TRANSLATE_DB). Manage them from the command line:

    python3 -m live_translate.invites add "阿明"                 # new code, no daily limit
    python3 -m live_translate.invites add "小美" --daily-limit 300
    python3 -m live_translate.invites add "阿明" --code TUMUOI-1954   # choose the code yourself
    python3 -m live_translate.invites list                       # usage + estimated cost
    python3 -m live_translate.invites disable MT-7K3Q-9XPA
    python3 -m live_translate.invites enable  MT-7K3Q-9XPA
    python3 -m live_translate.invites limit   MT-7K3Q-9XPA 500    # 0 = unlimited
    python3 -m live_translate.invites delete  MT-7K3Q-9XPA
"""

from __future__ import annotations

import argparse
import os
import secrets
import sqlite3
import threading
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

DB_PATH = Path(os.environ.get("LIVE_TRANSLATE_DB", Path(__file__).parent / "data" / "invites.db"))
# Letters/digits that can't be confused when read aloud or typed (no 0/O, 1/I/L).
ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
# USD per million tokens (input, output), for the cost estimate in `list`.
# Haiku 5.5's price applies to prompts up to 100K tokens, which translation requests always are.
MODEL_PRICES = {
    "claude-opus-5-5": (4.0, 20.0),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-haiku-5-5": (0.10, 0.50),
}
_model = os.environ.get("LIVE_TRANSLATE_MODEL", "claude-opus-5-5")
_default_in, _default_out = MODEL_PRICES.get(_model, MODEL_PRICES["claude-opus-5-5"])
PRICE_IN = float(os.environ.get("LIVE_TRANSLATE_PRICE_IN", _default_in))
PRICE_OUT = float(os.environ.get("LIVE_TRANSLATE_PRICE_OUT", _default_out))
PRICE_SEARCH = float(os.environ.get("LIVE_TRANSLATE_PRICE_SEARCH", "0.01"))  # USD per web search

_lock = threading.Lock()


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS invites (
            code        TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            active      INTEGER NOT NULL DEFAULT 1,
            daily_limit INTEGER NOT NULL DEFAULT 0,
            created_at  TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS usage (
            code          TEXT NOT NULL,
            day           TEXT NOT NULL,
            requests      INTEGER NOT NULL DEFAULT 0,
            input_tokens  INTEGER NOT NULL DEFAULT 0,
            output_tokens INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (code, day)
        );
        """
    )
    cols = {r[1] for r in conn.execute("PRAGMA table_info(usage)")}
    if "searches" not in cols:  # databases created before web search existed
        conn.execute("ALTER TABLE usage ADD COLUMN searches INTEGER NOT NULL DEFAULT 0")
        conn.commit()
    return conn


_conn: sqlite3.Connection | None = None


def db() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = _connect()
    return _conn


def normalize(code: str) -> str:
    return code.strip().upper().replace(" ", "")


def new_code() -> str:
    body = "".join(secrets.choice(ALPHABET) for _ in range(8))
    return f"MT-{body[:4]}-{body[4:]}"


@dataclass
class CheckResult:
    status: str  # "ok" | "missing" | "invalid" | "disabled" | "limit"
    name: str = ""
    used_today: int = 0
    daily_limit: int = 0


def check(code: str | None) -> CheckResult:
    """Validate a code without recording usage."""
    if not code or not code.strip():
        return CheckResult("missing")
    with _lock:
        row = db().execute("SELECT * FROM invites WHERE code = ?", (normalize(code),)).fetchone()
        if row is None:
            return CheckResult("invalid")
        used = db().execute(
            "SELECT requests FROM usage WHERE code = ? AND day = ?", (row["code"], date.today().isoformat())
        ).fetchone()
    used_today = used["requests"] if used else 0
    res = CheckResult("ok", row["name"], used_today, row["daily_limit"])
    if not row["active"]:
        res.status = "disabled"
    elif row["daily_limit"] and used_today >= row["daily_limit"]:
        res.status = "limit"
    return res


def record(code: str, input_tokens: int = 0, output_tokens: int = 0, searches: int = 0, requests: int = 1) -> None:
    with _lock:
        db().execute(
            """INSERT INTO usage (code, day, requests, input_tokens, output_tokens, searches) VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(code, day) DO UPDATE SET
                 requests = requests + excluded.requests,
                 input_tokens = input_tokens + excluded.input_tokens,
                 output_tokens = output_tokens + excluded.output_tokens,
                 searches = searches + excluded.searches""",
            (normalize(code), date.today().isoformat(), requests, input_tokens, output_tokens, searches),
        )
        db().commit()


def add(name: str, daily_limit: int = 0, code: str | None = None) -> str:
    """Create a code. Pass `code` to choose it yourself; raises ValueError if taken or malformed."""
    if code is not None:
        code = normalize(code)
        if not (4 <= len(code) <= 32) or not all(ch.isalnum() or ch == "-" for ch in code):
            raise ValueError("邀請碼只能用英文字母、數字和「-」，長度 4–32 個字。")
        with _lock:
            try:
                db().execute(
                    "INSERT INTO invites (code, name, daily_limit, created_at) VALUES (?, ?, ?, ?)",
                    (code, name, daily_limit, datetime.now().isoformat(timespec="seconds")),
                )
                db().commit()
            except sqlite3.IntegrityError:
                raise ValueError(f"邀請碼 {code} 已經存在。") from None
        return code
    with _lock:
        while True:
            code = new_code()
            try:
                db().execute(
                    "INSERT INTO invites (code, name, daily_limit, created_at) VALUES (?, ?, ?, ?)",
                    (code, name, daily_limit, datetime.now().isoformat(timespec="seconds")),
                )
                db().commit()
                return code
            except sqlite3.IntegrityError:
                continue  # astronomically unlikely collision: try another


def _update(code: str, sql: str, *args) -> bool:
    with _lock:
        cur = db().execute(sql, (*args, normalize(code)))
        db().commit()
        return cur.rowcount > 0


def set_active(code: str, active: bool) -> bool:
    return _update(code, "UPDATE invites SET active = ? WHERE code = ?", int(active))


def set_limit(code: str, daily_limit: int) -> bool:
    return _update(code, "UPDATE invites SET daily_limit = ? WHERE code = ?", daily_limit)


def delete(code: str) -> bool:
    with _lock:
        c = normalize(code)
        db().execute("DELETE FROM usage WHERE code = ?", (c,))
        cur = db().execute("DELETE FROM invites WHERE code = ?", (c,))
        db().commit()
        return cur.rowcount > 0


def parse_spec(spec: str) -> list[tuple[str, str, int]]:
    """Parse "Mama:TUMUOI-1954, 阿明:TUMUOI-2024:200" (or one entry per line) into (name, code, limit)."""
    out = []
    for raw in spec.replace("\n", ",").split(","):
        item = raw.strip()
        if not item:
            continue
        parts = [p.strip() for p in item.split(":")]
        if len(parts) not in (2, 3) or not parts[0] or not parts[1]:
            raise ValueError(f"格式不對：「{item}」，應該是 名字:邀請碼 或 名字:邀請碼:每日上限")
        try:
            limit = int(parts[2]) if len(parts) == 3 and parts[2] else 0
        except ValueError:
            raise ValueError(f"「{item}」的每日上限要是數字（0 = 不限）") from None
        code = normalize(parts[1])
        if not (4 <= len(code) <= 32) or not all(ch.isalnum() or ch == "-" for ch in code):
            raise ValueError(f"邀請碼「{parts[1]}」只能用英文字母、數字和「-」，長度 4–32 個字。")
        out.append((parts[0], code, limit))
    return out


def sync_from_env(spec: str) -> list[tuple[str, str, int]]:
    """Make the database match an invite list kept in an environment variable (used on Railway).

    Listed codes are created or updated and enabled; codes not in the list are disabled
    (not deleted, so their usage history is kept).
    """
    entries = parse_spec(spec)
    now = datetime.now().isoformat(timespec="seconds")
    with _lock:
        conn = db()
        for name, code, limit in entries:
            conn.execute(
                """INSERT INTO invites (code, name, active, daily_limit, created_at) VALUES (?, ?, 1, ?, ?)
                   ON CONFLICT(code) DO UPDATE SET name = excluded.name, active = 1, daily_limit = excluded.daily_limit""",
                (code, name, limit, now),
            )
        listed = [c for _, c, _ in entries]
        if listed:
            conn.execute(f"UPDATE invites SET active = 0 WHERE code NOT IN ({','.join('?' * len(listed))})", listed)
        else:
            conn.execute("UPDATE invites SET active = 0")
        conn.commit()
    return entries


def any_codes() -> bool:
    with _lock:
        return db().execute("SELECT 1 FROM invites LIMIT 1").fetchone() is not None


def report() -> list[dict]:
    today = date.today().isoformat()
    with _lock:
        rows = db().execute(
            """SELECT i.code, i.name, i.active, i.daily_limit, i.created_at,
                      COALESCE(SUM(u.requests), 0) AS total_requests,
                      COALESCE(SUM(u.input_tokens), 0) AS input_tokens,
                      COALESCE(SUM(u.output_tokens), 0) AS output_tokens,
                      COALESCE(SUM(u.searches), 0) AS searches,
                      COALESCE(SUM(CASE WHEN u.day = ? THEN u.requests END), 0) AS today_requests
               FROM invites i LEFT JOIN usage u ON u.code = i.code
               GROUP BY i.code ORDER BY i.created_at""",
            (today,),
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["cost_usd"] = (d["input_tokens"] * PRICE_IN + d["output_tokens"] * PRICE_OUT) / 1_000_000 + d["searches"] * PRICE_SEARCH
        out.append(d)
    return out


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="./invite.sh", description="管理 Muối Từ 邀請碼")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add", help="新增邀請碼")
    a.add_argument("name", help="這個碼是給誰的（備註）")
    a.add_argument("--daily-limit", type=int, default=0, help="每天最多翻譯幾次，0 = 不限")
    a.add_argument("--code", help="自己指定邀請碼（例如 TUMUOI-1954）；不填就自動產生")
    sub.add_parser("list", help="列出所有邀請碼與用量")
    for cmd, h in [("disable", "停用"), ("enable", "重新啟用"), ("delete", "刪除（連同用量紀錄）")]:
        sub.add_parser(cmd, help=h).add_argument("code")
    lim = sub.add_parser("limit", help="修改每日上限")
    lim.add_argument("code")
    lim.add_argument("daily_limit", type=int)
    args = ap.parse_args(argv)

    if args.cmd == "add":
        try:
            code = add(args.name, args.daily_limit, args.code)
        except ValueError as e:
            raise SystemExit(f"無法建立：{e}")
        print(f"已建立邀請碼：{code}  （{args.name}）")
        if args.code and sum(ch.isalnum() for ch in code) < 10:
            print("提醒：自訂的碼比較短，別人比較容易猜到。建議設每日上限（--daily-limit），或用自動產生的碼。")
        print("把這個碼傳給對方，請他在 App 或網頁的「設定 → 邀請碼」輸入。")
    elif args.cmd == "list":
        rows = report()
        if not rows:
            print("還沒有邀請碼。用：python3 -m live_translate.invites add \"名字\"")
            return
        print(f"{'邀請碼':<14} {'名字':<10} {'狀態':<4} {'今日/上限':<10} {'累計次數':>8} {'估計費用':>10}")
        for r in rows:
            lim_s = f"{r['today_requests']}/{r['daily_limit'] or '∞'}"
            st = "啟用" if r["active"] else "停用"
            print(f"{r['code']:<14} {r['name']:<10} {st:<4} {lim_s:<10} {r['total_requests']:>8} {'$' + format(r['cost_usd'], '.3f'):>10}")
        total = sum(r["cost_usd"] for r in rows)
        print(f"\n全部估計費用：${total:.3f}（{_model}，以每百萬 token 輸入 ${PRICE_IN:g} / 輸出 ${PRICE_OUT:g}、每次上網搜尋 ${PRICE_SEARCH:g} 計算）")
    else:
        fn = {
            "disable": lambda: set_active(args.code, False),
            "enable": lambda: set_active(args.code, True),
            "delete": lambda: delete(args.code),
            "limit": lambda: set_limit(args.code, args.daily_limit),
        }[args.cmd]
        print("完成" if fn() else f"找不到邀請碼：{args.code}")


if __name__ == "__main__":
    main()
