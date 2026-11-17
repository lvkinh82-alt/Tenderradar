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

import base64
import re
import binascii
import html
import json
import os
import secrets
from datetime import date
from pathlib import Path
from typing import Any, Callable, Iterator, Literal

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

# Messages shown to users are bilingual (Chinese / English).
INVITE_ERRORS = {
    "missing": (401, "請先輸入邀請碼才能開始使用。 / Please enter your invite code to start."),
    "invalid": (401, "邀請碼不正確，請確認後重新輸入。 / That invite code isn't right. Please check it."),
    "disabled": (403, "這個邀請碼已停用，請聯絡提供邀請碼的人。 / This invite code has been turned off."),
    "limit": (429, "今天的使用次數已用完，明天再來吧！ / Today's limit is used up. Please try again tomorrow."),
}

# Live web search for "Ask AI" and the video assistant (billed per search on top of tokens).
# The basic tool version works on every current model, including Claude Haiku 5.5.
WEB_SEARCH_ON = os.environ.get("LIVE_TRANSLATE_WEB_SEARCH", "1") != "0"
WEB_TOOLS = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}]

SYSTEM_PROMPT = """You are a real-time interpreter embedded in a live translation app.
You receive one spoken or typed segment at a time and return ONLY its translation.

Rules:
- Output the translation text only: no quotes, notes, romanization, or explanations
  (plus the direction marker line when the message asks for one).
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

VISION_PROMPT = """You are the live video assistant inside Muối Từ, a translation app.
The user is pointing their phone camera at something and asking for help. You get the
current camera frame plus their question (transcribed from speech, so it may contain
recognition errors) and, sometimes, the last few questions and answers.

How to answer:
- Reply in the answer language given in the message, the user's own language.
- Your reply is read aloud: keep it short and practical, 1-4 sentences, plain text,
  no markdown. Use a short numbered sequence only when the user needs steps.
- Base the answer on what is actually visible. If something you need is blurry, cut off
  or too dark, say so and tell them how to adjust the camera.
- If relevant text in another language is in view, translate it.
- With no question, say what matters in the scene and translate any visible foreign text.
- Medicine, electricity, gas and similar risks: give the practical answer, add a one-line
  caution when there is real risk, and never guess a dosage you cannot read clearly;
  tell them to check with a pharmacist or doctor instead.
- If the question needs current information you can't see (price, where to buy, reviews,
  opening hours, what a product is), use web search. Don't announce the search and
  don't put URLs in the text; the app lists your sources."""

ASK_PROMPT = """You are the "Ask AI" helper inside Muối Từ, a translation app used by older people
and their families. Answer the user's question (transcribed from speech, so it may contain
recognition errors) helpfully and truthfully.

How to answer:
- Reply in the answer language given in the message.
- Your reply is read aloud: plain text, no markdown, no URLs, 1-5 short sentences.
  Use a short numbered sequence only when the user needs steps.
- Use web search whenever the answer depends on current or changing facts: news, prices,
  weather, opening hours, schedules, rules and laws, or anything you are not sure about.
  Don't search for stable knowledge, greetings or simple conversation.
- Don't announce that you are searching; the app shows that. Give the answer directly.
  The app lists your sources separately, so don't cite them in the text.
- If you can't find a reliable answer, say so plainly and suggest who to ask.
- Health, medicine, money and legal questions: give practical general information and
  suggest checking with a doctor, pharmacist or professional when it matters."""

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
    # Two-way conversation: translate into whichever of lang_a / lang_b the text is NOT in.
    # Speech recognition is often set to the wrong person's language, so the model decides.
    two_way: bool = False
    lang_a: str = ""
    lang_b: str = ""


class VisionTurn(BaseModel):
    question: str = Field("", max_length=2000)
    answer: str = Field("", max_length=4000)


