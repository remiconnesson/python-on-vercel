# 07 · LangGraph on Vercel Workflow

A LangGraph graph runs inside a durable Vercel Workflow, written with the Python SDK [`vercel-workflow`](https://pypi.org/project/vercel-workflow/) (beta). The graph is `write → review → END`, and loops back to `write` when the reviewer asks for changes. The `write` node calls the LLM through a `@wf.step`, so the call is retried on failure and its result is recorded. The `review` node pauses the run on a Workflow hook until a human approves over HTTP. The run uses no compute while it waits, and it survives restarts and redeploys.

There's no official LangGraph integration for Vercel Workflow, and no Workflow-backed LangGraph checkpointer. This demo uses the plain SDKs. [RESEARCH.md](./RESEARCH.md) covers what exists and why the demo is built this way.

Open the deployment (or `http://localhost:8000`) in a browser to get the explainer page. You start a run, watch where the graph is, approve the draft or send feedback, and see a log of every state change with the pause lengths the server measured. Browsers that ask for `text/html` at `/` get `index.html`; everything else gets the JSON listing. `main.py` reads the file once at import, so restart the server after editing it.

```
07-langgraph-workflow/
├── agent.py         # Workflows registry, LLM step, LangGraph graph, hook model, run_agent workflow
├── main.py          # FastAPI: GET /, POST /api/runs, GET /api/runs/{id}, POST /api/runs/{id}/approve
├── index.html       # Visual explainer served at GET / to browsers (vanilla JS, no build step)
├── pyproject.toml   # deps, [tool.vercel] web entrypoint, [[tool.vercel.workflows]] registry entrypoint
├── uv.lock          # locked deps (uv lock)
├── .gitignore       # ignores .venv and .workflow-data (local run storage)
└── RESEARCH.md      # sources, mechanics, gotchas, why this approach
```

## How it works

- **The workflow body runs the graph.** `run_agent` calls `graph.ainvoke(...)`. Workflow re-runs the body from the start every time the run wakes up, after a step finishes or a hook receives a payload. Steps and hooks that already completed return their recorded values right away, so LangGraph is back at the same point in a few milliseconds.
- **Side effects run in steps.** `generate()` (ChatOpenAI → AI Gateway) is a `@wf.step`. It runs as its own invocation in the regular interpreter, gets 3 retries, and its return value is stored in the run's event log.
- **The human-in-the-loop pause is a Workflow hook, not LangGraph's `interrupt()`.** `Approval.wait(token=...)` suspends the run, and `POST /api/runs/{id}/approve` calls `Approval(...).resume(token)`. The hook's `metadata` carries the draft and its number, so `GET /api/runs/{id}` can show them while the run waits.
- **There's no LangGraph checkpointer.** The Workflow event log is the persistence layer.

## Run locally

```bash
uv sync
FAKE_LLM=1 uv run uvicorn main:app --port 8000                 # no credentials: fake chat model
AI_GATEWAY_API_KEY=... uv run uvicorn main:app --port 8000     # real model through AI Gateway
```

Without `VERCEL_DEPLOYMENT_ID`, the SDK uses its **Local World**. It stores runs, steps, hooks, and events as JSON in `.workflow-data/` and uses an in-process queue. You don't need a Vercel account or `vercel dev`. Runs waiting on a hook survive a server restart: the next `approve` resumes them from disk. With `FAKE_LLM=1`, every draft is the same canned text. Without any credential, the run fails right away with a clear error. The step raises `FatalError`, so it isn't retried. To change the model, set `AI_GATEWAY_MODEL` (default `openai/gpt-5.4-nano`).

## Endpoints (curl)

```bash
BASE=http://localhost:8000   # or https://<your-deployment>.vercel.app

curl $BASE/                                                       # endpoint listing
curl -X POST $BASE/api/runs -H 'content-type: application/json' \
  -d '{"topic": "a solar-powered kettle"}'                        # -> {"run_id": "wrun_..."}
curl $BASE/api/runs/wrun_XXXX
# -> {"status": "running", "awaiting_approval": {"draft": "...", "draft_number": 1, "paused_at": "2026-10-08T14:25:53.237000+00:00"}}
curl -X POST $BASE/api/runs/wrun_XXXX/approve -H 'content-type: application/json' \
  -d '{"approved": false, "feedback": "Mention it boils in 3 minutes"}'   # loops back to `write`
curl -X POST $BASE/api/runs/wrun_XXXX/approve -H 'content-type: application/json' \
  -d '{"approved": true}'                                         # -> {"ok": true, "paused_s": 12.345}
curl $BASE/api/runs/wrun_XXXX
# -> {"status": "completed", "result": {"topic": "...", "draft": "...", "drafts": 2}}
```

`awaiting_approval` is the hook's metadata (the draft and its number, counted in the graph state) plus `paused_at`, the time Workflow created the hook. `approve` returns `paused_s`, how long the run sat on that hook, measured on the server. It returns 409 when the run isn't waiting for review.

## Deploy notes

- **Project settings:** Framework Preset **FastAPI**, Root Directory `07-langgraph-workflow`. Keep the default Build and Install commands. You don't need `vercel.json`.
- **Build:** `@vercel/python` reads `pyproject.toml`. `[tool.vercel] entrypoint` is the web function. `[[tool.vercel.workflows]]` becomes a second function (`_py_workflows/...`) that Vercel Queues trigger on the registry's `__wkf_*` topics. The builder imports `agent:wf` at build time to find those topics, so importing `agent` must not need credentials.
- **Env vars:** none are required. The deployment's OIDC token authenticates both Workflow and AI Gateway (`vercel.oidc.aio.get_vercel_oidc_token()`). `AI_GATEWAY_API_KEY` overrides it, and `AI_GATEWAY_MODEL` is optional.
- **Resources:** nothing to provision. Workflows (event log) and Queues are managed and usage-billed. Runs show up under **Observability → Workflows**.

## Gotchas (found while building this)

- **Every node and conditional-edge router must be `async def`.** LangGraph runs sync callables with `loop.run_in_executor()`, which the workflow event loop rejects with `SandboxRestrictionError`. `graph.ainvoke()` works, and so do the default `values`/`updates` stream modes. The `messages`/`custom` stream modes and subgraph streaming use `call_soon_threadsafe()`, which is also blocked.
- **`passthrough_modules` is required.** The workflow sandbox re-imports modules per sandbox. Re-importing LangChain fails because the sandbox blocks `ssl`, so `langgraph`, `langchain_core`, `langchain_openai`, and `langsmith` are served from the host interpreter.
- **SDK bug in vercel-workflow 0.11.0 and 0.11.1 (and vercel-py `main` as of 2026-10-08).** Passing a package through the sandbox overwrites the host module's `__spec__`. That breaks `langchain_core`'s lazy imports, so `from langchain_openai import ChatOpenAI` *inside a step* raises `ImportError: module ''langchain_core'.'config'' not found` once a workflow body has run in that process. Workaround: import LangChain at module top, as `agent.py` does.
- **Step inputs and outputs must be plain data.** Returning an `AIMessage`, or even `message.text` (a `str` subclass), fails with `Cannot serialize value ... Register TextAccessor with @serializable`, so the step returns `str(message.text)`.
