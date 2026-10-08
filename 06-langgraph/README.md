# LangGraph on Vercel

A LangGraph agent with a two-node `StateGraph` (`agent` <-> `tools`, with one `multiply` tool), served by FastAPI as a single Vercel Function with no `vercel.json`. The model is called through [Vercel AI Gateway](https://vercel.com/docs/ai-gateway)'s OpenAI-compatible endpoint using `langchain-openai`. Locally it authenticates with `AI_GATEWAY_API_KEY`; on Vercel it uses the project's OIDC token, so no secret is needed. `POST /invoke` returns the final answer, and `POST /stream` streams LLM tokens and per-node updates as Server-Sent Events.

```
06-langgraph/
├── main.py         # the graph, the AI Gateway credential lookup, and the FastAPI routes
├── index.html      # the visual explainer served at `/` to browsers
├── pyproject.toml  # dependencies; Vercel detects FastAPI from them
├── uv.lock         # pinned versions, used by Vercel's uv-based install
├── README.md
└── RESEARCH.md     # sources, how it works on Vercel, gotchas, and why this design
```

Open the deployment in a browser for a live explainer: it streams a run and draws which graph node holds control, times each node, sends a follow-up on the same thread to show which instance answered and how many messages it still held, and compares the stream with `/invoke`. It only calls the model when you press a button. `curl` on `/` still gets JSON.

## Run locally

```bash
uv sync

# Option A: AI Gateway API key
AI_GATEWAY_API_KEY=... uv run uvicorn main:app --reload

# Option B: the project's OIDC token (valid for 12h; run `vercel env pull` again to refresh it)
vercel link && vercel env pull
uv run --env-file .env.local uvicorn main:app --reload
```

If neither credential is present, `POST /invoke` and `POST /stream` return a `500` with a message that says how to fix it. `GET /` works without a credential.

To use a different model, set `AI_GATEWAY_MODEL` (default `openai/gpt-5.4-nano`). Pick a model that supports tool calls on the Chat Completions API (see RESEARCH.md: GPT-6 models don't).

## Deploy

- Framework preset: **FastAPI**, which Vercel detects from the `fastapi` dependency and the `app` object in `main.py`. Set Root Directory to `06-langgraph`. Leave the build and install commands at their defaults.
- Environment variables: none required. On Vercel, the Python runtime adds an `x-vercel-oidc-token` header to every request, and `vercel.oidc` uses it to authenticate with AI Gateway. Optional: `AI_GATEWAY_MODEL`, or `AI_GATEWAY_API_KEY` if you want to use a key instead of OIDC.
- No `vercel.json`: with Fluid compute the default max duration is 300s and Python streaming is on by default. To allow longer agent runs, add `{"functions": {"main.py": {"maxDuration": 800}}}`.
- Memory is per instance. `InMemorySaver` keeps each thread in the RAM of one function instance. A `thread_id` usually carries over between requests because Fluid compute reuses warm instances, but a cold start, a redeploy, or a request that lands on another instance starts a new conversation. For durable threads, use `langgraph-checkpoint-postgres`.

## Try it

```bash
URL=http://localhost:8000   # or https://<your-deployment>.vercel.app

curl $URL/
# {"model": "openai/gpt-5.4-nano", "credential": "oidc", "region": "iad1", "instance_id": "...", ...}

curl -X POST $URL/invoke -H 'content-type: application/json' \
  -d '{"message": "What is 12.5 times 4?"}'
# {"thread_id": "...", "instance_id": "...", "prior_messages": 0, "answer": "...50...", "messages": [human, ai (tool_calls), tool, ai]}

curl -N -X POST $URL/stream -H 'content-type: application/json' \
  -d '{"message": "What is 12.5 times 4?", "thread_id": "demo-1"}'
# event: thread  data: {"thread_id": "demo-1", "instance_id": "...", "prior_messages": 0}
# event: update  data: {"node": "agent", "messages": [{"type": "ai", "tool_calls": [{"name": "multiply", ...}]}]}
# event: update  data: {"node": "tools", "messages": [{"type": "tool", "content": "50.0"}]}
# event: token   data: {"node": "agent", "text": "12.5"}   ... one event per token
# event: update  data: {"node": "agent", "messages": [{"type": "ai", "content": "..."}]}
# event: done    data: {}

# Continue the same conversation. This only works if the request reaches the same instance:
# the thread event then shows the same instance_id and prior_messages: 4.
curl -N -X POST $URL/stream -H 'content-type: application/json' \
  -d '{"message": "Now multiply that by 3", "thread_id": "demo-1"}'
```

If the model call fails after streaming has started, the stream sends `event: error` with the details, because the `200` status line has already gone out. `/invoke` returns the same failure as a `502` JSON response.