class VisionRequest(BaseModel):
    image: str = Field(..., min_length=100, max_length=7_000_000)  # base64, no data: prefix
    media_type: Literal["image/jpeg", "image/png", "image/webp"] = "image/jpeg"
    question: str = Field("", max_length=2000)
    answer_lang: str = "Traditional Chinese"
    history: list[VisionTurn] = Field(default_factory=list, max_length=6)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    answer_lang: str = "Traditional Chinese"
    history: list[VisionTurn] = Field(default_factory=list, max_length=6)


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
    if req.two_way and req.lang_a and req.lang_b:
        parts.append(
            f"Two-way conversation.\nLanguage A: {req.lang_a}\nLanguage B: {req.lang_b}\n"
            "Decide which of the two languages the segment is in, judging from its words; speech "
            "recognition may have been set to the wrong language, so look past odd spellings to the meaning. "
            "Translate it into the other language.\n"
            "Start your reply with one line containing only @@A if you translated into Language A, "
            "or @@B if you translated into Language B, then the translation on the next line."
        )
    else:
        src = "auto-detect" if req.source_lang == "auto" else req.source_lang
        parts.append(f"Source language: {src}\nTarget language: {req.target_lang}")
    parts.append("Style: " + STYLES.get(req.style, STYLES["natural"]))
    parts.append("<segment>\n" + req.text.strip() + "\n</segment>")
    return "\n\n".join(parts)


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _collect_sources(content: list[Any], cited: dict[str, str], found: dict[str, str]) -> None:
    """Remember pages Claude cited and pages the search returned (cited ones are shown first)."""
    for block in content:
        if block.type == "text":
            for c in getattr(block, "citations", None) or []:
                if getattr(c, "url", None):
                    cited.setdefault(c.url, c.title or c.url)
        elif block.type == "web_search_tool_result" and isinstance(block.content, list):
            for r in block.content:
                if getattr(r, "url", None):
                    found.setdefault(r.url, r.title or r.url)


def stream_claude(
    system: str,
    user_message: str | list[dict[str, Any]],
    on_usage: Callable[[int, int, int], None] | None = None,
    tools: list[dict[str, Any]] | None = None,
    direction_marker: bool = False,
) -> Iterator[str]:
    tokens_in = tokens_out = searches = 0
    cited: dict[str, str] = {}
    found: dict[str, str] = {}
    messages: list[dict[str, Any]] = [{"role": "user", "content": user_message}]
    assistant_so_far: list[Any] = []
    # Two-way translation starts with "@@A" / "@@B": turn it into a "dir" event, never show it.
    marker_buf: str | None = "" if direction_marker else None

    def take_marker(final_flush: bool = False) -> Iterator[str]:
        nonlocal marker_buf
        buf = marker_buf or ""
        if not final_flush and "\n" not in buf and len(buf.strip()) < 12:
            return  # wait for more text
        marker_buf = None
        m = re.match(r"\s*@@([AB])[ \t]*\n?", buf)
        if m:
            yield sse("dir", {"to": m.group(1)})
            buf = buf[m.end():].lstrip("\n")
        if buf:
            yield sse("delta", {"text": buf})

    try:
        for _ in range(3):  # a web-search turn can pause; resume it up to twice
            params: dict[str, Any] = dict(
                model=MODEL,
                max_tokens=4000,
                system=system,
                output_config={"effort": EFFORT},
                messages=messages,
            )
            if tools:
                params["tools"] = tools
            if MODEL in FALLBACK_MODELS:
                stream_ctx = client().beta.messages.stream(
                    **params, betas=["server-side-fallback-2026-07-01"], fallbacks="default"
                )
            else:
                stream_ctx = client().messages.stream(**params)
            with stream_ctx as stream:
                for event in stream:
                    if event.type == "text":
                        if marker_buf is not None:
                            marker_buf += event.text
                            yield from take_marker()
                        else:
                            yield sse("delta", {"text": event.text})
                    elif event.type == "content_block_start" and event.content_block.type == "server_tool_use":
                        yield sse("status", {"kind": "search", "query": ""})
                    elif event.type == "content_block_stop" and event.content_block.type == "server_tool_use":
                        query = event.content_block.input.get("query", "") if isinstance(event.content_block.input, dict) else ""
                        yield sse("status", {"kind": "search", "query": query})
                final = stream.get_final_message()
            u = final.usage
            tokens_in += u.input_tokens + (u.cache_creation_input_tokens or 0) + (u.cache_read_input_tokens or 0)
            tokens_out += u.output_tokens
            searches += getattr(getattr(u, "server_tool_use", None), "web_search_requests", 0) or 0
            _collect_sources(final.content, cited, found)
            if final.stop_reason != "pause_turn":
                break
            # send the paused turn back unchanged; the API resumes where it stopped
            assistant_so_far = assistant_so_far + list(final.content)
            messages = [messages[0], {"role": "assistant", "content": assistant_so_far}]
        if marker_buf is not None:
            yield from take_marker(final_flush=True)
        sources = cited or found  # what the answer relied on; otherwise what was searched
        if sources:
            yield sse("sources", {"items": [{"url": k, "title": v} for k, v in list(sources.items())[:5]]})
        if final.stop_reason == "refusal":
            yield sse("error", {"message": "AI 無法處理這個內容。 / The AI declined this request."})
        else:
            yield sse("done", {"stop_reason": final.stop_reason})
    except (anthropic.AuthenticationError, TypeError):
        # TypeError: SDK found no credentials at all (no key / token / profile).
        yield sse("error", {"message": "伺服器的 API 金鑰沒設定好。 / The server's API key is missing or invalid."})
    except anthropic.RateLimitError:
        yield sse("error", {"message": "太多人同時使用，請稍等再試。 / Too many requests, please try again shortly."})
    except anthropic.APIStatusError as e:
        yield sse("error", {"message": f"AI 服務出錯（{e.status_code}）。 / AI service error ({e.status_code}): {e.message}"})
    except anthropic.APIConnectionError:
        yield sse("error", {"message": "連不上 AI 服務，請檢查網路。 / Can't reach the AI service."})
    finally:
        # only count requests that actually used API credit, so server-side
        # failures don't eat into a friend's daily limit
        if on_usage and (tokens_in or tokens_out):
            on_usage(tokens_in, tokens_out, searches)


