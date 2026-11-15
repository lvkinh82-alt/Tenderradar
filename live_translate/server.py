"""LinguaLive - real-time speech translation server.

Browser captures speech (Web Speech API) -> this server streams the
translation back from Claude over Server-Sent Events.

Run:
    pip install -r live_translate/requirements.txt
    export ANTHROPIC_API_KEY=sk-ant-...
    python -m live_translate.server        # http://localhost:8765
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterator

import anthropic
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

MODEL = os.environ.get("LIVE_TRANSLATE_MODEL", "claude-opus-5-5")
EFFORT = os.environ.get("LIVE_TRANSLATE_EFFORT", "low")  # low = fastest
STATIC_DIR = Path(__file__).parent / "static"

SYSTEM_PROMPT = """You are a real-time interpreter embedded in a live translation app.
You receive one spoken or typed segment at a time and return ONLY its translation.

Rules:
- Output the translation text only: no quotes, notes, romanization, or explanations.
- Preserve meaning, tone, register and names; sound natural to a native speaker.
- Speech-recognition output may lack punctuation or contain small recognition errors;
  infer the intended meaning and add natural punctuation in the target language.
- Use the recent conversation context (if given) to keep terminology and pronouns consistent.
- If the segment is already in the target language, return it lightly cleaned up.
- If the segment is empty noise (e.g. "um", "uh"), return an empty string."""

app = FastAPI(title="LinguaLive")
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


def build_user_message(req: TranslateRequest) -> str:
    parts: list[str] = []
    if req.context:
        lines = [f"- {c.source} => {c.translation}" for c in req.context[-6:]]
        parts.append("<recent_context>\n" + "\n".join(lines) + "\n</recent_context>")
    if req.glossary.strip():
        parts.append("<glossary>\n" + req.glossary.strip() + "\n</glossary>")
    src = "auto-detect" if req.source_lang == "auto" else req.source_lang
    parts.append(f"Source language: {src}\nTarget language: {req.target_lang}")
    parts.append("<segment>\n" + req.text.strip() + "\n</segment>")
    return "\n\n".join(parts)


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def stream_translation(req: TranslateRequest) -> Iterator[str]:
    try:
        with client().beta.messages.stream(
            model=MODEL,
            max_tokens=4000,
            system=SYSTEM_PROMPT,
            output_config={"effort": EFFORT},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=[{"role": "user", "content": build_user_message(req)}],
        ) as stream:
            for text in stream.text_stream:
                yield sse("delta", {"text": text})
            final = stream.get_final_message()
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


@app.post("/api/translate")
def translate(req: TranslateRequest):
    return StreamingResponse(
        stream_translation(req),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/health")
def health():
    has_key = bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))
    return JSONResponse({"ok": True, "model": MODEL, "credentials": has_key})


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def main() -> None:
    import uvicorn

    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8765"))
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
