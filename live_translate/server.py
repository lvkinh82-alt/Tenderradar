"""Muối Từ (Phiên Dịch AI) - real-time speech translation server.

Browser captures speech (Web Speech API) -> this server streams the
translation back from Claude over Server-Sent Events.

Run:
    pip3 install -r live_translate/requirements.txt
    export ANTHROPIC_API_KEY=sk-ant-...
    python3 -m live_translate.invites add "名字"   # create an invite code first
    python3 -m live_translate.server        # http://localhost:8765

Every translation needs a valid invite code (header X-Invite-Code), so only the
people you give a code to spend your API credit. Set LIVE_TRANSLATE_REQUIRE_INVITE=0
to turn the check off (e.g. for purely local use).
"""

from __future__ import annotations

import html
import json
import os
import secrets
from pathlib import Path
from typing import Callable, Iterator

import anthropic
from fastapi import FastAPI, Header
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import invites

MODEL = os.environ.get("LIVE_TRANSLATE_MODEL", "claude-opus-5-5")
EFFORT = os.environ.get("LIVE_TRANSLATE_EFFORT", "low")  # low = fastest
STATIC_DIR = Path(__file__).parent / "static"
# Models that accept the server-side refusal fallback. Others (e.g. claude-haiku-5-5)
# reject the parameter, so they are called without it.
FALLBACK_MODELS = {"claude-fable-5-2", "claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5"}
REQUIRE_INVITE = os.environ.get("LIVE_TRANSLATE_REQUIRE_INVITE", "1") != "0"

INVITE_ERRORS = {
    "missing": (401, "請先輸入邀請碼才能開始翻譯。"),
    "invalid": (401, "邀請碼不正確，請確認後重新輸入。"),
    "disabled": (403, "這個邀請碼已停用，請聯絡提供邀請碼的人。"),
    "limit": (429, "今天的翻譯次數已用完，明天再來吧！"),
}

SYSTEM_PROMPT = """You are a real-time interpreter embedded in a live translation app.
You receive one spoken or typed segment at a time and return ONLY its translation.

Rules:
- Output the translation text only: no quotes, notes, romanization, or explanations.
- Preserve meaning, tone, register and names; sound natural to a native speaker.
- Speech-recognition output may lack punctuation or contain small recognition errors;
  infer the intended meaning and add natural punctuation in the target language.
- Use the recent conversation context (if given) to keep terminology and pronouns consistent.
- If the segment is already in the target language, return it lightly cleaned up.
- If the segment is empty noise (e.g. "um", "uh"), return an empty string.
- Internet slang, memes and idioms: translate the meaning and the vibe, choosing an
  equivalent expression a native speaker would actually use, not a literal rendering.
- Follow the requested style when one is given."""

STYLES = {
    "natural": "Natural, faithful translation in a neutral register.",
    "casual": "Casual and friendly, like texting a friend. Contractions and everyday words are fine.",
    "formal": "Formal and polite, suitable for business email or official communication.",
    "social": "Native social-media voice: the slang, abbreviations and emoji habits a young native "
              "speaker would use on TikTok / Instagram / X. Keep it short and punchy.",
    "business": "Professional business register; precise terminology, concise.",
}

EXPLAIN_PROMPT = """You are a friendly language coach. The user saw a sentence and its translation.
Explain, in the requested explanation language, briefly and in plain text (no markdown headings):
1. Any slang, idioms, memes, abbreviations or cultural references in the original, and what they really mean.
2. Tone / vibe of the original (e.g. joking, sarcastic, polite, flirty).
3. One or two alternative ways to say it in the target language, with when to use each.
Keep it under 150 words. If there is nothing notable, say so in one sentence and give the alternatives."""

app = FastAPI(title="Muối Từ · Phiên Dịch AI")
_client: anthropic.Anthropic | None = None


def client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


class ContextPair(BaseModel):
    source: str
    translation: str


class TranslateRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=8000)
    source_lang: str = "auto"
    target_lang: str
    context: list[ContextPair] = Field(default_factory=list, max_length=10)
    glossary: str = Field("", max_length=4000)
    style: str = "natural"


class ExplainRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)
    translation: str = Field("", max_length=8000)
    target_lang: str
    explain_lang: str = "Traditional Chinese"


def build_user_message(req: TranslateRequest) -> str:
    parts: list[str] = []
    if req.context:
        lines = [f"- {c.source} => {c.translation}" for c in req.context[-6:]]
        parts.append("<recent_context>\n" + "\n".join(lines) + "\n</recent_context>")
    if req.glossary.strip():
        parts.append("<glossary>\n" + req.glossary.strip() + "\n</glossary>")
    src = "auto-detect" if req.source_lang == "auto" else req.source_lang
    parts.append(f"Source language: {src}\nTarget language: {req.target_lang}")
    parts.append("Style: " + STYLES.get(req.style, STYLES["natural"]))
    parts.append("<segment>\n" + req.text.strip() + "\n</segment>")
    return "\n\n".join(parts)


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def stream_claude(
    system: str, user_message: str, on_usage: Callable[[int, int], None] | None = None
) -> Iterator[str]:
    tokens_in = tokens_out = 0
    try:
        params = dict(
            model=MODEL,
            max_tokens=4000,
            system=system,
            output_config={"effort": EFFORT},
            messages=[{"role": "user", "content": user_message}],
        )
        if MODEL in FALLBACK_MODELS:
            stream_ctx = client().beta.messages.stream(
                **params, betas=["server-side-fallback-2026-07-01"], fallbacks="default"
            )
        else:
            stream_ctx = client().messages.stream(**params)
        with stream_ctx as stream:
            for text in stream.text_stream:
                yield sse("delta", {"text": text})
            final = stream.get_final_message()
        tokens_in = final.usage.input_tokens + (final.usage.cache_creation_input_tokens or 0) + (
            final.usage.cache_read_input_tokens or 0
        )
        tokens_out = final.usage.output_tokens
        if final.stop_reason == "refusal":
            yield sse("error", {"message": "The model declined to translate this segment."})
        else:
            yield sse("done", {"stop_reason": final.stop_reason})
    except (anthropic.AuthenticationError, TypeError):
        # TypeError: SDK found no credentials at all (no key / token / profile).
        yield sse("error", {"message": "Invalid or missing ANTHROPIC_API_KEY on the server."})
    except anthropic.RateLimitError:
        yield sse("error", {"message": "Rate limited - please slow down and retry."})
    except anthropic.APIStatusError as e:
        yield sse("error", {"message": f"API error {e.status_code}: {e.message}"})
    except anthropic.APIConnectionError:
        yield sse("error", {"message": "Network error contacting the translation API."})
    finally:
        # only count requests that actually used API credit, so server-side
        # failures don't eat into a friend's daily limit
        if on_usage and (tokens_in or tokens_out):
            on_usage(tokens_in, tokens_out)


def sse_response(events: Iterator[str]) -> StreamingResponse:
    return StreamingResponse(
        events,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def gate(code: str | None) -> tuple[JSONResponse | None, Callable[[int, int], None] | None]:
    """Reject requests without a usable invite code; otherwise return a usage recorder."""
    if not REQUIRE_INVITE:
        return None, None
    res = invites.check(code)
    if res.status != "ok":
        status, message = INVITE_ERRORS[res.status]
        return JSONResponse({"error": res.status, "message": message}, status_code=status), None
    assert code is not None
    return None, lambda i, o: invites.record(code, i, o)


@app.post("/api/translate")
def translate(req: TranslateRequest, x_invite_code: str | None = Header(default=None)):
    denied, on_usage = gate(x_invite_code)
    if denied:
        return denied
    return sse_response(stream_claude(SYSTEM_PROMPT, build_user_message(req), on_usage))


@app.post("/api/explain")
def explain(req: ExplainRequest, x_invite_code: str | None = Header(default=None)):
    denied, on_usage = gate(x_invite_code)
    if denied:
        return denied
    msg = (
        f"<original>\n{req.text.strip()}\n</original>\n"
        f"<translation target=\"{req.target_lang}\">\n{req.translation.strip()}\n</translation>\n"
        f"Explanation language: {req.explain_lang}"
    )
    return sse_response(stream_claude(EXPLAIN_PROMPT, msg, on_usage))


@app.get("/api/health")
def health(x_invite_code: str | None = Header(default=None)):
    has_key = bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))
    body: dict = {"ok": True, "model": MODEL, "credentials": has_key, "invite_required": REQUIRE_INVITE}
    if REQUIRE_INVITE:
        res = invites.check(x_invite_code)
        body["invite"] = res.status
        if res.status in ("ok", "limit"):
            body["invite_name"] = res.name
            body["used_today"] = res.used_today
            body["daily_limit"] = res.daily_limit
        if res.status != "ok":
            body["invite_message"] = INVITE_ERRORS[res.status][1]
    return JSONResponse(body)