def sse_response(events: Iterator[str]) -> StreamingResponse:
    return StreamingResponse(
        events,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def gate(code: str | None) -> tuple[JSONResponse | None, Callable[[int, int, int], None] | None]:
    """Reject requests without a usable invite code; otherwise return a usage recorder."""
    if not REQUIRE_INVITE:
        return None, None
    res = invites.check(code)
    if res.status != "ok":
        status, message = INVITE_ERRORS[res.status]
        return JSONResponse({"error": res.status, "message": message}, status_code=status), None
    assert code is not None
    return None, lambda i, o, s: invites.record(code, i, o, s)


@app.post("/api/translate")
def translate(req: TranslateRequest, x_invite_code: str | None = Header(default=None)):
    denied, on_usage = gate(x_invite_code)
    if denied:
        return denied
    return sse_response(
        stream_claude(SYSTEM_PROMPT, build_user_message(req), on_usage, direction_marker=req.two_way)
    )


@app.post("/api/vision")
def vision(req: VisionRequest, x_invite_code: str | None = Header(default=None)):
    denied, on_usage = gate(x_invite_code)
    if denied:
        return denied
    try:
        raw = base64.b64decode(req.image, validate=True)
    except (binascii.Error, ValueError):
        return JSONResponse({"error": "bad_image", "message": "畫面資料損壞，請再試一次。 / The picture was damaged, please try again."}, status_code=400)
    if len(raw) > 3_500_000:  # API limit is 5 MB per image; the app sends ~100-300 KB
        return JSONResponse({"error": "image_too_large", "message": "畫面太大，請再試一次。 / The picture is too large, please try again."}, status_code=413)
    parts = []
    if req.history:
        turns = "\n".join(f"Q: {t.question}\nA: {t.answer}" for t in req.history[-4:])
        parts.append(f"<conversation_so_far>\n{turns}\n</conversation_so_far>")
    parts.append(f"Answer language: {req.answer_lang}")
    q = req.question.strip()
    parts.append(f"<question>\n{q}\n</question>" if q else "No question: describe what matters and translate visible foreign text.")
    content = [
        {"type": "image", "source": {"type": "base64", "media_type": req.media_type, "data": req.image}},
        {"type": "text", "text": "\n\n".join(parts)},
    ]
    return sse_response(stream_claude(VISION_PROMPT, content, on_usage, WEB_TOOLS if WEB_SEARCH_ON else None))


@app.post("/api/ask")
def ask(req: AskRequest, x_invite_code: str | None = Header(default=None)):
    """General question answering with live web search (the "Ask AI" function)."""
    denied, on_usage = gate(x_invite_code)
    if denied:
        return denied
    parts = []
    if req.history:
        turns = "\n".join(f"Q: {t.question}\nA: {t.answer}" for t in req.history[-4:])
        parts.append(f"<conversation_so_far>\n{turns}\n</conversation_so_far>")
    parts.append(f"Today's date: {date.today().isoformat()}\nAnswer language: {req.answer_lang}")
    parts.append(f"<question>\n{req.question.strip()}\n</question>")
    return sse_response(stream_claude(ASK_PROMPT, "\n\n".join(parts), on_usage, WEB_TOOLS if WEB_SEARCH_ON else None))


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
