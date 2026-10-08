# 04 · AI SDK for Python on Vercel

A FastAPI app built on the official **AI SDK for Python** (PyPI package [`ai`](https://pypi.org/project/ai/), public beta, from [vercel-labs/ai-python](https://github.com/vercel-labs/ai-python)). It shows text generation, token streaming, and an agent with one tool, all going through **Vercel AI Gateway**. `/api/chat` speaks the **AI SDK UI message stream** protocol, so a `useChat` frontend can use it directly. On Vercel the SDK authenticates with the deployment's **OIDC token**, so you don't need an API key. See [RESEARCH.md](./RESEARCH.md) for the background.

## Files

```
04-ai-sdk/
├── main.py         # FastAPI app: ai.stream, ai.Agent + @ai.tool, ai.ui.ai_sdk.to_sse
├── index.html      # the visual explainer served at `/`: calls every route live, parses /api/chat's SSE by hand
├── pyproject.toml  # deps: ai[vercel] (the [vercel] extra adds OIDC auth), fastapi; uvicorn is a dev-only dependency
├── uv.lock         # locked dependency versions
└── RESEARCH.md     # what exists and why this approach
```

## Endpoints

| Route | What it shows |
| --- | --- |
| `GET /` | The visual explainer page (see below) |
| `GET /api` | JSON with the model id, the installed `ai` version, which credential was detected, and the endpoint list |
| `GET /api/generate?prompt=` | `ai.stream(...)` read to the end, returned as JSON (`text`, `usage`, `finish_reason`, `response_model`, `model_ms`) |
| `GET /api/stream?prompt=` | `TextDelta` chunks streamed as `text/plain` |
| `POST /api/chat` | `ai.Agent` with a `get_weather` tool, sent as an AI SDK UI message stream (SSE, `x-vercel-ai-ui-message-stream: v1`) |

## Run locally

```bash
uv sync
export AI_GATEWAY_API_KEY=...   # Vercel dashboard > AI Gateway > API Keys
uv run uvicorn main:app --reload
# open http://127.0.0.1:8000
```

You can use OIDC instead of a key: once the project is linked, run `vercel env pull`, then `uv run --env-file .env.local uvicorn main:app`. The token lasts 12 hours, so run `vercel env pull` again when it expires. `vercel dev -L` also works without linking, but it still needs `AI_GATEWAY_API_KEY`.

With no credential, the AI routes return a `503` that explains how to set one.

## Deploy (Vercel)

- **Framework preset:** FastAPI. Zero-config: Vercel detects `fastapi` in `pyproject.toml` and serves `app` from `main.py`. There's no `vercel.json`.
- **Root Directory:** `04-ai-sdk`. Leave the build and install commands at their defaults (uv + `uv.lock`).
- **Env vars:** none required. AI Gateway uses the deployment's OIDC token. The SDK enables OIDC when `VERCEL=1`, and the Python runtime passes the per-request `x-vercel-oidc-token` header to `vercel.oidc`. The team needs AI Gateway credits.
- **Optional env vars:** `AI_SDK_DEFAULT_MODEL` changes the model (the default is `openai/gpt-6-luna`; any [AI Gateway model id](https://vercel.com/ai-gateway/models) works). `AI_GATEWAY_API_KEY` uses a key instead of OIDC.

## Try it

```bash
BASE=http://127.0.0.1:8000   # or your deployment URL

curl $BASE/api
curl "$BASE/api/generate?prompt=Why%20is%20the%20sky%20blue%3F"
curl -N "$BASE/api/stream?prompt=Write%20a%20haiku%20about%20Python"
curl -N $BASE/api/chat -H 'content-type: application/json' -d '{
  "messages": [{"id": "1", "role": "user", "parts": [{"type": "text", "text": "What is the weather in Paris?"}]}]
}'
```

Open the deployment in a browser for a live explainer. On load it calls only `GET /api` (no model call) to show the model, SDK version, credential source and function region. Its buttons then call the model routes: `/api/chat` is read by a hand-written `useChat`-style client that shows each SSE event in an ordered log with arrival times, a lane timeline of the agent's steps, and the tool call and reply as a chat UI would render them; `/api/stream` is plotted chunk by chunk; `/api/generate` shows token usage and timing. Locally without a credential, each model route shows its `503` message.

`/api/chat` streams `data: {...}` events: `start`, `text-delta`, `tool-input-start`/`tool-input-delta`, `tool-output-available`, `finish`, and then `data: [DONE]`. To use it from React, point `useChat({ transport: new DefaultChatTransport({ api: "/api/chat" }) })` at it.