ADMIN_TOKEN = os.environ.get("LIVE_TRANSLATE_ADMIN_TOKEN", "")


@app.get("/admin")
def admin(token: str = ""):
    """Usage per invite code, for hosts without a terminal (e.g. Railway). Open /admin?token=..."""
    if not ADMIN_TOKEN:
        return HTMLResponse("管理頁未啟用：請設定 LIVE_TRANSLATE_ADMIN_TOKEN。", status_code=404)
    if not secrets.compare_digest(token.encode(), ADMIN_TOKEN.encode()):
        return HTMLResponse("密碼不正確。", status_code=403)
    rows = invites.report()
    total = sum(r["cost_usd"] for r in rows)
    trs = "".join(
        f"<tr><td><code>{html.escape(r['code'])}</code></td><td>{html.escape(r['name'])}</td>"
        f"<td>{'啟用' if r['active'] else '停用'}</td><td>{r['today_requests']} / {r['daily_limit'] or '∞'}</td>"
        f"<td>{r['total_requests']}</td><td>${r['cost_usd']:.4f}</td></tr>"
        for r in rows
    )
    page = f"""<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex">
<title>Muối Từ 用量</title><style>
body{{font:15px/1.5 system-ui,sans-serif;margin:0;padding:16px;background:#f6f7fb;color:#1b1f2a}}
h1{{font-size:18px}} .wrap{{overflow-x:auto}} table{{border-collapse:collapse;background:#fff;min-width:520px;width:100%}}
th,td{{padding:8px 10px;border-bottom:1px solid #e3e6ee;text-align:left;white-space:nowrap}} th{{color:#6b7385;font-weight:600}}
.sum{{margin-top:12px;color:#047857;font-weight:600}} .note{{color:#6b7385;font-size:13px}}
</style></head><body><h1>Muối Từ · 邀請碼用量</h1>
<div class="wrap"><table><tr><th>邀請碼</th><th>名字</th><th>狀態</th><th>今日 / 上限</th><th>累計次數</th><th>估計費用</th></tr>{trs}</table></div>
<div class="sum">全部估計費用：${total:.4f}</div>
<p class="note">模型：{html.escape(MODEL)}。實際帳單以 Anthropic Console 為準。</p></body></html>"""
    return HTMLResponse(page)


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


# PWA files must be served from the root so the service worker can control "/".
@app.get("/manifest.webmanifest")
def manifest():
    return FileResponse(STATIC_DIR / "manifest.webmanifest", media_type="application/manifest+json")


@app.get("/sw.js")
def service_worker():
    return FileResponse(STATIC_DIR / "sw.js", media_type="text/javascript")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def main() -> None:
    import uvicorn

    spec = os.environ.get("LIVE_TRANSLATE_INVITES", "").strip()
    if spec:
        entries = invites.sync_from_env(spec)
        print(f"已從 LIVE_TRANSLATE_INVITES 載入 {len(entries)} 個邀請碼：" + "、".join(n for n, _, _ in entries))
    if REQUIRE_INVITE and not invites.any_codes():
        print('提醒：還沒有任何邀請碼，所有翻譯都會被拒絕。先執行：./live_translate/invite.sh add "名字"（或 python3 -m live_translate.invites add "名字"）')
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8765"))
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
