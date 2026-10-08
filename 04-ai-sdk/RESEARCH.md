# Research: "AI SDK Python" on Vercel (as of 2026-10-08)

## Summary

Vercel now ships an official **AI SDK for Python**: the PyPI package `ai` (`import ai`), developed in `vercel-labs/ai-python`, currently `0.8.0` and in public beta. It uses AI Gateway as its default provider. It also includes an adapter (`ai.ui.ai_sdk`) that reads and writes the **AI SDK UI message stream**, which means a JS `useChat` frontend can talk to a Python backend without any custom protocol code. That adapter replaces the older pattern, where a FastAPI backend hand-wrote the stream protocol around the OpenAI SDK.

## What's available

### Official: AI SDK for Python (`ai`)
- [Vercel docs: AI SDK for Python with AI Gateway](https://vercel.com/docs/ai-gateway/sdks-and-apis/ai-sdk-python) (updated 2026-09-08). Covers `uv add ai`, `ai.get_model()`, `ai.stream()`, structured output, `@ai.tool` + `ai.Agent`, and file parts. Auth is `AI_GATEWAY_API_KEY`, or OIDC through `uv add "ai[vercel]"`.
- [ai-python.dev/docs](https://ai-python.dev/docs) is the SDK's own docs site: getting started, streaming, agents, tools, hooks, AI SDK UI, and testing.
- [github.com/vercel-labs/ai-python](https://github.com/vercel-labs/ai-python) is the source (Apache-2.0, about 190 stars, pushed 2026-10-07). The `examples/` folder has `agents/`, `models/`, `media/`, and `apps/`.
- [examples/apps/web_agent](https://github.com/vercel-labs/ai-python/tree/main/examples/apps/web_agent) is the official full-stack reference. It pairs a FastAPI backend (`ai[vercel]`) with a Vite + React frontend that uses `useChat` from `@ai-sdk/react` and AI Elements. The backend calls `ai.ui.ai_sdk.to_messages` and `to_sse`, and adds human-in-the-loop tool approval. It deploys as two **Vercel Services** declared in `vercel.json` (`services` + `rewrites`).
- [PyPI `ai`](https://pypi.org/project/ai/): `0.8.0` was released 2026-09-29. It requires Python >= 3.12 and depends on `httpx2`, `pydantic`, and `modelsdotdev`. Optional extras: `vercel` (adds `vercel-oidc`), `openai`, `anthropic`, `mcp`, and `otel`.
- [Releases](https://github.com/vercel-labs/ai-python/releases): roughly one minor release every week or two (0.4 to 0.8 shipped between July and September 2026), and most of them list **breaking changes**.

### AI Gateway from Python (other ways)
- [Python with AI Gateway: OpenAI and Anthropic SDKs](https://vercel.com/docs/ai-gateway/sdks-and-apis/python): use the OpenAI-compatible `https://ai-gateway.vercel.sh/v1` base URL with the regular `openai` or `anthropic` client.
- [AI Gateway OIDC auth](https://vercel.com/docs/ai-gateway/authentication-and-byok/oidc): run `vercel link` and `vercel env pull` to get a `VERCEL_OIDC_TOKEN`. The token is valid for 12 hours. Python examples are given for both `ai` and `openai`.
- [AI Gateway model list](https://vercel.com/ai-gateway/models/gpt-6-luna) (plus `GET https://ai-gateway.vercel.sh/v1/models`): `openai/gpt-6-luna` costs $0.10/$0.50 per 1M tokens, was released 2026-09-22, and supports tools and streaming.

### The older pattern: `useChat` frontend + hand-rolled Python stream
- [vercel-labs/ai-sdk-preview-python-streaming](https://github.com/vercel-labs/ai-sdk-preview-python-streaming) is the [AI SDK Python Streaming template](https://vercel.com/templates/python/ai-sdk-python-streaming). It's a Next.js app with `useChat` and a FastAPI backend in `api/index.py`. The backend formats the UI-message-stream SSE events itself (`start`, `text-delta`, `tool-input-*`) on top of `openai` + AI Gateway, and calls `vercel.oidc.get_vercel_oidc_token()` after a manual `set_headers` middleware.
- [vercel-labs/ai-sdk-flask](https://github.com/vercel-labs/ai-sdk-flask) is the [AI SDK with Flask template](https://vercel.com/templates/python/ai-sdk-with-flask): Flask plus `openai` plus `vercel`, with `set_headers(request.headers)` in `before_request`. Despite the name, it doesn't use the `ai` package.
- [FastAPI starter templates (KB)](https://vercel.com/kb/guide/build-with-a-fastapi-starter-template) lists the Next.js FastAPI Starter chatbot and the OpenAI Agents SDK + Sandbox template.
- [AI SDK UI stream protocol](https://ai-sdk.dev/docs/ai-sdk-ui/stream-protocol): custom backends must send SSE `data:` chunks and the header `x-vercel-ai-ui-message-stream: v1`, and end with `data: [DONE]`.

### Other packages with similar names (not the official SDK)
- [PyPI `vercel-ai-sdk`](https://pypi.org/project/vercel-ai-sdk/) (`0.0.1.dev10`, April 2026): an earlier "experimental, evaluation only" toolkit from the same Vercel author. Its last release came before the `ai` beta.
- [python-ai-sdk/sdk](https://github.com/python-ai-sdk/sdk) ("The Vercel AI SDK, in Python", community, last pushed 2026-02). Also community: PyPI [`ai-sdk-python`](https://pypi.org/project/ai-sdk-python/) and [`vercel-ai`](https://pypi.org/project/vercel-ai/).
- [PyPI `vercel`](https://pypi.org/project/vercel/) (`0.11.x`) is the Vercel platform SDK (Sandbox, Blob, cache, queues, workflow, OIDC). It has no AI module. It's covered by the [Python SDK beta changelog](https://vercel.com/changelog/vercel-python-sdk-in-beta).

## How it works on Vercel

1. **Zero-config FastAPI.** Vercel sees `fastapi` in `pyproject.toml` and picks up `app` from `main.py` (it also checks `app.py`, `index.py`, `server.py`, and the same names under `src/` or `app/`). The whole app becomes one Fluid Compute function ([FastAPI docs](https://vercel.com/docs/frameworks/backend/fastapi), [Python runtime](https://vercel.com/docs/functions/runtimes/python)). Python 3.12 is the default, and 3.13 and 3.14 are also available. Dependencies come from `pyproject.toml` + `uv.lock`. Streaming responses are on by default ([changelog](https://vercel.com/changelog/python-vercel-functions-now-have-streaming-enabled-by-default)).
2. **Model routing.** `ai.get_model("openai/gpt-6-luna")` turns an id with no `provider:` prefix into `gateway:openai/gpt-6-luna`. The `GatewayProvider` then streams over AI Gateway's native protocol (`https://ai-gateway.vercel.sh/v4/ai`), not the OpenAI-compatible endpoint. If no id is passed, `ai.get_model()` reads `AI_SDK_DEFAULT_MODEL`.
3. **Auth order** (from `ai/providers/ai_gateway/provider.py` in 0.8.0): use `AI_GATEWAY_API_KEY` if it's set. Otherwise, if `VERCEL == "1"` or `VERCEL_OIDC_TOKEN` is set, call `vercel.oidc.get_vercel_oidc_token()` (this needs the `ai[vercel]` extra). Otherwise send no auth, and `provider.is_configured()` returns `False`. The token is looked up again each time the client is accessed, so rotation works.
4. **Where the OIDC token comes from in Python.** For each request, the Vercel Python runtime ([`vercel_runtime/headers.py`](https://github.com/vercel/vercel/blob/main/python/vercel-runtime/src/vercel_runtime/headers.py), `vc_init.py`) adds an `x-vercel-oidc-token` header. It uses the internal header or the `VERCEL_OIDC_TOKEN` env var, then calls `vercel.headers.set_headers(...)`, which sets a ContextVar. `vercel.oidc.get_vercel_oidc_token()` reads that ContextVar, falls back to the `VERCEL_OIDC_TOKEN` env var, and finally tries to refresh using `.vercel/` and the CLI token for local dev. Older templates call `set_headers` themselves in middleware; current runtimes do it automatically.
5. **UI streaming.** `ai.ui.ai_sdk.to_messages(ui_messages)` turns `useChat`'s `UIMessage[]` into `ai` messages and extracts tool approvals. `ai.ui.ai_sdk.to_sse(agent_stream)` turns agent events into `data: {...}\n\n` UI chunks followed by `data: [DONE]`. `UI_MESSAGE_STREAM_HEADERS` includes `x-vercel-ai-ui-message-stream: v1` and `x-accel-buffering: no`.

## Gotchas

- **Package name confusion.** The official package is `ai` (`pip install ai`, `import ai`). It is *not* `vercel-ai-sdk`, `ai-sdk-python`, or `vercel-ai`. The repo used to be `vercel-labs/py-ai`, and the old URL still redirects.
- **This is not a 1:1 port of the TypeScript API.** There's no `generate_text` or `stream_text`. `ai.stream()` is an async context manager that always streams. For the full text, drain the stream and read `stream.text` / `stream.usage`, or call `ai.experimental_generate()`. Tool loops use `ai.Agent(tools=[...]).run(model, messages)`. There's no `system=` argument, so prepend `ai.system_message(...)`.
- **Beta churn.** Minor releases include breaking changes, so rely on `uv.lock`. Every API used in this demo was checked against the installed 0.8.0 source.
- **OIDC needs the `[vercel]` extra.** Without it, the gateway raises `InstallationError` when it tries OIDC. `vercel dev -L` (unlinked) doesn't set `VERCEL=1`, so locally you need `AI_GATEWAY_API_KEY` or a pulled `VERCEL_OIDC_TOKEN`, which expires after 12 hours.
- **Errors after streaming starts.** Once `StreamingResponse` has sent `200`, the status can't change. `to_sse` doesn't catch provider errors, so the app has to emit `{"type":"error","errorText":...}` itself. Errors from `agent.run` arrive wrapped in an `ExceptionGroup` (the loop runs in a TaskGroup); unwrap it to get a readable message such as `AI Gateway authentication failed: Invalid API key.`
- **Wire detail (0.8.0).** For client-side `@ai.tool`s, the adapter emits `tool-input-start`, then `tool-input-delta` (the full JSON args), then `tool-output-available`. It does not emit `tool-input-available` (seen with `ai.testing.FakeModel`, and it matches `on_tool_result` in the source). `useChat` works with this because it parses the streamed input, but hand-written clients shouldn't wait for `tool-input-available`. The `finish` chunk carries `messageMetadata.aiPython.sourceMessages`, which is used to round-trip history.
- **New models work.** The SDK resolves metadata from a bundled models.dev snapshot (`modelsdotdev`), but gateway ids that aren't in the snapshot (for example `openai/gpt-6-luna`) still resolve and route.
- **Tooling.** The SDK uses `httpx2`, not `httpx`, so Starlette's `TestClient` (which needs `httpx`) isn't installed. For tests, `ai.testing.FakeModel` replays scripted conversations with no network.

## Approach chosen for this demo

**A single zero-config FastAPI app on the official `ai[vercel]` package, plus one static HTML page.**

- **Why `ai` rather than the OpenAI SDK pointed at the gateway:** it's Vercel's official AI SDK for Python, its docs live under the AI Gateway docs, and AI Gateway with OIDC works with no code. It also includes the AI SDK UI adapter, which is the whole point of an "AI SDK" demo.
- **What it shows:** generation (`/api/generate`), raw token streaming (`/api/stream`), and an agent with one tool whose output is an AI SDK UI message stream (`/api/chat`). Together these cover `ai.stream`, `ai.Agent`, `@ai.tool`, and `ai.ui.ai_sdk` in about 120 lines.
- **Why not Next.js or Vite + `useChat`:** the official full-stack example needs Vercel Services, a Node build, and about 40 frontend files. The goal here is to show the Python side. The protocol is plain SSE, so `index.html` parses it in about 30 lines of vanilla JS and prints the raw chunks. The README shows the `useChat` transport line for real apps.
- **Model:** `openai/gpt-6-luna`. It's one of the cheapest current models on AI Gateway, and you can override it with `AI_SDK_DEFAULT_MODEL` without changing code.
- **Credentials:** the app calls `MODEL.provider.is_configured()` up front, so a missing credential returns a clear `503` before any streaming starts. Provider and OIDC errors come back as a `502` (generate), an inline `[error]` line (text stream), or a protocol `error` chunk (chat).
