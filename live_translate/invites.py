"""Invite codes for Muối Từ: only people you give a code to can use your API credit.

Codes and usage live in a small SQLite file (default: live_translate/data/invites.db,
override with LIVE_TRANSLATE_DB). Manage them from the command line:

    python -m live_translate.invites add "阿明"                 # new code, no daily limit
    python -m live_translate.invites add "小美" --daily-limit 300
    python -m live_translate.invites list                       # usage + estimated cost
    python -m live_translate.invites disable MT-7K3Q-9XPA
    python -m live_translate.invites enable  MT-7K3Q-9XPA
    python -m live_translate.invites limit   MT-7K3Q-9XPA 500    # 0 = unlimited
    python -m live_translate.invites delete  MT-7K3Q-9XPA
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
# USD per million tokens, for the cost estimate in `list` (Claude Opus 5.5 by default).
PRICE_IN = float(os.environ.get("LIVE_TRANSLATE_PRICE_IN", "4"))
PRICE_OUT = float(os.environ.get("LIVE_TRANSLATE_PRICE_OUT", "20"))

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


def record(code: str, input_tokens: int = 0, output_tokens: int = 0, requests: int = 1) -> None:
    with _lock:
        db().execute(
            """INSERT INTO usage (code, day, requests, input_tokens, output_tokens) VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(code, day) DO UPDATE SET
                 requests = requests + excluded.requests,
                 input_tokens = input_tokens + excluded.input_tokens,
                 output_tokens = output_tokens + excluded.output_tokens""",
            (normalize(code), date.today().isoformat(), requests, input_tokens, output_tokens),
        )
        db().commit()


def add(name: str, daily_limit: int = 0) -> str:
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
                      COALESCE(SUM(CASE WHEN u.day = ? THEN u.requests END), 0) AS today_requests
               FROM invites i LEFT JOIN usage u ON u.code = i.code
               GROUP BY i.code ORDER BY i.created_at""",
            (today,),
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["cost_usd"] = (d["input_tokens"] * PRICE_IN + d["output_tokens"] * PRICE_OUT) / 1_000_000
        out.append(d)
    return out


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="python -m live_translate.invites", description="管理 Muối Từ 邀請碼")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add", help="新增邀請碼")
    a.add_argument("name", help="這個碼是給誰的（備註）")
    a.add_argument("--daily-limit", type=int, default=0, help="每天最多翻譯幾次，0 = 不限")
    sub.add_parser("list", help="列出所有邀請碼與用量")
    for cmd, h in [("disable", "停用"), ("enable", "重新啟用"), ("delete", "刪除（連同用量紀錄）")]:
        sub.add_parser(cmd, help=h).add_argument("code")
    lim = sub.add_parser("limit", help="修改每日上限")
    lim.add_argument("code")
    lim.add_argument("daily_limit", type=int)
    args = ap.parse_args(argv)

    if args.cmd == "add":
        code = add(args.name, args.daily_limit)
        print(f"已建立邀請碼：{code}  （{args.name}）")
        print("把這個碼傳給對方，請他在 App 或網頁的「設定 → 邀請碼」輸入。")
    elif args.cmd == "list":
        rows = report()
        if not rows:
            print("還沒有邀請碼。用：python -m live_translate.invites add \"名字\"")
            return
        print(f"{'邀請碼':<14} {'名字':<10} {'狀態':<4} {'今日/上限':<10} {'累計次數':>8} {'估計費用':>10}")
        for r in rows:
            lim_s = f"{r['today_requests']}/{r['daily_limit'] or '∞'}"
            st = "啟用" if r["active"] else "停用"
            print(f"{r['code']:<14} {r['name']:<10} {st:<4} {lim_s:<10} {r['total_requests']:>8} {'$' + format(r['cost_usd'], '.3f'):>10}")
        total = sum(r["cost_usd"] for r in rows)
        print(f"\n全部估計費用：${total:.3f}（以每百萬 token 輸入 ${PRICE_IN:g} / 輸出 ${PRICE_OUT:g} 計算）")
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
