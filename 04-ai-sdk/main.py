"""AI SDK for Python (the `ai` package) + FastAPI on Vercel.

Vercel finds `app` in main.py and deploys it as one Python Function (zero-config).
Models are called through Vercel AI Gateway, the SDK's default provider.
"""

import json
import os
from pathlib import Path

import ai
import pydantic
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse

# A model ID without a "provider:" prefix routes through AI Gateway.
# AI_SDK_DEFAULT_MODEL is the SDK's own env var for a default model.
MODEL = ai.get_model(os.getenv("AI_SDK_DEFAULT_MODEL", "openai/gpt-6-luna"))
SYSTEM = ai.system_message("You are a concise assistant. Answer in 1-3 sentences.")
INDEX_HTML = (Path(__file__).parent / "index.html").read_text()

app = FastAPI(title="AI SDK for Python on Vercel")


def require_credentials() -> None:
    # The gateway provider authenticates with AI_GATEWAY_API_KEY if set, otherwise
    # with the Vercel OIDC token (VERCEL=1 or VERCEL_OIDC_TOKEN, via `ai[vercel]`).
    if not MODEL.provider.is_configured():
        raise HTTPException(
            status_code=503,
            detail=(
                "No AI Gateway credentials. Locally: export AI_GATEWAY_API_KEY=... "
                "(Vercel dashboard > AI Gateway > API Keys), or load the VERCEL_OIDC_TOKEN "
                "from `vercel env pull`. On Vercel, OIDC is used automatically."
            ),
        )


def error_text(exc: BaseException) -> str:
    while isinstance(exc, BaseExceptionGroup):  # the agent loop runs in a TaskGroup
        exc = exc.exceptions[0]
    return str(exc)


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return INDEX_HTML


@app.get("/api")
def info() -> dict:
    return {
        "model": MODEL.id,
        "credentials": (
            "AI_GATEWAY_API_KEY" if os.getenv("AI_GATEWAY_API_KEY")
            else "Vercel OIDC" if MODEL.provider.is_configured()
            else None
        ),
        "endpoints": {
            "GET /api/generate?prompt=...": "full text as JSON",
            "GET /api/stream?prompt=...": "plain-text token stream",
            "POST /api/chat": "AI SDK UI message stream (SSE) for useChat, with a tool",
        },
    }


@app.get("/api/generate")
async def generate(prompt: str = "Why is the sky blue?") -> dict:
    require_credentials()
    try:
        # The SDK always streams; drain it, then read the assembled message.
        async with ai.stream(MODEL, [SYSTEM, ai.user_message(prompt)]) as stream:
            async for _ in stream:
                pass
    except Exception as exc:  # e.g. invalid key, unknown model, OIDC disabled
        raise HTTPException(status_code=502, detail=error_text(exc))
    return {"model": MODEL.id, "text": stream.text, "usage": stream.usage}


@app.get("/api/stream")
async def stream_text(prompt: str = "Write a haiku about Python.") -> StreamingResponse:
    require_credentials()

    async def chunks():
        try:
            async with ai.stream(MODEL, [SYSTEM, ai.user_message(prompt)]) as stream:
                async for event in stream:
                    if isinstance(event, ai.events.TextDelta):
                        yield event.chunk
        except Exception as exc:  # headers are already sent, so report inline
            yield f"\n[error] {error_text(exc)}\n"

    return StreamingResponse(chunks(), media_type="text/plain; charset=utf-8")


@ai.tool
async def get_weather(city: str) -> str:
    """Get the current weather for a city."""
    return f"Sunny and 22C in {city}"  # fake data keeps the demo self-contained


agent = ai.Agent(tools=[get_weather])  # runs the model <-> tool loop


class ChatRequest(pydantic.BaseModel):
    messages: list[ai.ui.ai_sdk.UIMessage]  # the body `useChat` sends


@app.post("/api/chat")
async def chat(request: ChatRequest) -> StreamingResponse:
    require_credentials()
    messages, _approvals = ai.ui.ai_sdk.to_messages(request.messages)

    async def sse():
        try:
            async with agent.run(MODEL, [SYSTEM, *messages]) as stream:
                # Agent events -> AI SDK UI message stream chunks ("data: {...}\n\n").
                async for chunk in ai.ui.ai_sdk.to_sse(stream):
                    yield chunk
        except Exception as exc:  # the protocol's error chunk; useChat surfaces it
            yield f"data: {json.dumps({'type': 'error', 'errorText': error_text(exc)})}\n\n"

    return StreamingResponse(sse(), headers=ai.ui.ai_sdk.UI_MESSAGE_STREAM_HEADERS)
