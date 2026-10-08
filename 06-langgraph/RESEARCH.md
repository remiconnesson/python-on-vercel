# Research: LangGraph (Python) on Vercel

Researched 2026-10-08. Versions current on that date: `langgraph` 1.2.14, `langchain` 1.4.3, `langchain-core` 1.6.7, `langchain-openai` 1.6.7, `fastapi` 0.143.0, `vercel` (Python SDK) 0.11.6. This demo locks versions about two days older (`langgraph` 1.2.13, `fastapi` 0.142.2, `vercel` 0.11.4) because the local uv config sets `exclude-newer = "2 days"`.

## What's available

**Vercel docs (official)**
- [LangChain with AI Gateway](https://vercel.com/docs/ai-gateway/ecosystem/framework-integrations/langchain): `ChatOpenAI` pointed at `https://ai-gateway.vercel.sh/v1`, using `AI_GATEWAY_API_KEY` or `VERCEL_OIDC_TOKEN`. The walkthrough is in TypeScript.
- [AI Gateway ecosystem](https://vercel.com/docs/ai-gateway/ecosystem): has the Python version, `ChatOpenAI(model=..., api_key=os.getenv("AI_GATEWAY_API_KEY"), base_url="https://ai-gateway.vercel.sh/v1")`.
- [AI Gateway OIDC authentication](https://vercel.com/docs/ai-gateway/authentication-and-byok/oidc): use the OIDC token as the bearer token. Pulled tokens last 12h locally (`vercel env pull`). The guide says to read the token at request time in long-running processes.
- [Chat Completions tool calling](https://vercel.com/docs/ai-gateway/sdks-and-apis/openai-chat-completions/tool-calling): Python `openai` client example with `tools=`, routed through AI Gateway (`AI_GATEWAY_API_KEY or VERCEL_OIDC_TOKEN`).
- [Deploy a FastAPI app on Vercel](https://vercel.com/docs/frameworks/backend/fastapi): zero-config entrypoints (`app.py`, `index.py`, `server.py`, `main.py`, ...), `tool.vercel.entrypoint`, lifespan (500 ms shutdown budget), and the 500 MB bundle limit (5 GB with Large Functions).
- [Python runtime](https://vercel.com/docs/functions/runtimes/python) and [Python version](https://vercel.com/docs/functions/runtimes/python/python-version): Python 3.12 (default), 3.13, and 3.14. Dependencies come from `pyproject.toml`/`uv.lock`. Streaming is supported.
- [Changelog: Python streaming on by default](https://vercel.com/changelog/python-vercel-functions-now-have-streaming-enabled-by-default): no flag needed since Jan 2025.
- [Fluid compute](https://vercel.com/docs/fluid-compute) and [max duration](https://vercel.com/docs/functions/configuring-functions/duration): instances are reused, Python gets in-function concurrency, and the default duration is 300s (Pro/Enterprise can go to 800s, or 1800s in beta).
- [Vercel Sandbox + LangChain](https://vercel.com/docs/sandbox/ecosystem/langchain): a `createAgent` agent with a sandboxed code tool and models through AI Gateway (TypeScript).
- [FastAPI starter templates](https://vercel.com/kb/guide/build-with-a-fastapi-starter-template): FastAPI boilerplate, Next.js+FastAPI, OpenAI Agents SDK + Sandbox. **None uses LangChain or LangGraph.**
- [AI Gateway model list API](https://ai-gateway.vercel.sh/v1/models) and the [gpt-5.4-nano page](https://vercel.com/ai-gateway/models/gpt-5.4-nano/api): `openai/gpt-5.4-nano` costs $0.20/$1.25 per 1M tokens.

**Vercel source / SDKs**
- [`vercel` Python SDK on PyPI](https://pypi.org/project/vercel/): `vercel.oidc` handles token lookup, refresh, and decoding. Its OIDC code ships as the `vercel-oidc` package ([PyPI JSON](https://pypi.org/pypi/vercel-oidc/json)).
- [vercel_runtime/headers.py](https://github.com/vercel/vercel/blob/main/python/vercel-runtime/src/vercel_runtime/headers.py) and [vc_init.py](https://github.com/vercel/vercel/blob/main/python/vercel-runtime/src/vercel_runtime/vc_init.py): the Python runtime appends `x-vercel-oidc-token` to the ASGI scope headers (taken from an internal header or `VERCEL_OIDC_TOKEN`) and calls `vercel.headers.set_headers(...)` on every request.
- [`@ai-sdk/langchain`](https://github.com/vercel/ai/tree/main/packages/langchain) and [examples/next-langchain](https://github.com/vercel/ai/tree/main/examples/next-langchain): convert LangGraph streams into AI SDK `UIMessageStream` for `useChat`. TypeScript only.

**LangChain docs**
- [LangGraph streaming](https://docs.langchain.com/oss/python/langgraph/streaming): `astream(stream_mode=[...], version="v2")` yields `{"type","ns","data"}` parts and needs LangGraph 1.1 or later. `messages` mode yields `(chunk, metadata)` and `updates` mode yields `{node: update}`.
- [LangGraph event streaming](https://docs.langchain.com/oss/python/langgraph/event-streaming): `stream_events(..., version="v3")` gives typed projections (`stream.messages`, `stream.values`, ...). It is new in LangGraph 1.2 and the docs recommend it for new in-process code.
- [Persistence](https://docs.langchain.com/oss/python/langgraph/persistence): `InMemorySaver` loses state on restart. Use `PostgresSaver` in production and keep `thread_id` under 255 characters.
- [LangChain agents (`create_agent`)](https://docs.langchain.com/oss/python/langchain/agents) and the [LangGraph quickstart](https://docs.langchain.com/oss/python/langgraph/quickstart): the high-level agent factory versus a hand-built `StateGraph` with an LLM node, a tool node, and a conditional edge.
- [langgraph-checkpoint-postgres](https://pypi.org/project/langgraph-checkpoint-postgres/): `PostgresSaver` / `AsyncPostgresSaver`. Call `.setup()` once. It needs `autocommit=True` and `row_factory=dict_row`.
- [langgraph-checkpoint-redis](https://pypi.org/project/langgraph-checkpoint-redis/): `RedisSaver` with TTL support. **Requires Redis 8+ or Redis Stack (RedisJSON + RediSearch).**

**Community**
- [langchain-vercel-ai-sdk-adapter](https://pypi.org/project/langchain-vercel-ai-sdk-adapter/): a third-party Python package that turns LangChain/LangGraph streams into the AI SDK UI message SSE protocol.
- [FastAPI SSE](https://fastapi.tiangolo.com/tutorial/server-sent-events/): built-in `EventSourceResponse` / `ServerSentEvent` since FastAPI 0.135, with automatic 15s keep-alive pings.
- Search results with no Vercel-specific code: [agent-service-toolkit](https://awesome.ecosyste.ms/projects/github.com%2Fjoshuac215%2Fagent-service-toolkit) (LangGraph + FastAPI + Streamlit), [langserve](https://github.com/langchain-ai/langserve), and a [LangChain forum thread on self-hosting](https://forum.langchain.com/t/can-i-deploy-a-langgraph-agent-myself-on-a-vps-or-aws/1950). The [machinelearningplus LangGraph+FastAPI article](https://machinelearningplus.com/gen-ai/langgraph-project-fullstack-ai-application-fastapi/) is a full-stack tutorial.

**Bottom line:** no official Vercel template or guide covers LangGraph in Python. Everything needed is documented separately: FastAPI zero-config, AI Gateway via `ChatOpenAI`, and OIDC via `vercel.oidc`.

## How it works on Vercel

1. **Detection and build.** `fastapi` in `pyproject.toml` plus an `app` in `main.py` selects the FastAPI preset. Vercel installs with uv from `uv.lock` and bundles the whole app as **one** Vercel Function. The bundle is about 64 MB, well under the 500 MB limit.
2. **Requests.** Every path goes to the ASGI app. The compiled graph and the `InMemorySaver` are module globals, so they are built once per instance at cold start. Fluid compute reuses that instance across requests, including concurrent ones.
3. **Streaming.** Python responses stream by default. FastAPI's `EventSourceResponse` writes each `ServerSentEvent` as `astream` yields it. I measured tokens arriving about 50 ms apart in a local test with a mock gateway.
4. **AI Gateway auth.**
   - On Vercel, the runtime puts `x-vercel-oidc-token` on each request and registers the headers with `vercel.headers`. `vercel.oidc.aio.get_vercel_oidc_token()` reads that context first, then the `VERCEL_OIDC_TOKEN` env var. If the token is missing or expired and a `.vercel/` link plus a CLI login exist, it refreshes the token locally.
   - The demo passes an **async** callable as `ChatOpenAI(api_key=...)`. The OpenAI client calls it before **every** request, so each LLM call uses the current request's token. `AI_GATEWAY_API_KEY` takes precedence when it is set.
5. **Duration.** The default is 300s with Fluid compute, which is plenty for a short agent loop. Longer loops need `maxDuration` in `vercel.json` keyed on `main.py`, or Vercel Workflow (see demo 07).

## Gotchas

- **`InMemorySaver` is per instance and never evicts.** A thread survives only while requests land on the same warm instance. A cold start, a redeploy, scale-out, or another region loses it. Memory also grows without limit. Use Postgres (for example Neon from the Marketplace) for real conversations. `langgraph-checkpoint-redis` needs RedisJSON + RediSearch, so check that your Redis provider has both modules.
- **Read the OIDC token per request, never at import time.** On Vercel it arrives as a request header. Locally a pulled token expires after 12h.
- **Prefer an async `api_key` callable.** `langchain-openai` runs a *sync* callable through `loop.run_in_executor`, which does not copy contextvars, so the request-header context may be missing there. This is from reading `_resolve_sync_and_async_api_keys` in `langchain_openai/chat_models/_client_utils.py`.
- **With SSE, the 200 status goes out before the graph runs.** Check credentials in a FastAPI dependency, which runs before the response starts, and report later failures as `event: error`.
- **GPT-6 models reject `tools` on Chat Completions.**
  - A third-party gateway's docs report this ([apiyi](https://docs.apiyi.com/en/api-capabilities/gpt-6-astra/overview.md)). `langchain-openai` also switches to the Responses API for names starting with `gpt-6` when tools are bound.
  - Through AI Gateway the model id is `openai/gpt-6-...`, so that switch does not happen. Use `openai/gpt-5.4-nano` or another model that supports Chat Completions tools, or set `use_responses_api=True`.
  - For GPT-5.4, don't set `reasoning_effort` together with tools on Chat Completions (per search results; [OpenAI model page](https://developers.openai.com/api/docs/models/gpt-5.4-nano) says the default effort is `none`).
- **`ChatOpenAI` targets the official OpenAI spec.** It drops non-standard response fields that a provider adds through the gateway, such as reasoning text.
- **`stream_mode="messages"` also emits `ToolMessage`s** returned by tool nodes. Filter on `AIMessageChunk` to get LLM tokens only.
- **The default `astream` output is still v1**, whose shape changes with the number of modes and subgraphs. Pass `version="v2"` for a stable `{"type","ns","data"}` shape.
- **Some blog posts say Python functions time out after 10s.** That is out of date. The default is 300s with Fluid compute.
- **FastAPI shutdown gets 500 ms**, so don't depend on lifespan teardown to flush a checkpointer.

## Approach chosen for this demo

- **A hand-built two-node `StateGraph`** (`agent` <-> `ToolNode`, routed by `tools_condition`) instead of `create_agent`. It shows the LangGraph primitives (state, nodes, a conditional edge, a checkpointer) in about 10 lines and needs only `langgraph` and `langchain-core`, not the `langchain` package. `create_agent(model, tools, checkpointer=...)` would replace those lines and is mentioned here as the high-level alternative.
- **`astream(stream_mode=["messages", "updates"], version="v2")` mapped to SSE events** (`thread`, `token`, `update`, `error`, `done`). This shows both token streaming and graph progress. Event streaming v3 is newer, but stream modes map one-to-one onto SSE and are the more widely documented API. FastAPI's native `EventSourceResponse` removes the need for `sse-starlette` and adds keep-alive pings.
- **AI Gateway through `ChatOpenAI(base_url=...)`**, the Vercel-documented path. LangChain has no dedicated AI Gateway integration in its provider list. The default model is `openai/gpt-5.4-nano`: cheap, released March 2026, tools supported on Chat Completions, and no reasoning by default, so tokens stream quickly. Override it with `AI_GATEWAY_MODEL`.
- **Credentials:** `AI_GATEWAY_API_KEY` first, otherwise `vercel.oidc`. The same async function is both the FastAPI dependency (fails fast with a clear 500) and the `api_key` provider, so deployments need no secrets.
- **Zero config:** no `vercel.json`. The defaults cover duration and streaming.
