# Research: LangGraph on Vercel Workflow (Python)

Researched on 2026-10-08. Short version: **no official or community integration between LangGraph and Vercel Workflow exists.** There's no template, docs page, blog post, LangGraph checkpointer backed by Workflow, or "nodes as steps" adapter, in Python or JS. What does exist is an official **Python Workflow SDK (beta)** whose primitives are enough to run a LangGraph graph durably. This demo does that, and the gotchas below come from testing it.

## What's available

**Vercel Workflow for Python (official)**

- [vercel.com/docs/workflows/python](https://vercel.com/docs/workflows/python) redirects to [workflow-sdk.dev/docs/getting-started/python](https://workflow-sdk.dev/docs/getting-started/python), the canonical Python guide (beta, updated 2026-10-07). It covers `pyproject.toml` (`dependencies = ["vercel-workflow"]`, `[[tool.vercel.workflows]] entrypoint = "module:obj"`), `Workflows`, `@wf.workflow`, `@wf.step` (`cancellable=`), `workflow.start()` / `Run`, `sleep()`, `now()` / `time_ns()` / `random()`, hooks (`BaseHook.wait()` / `.resume()`), and streams.
- [vercel.com/docs/workflows](https://vercel.com/docs/workflows) is the product overview. Functions run workflow and step code, Vercel Queues dispatch them, managed storage holds the event log, and billing is usage-based ([pricing](https://vercel.com/docs/workflows/pricing)). Python is listed next to JS and TS.
- [pypi.org/project/vercel-workflow](https://pypi.org/project/vercel-workflow/) is the SDK package. The latest release is 0.11.1 (2026-10-06). The umbrella [`vercel`](https://pypi.org/project/vercel/) package depends on it. The import is `from vercel import workflow`.
- [github.com/vercel/vercel-py](https://github.com/vercel/vercel-py) holds the source in `src/vercel-workflow/`, including the sandbox (`_internal/py_sandbox.py`), runtime, and Local and Vercel Worlds.
- [vercel/workflow `workbench/python`](https://github.com/vercel/workflow/tree/main/workbench/python) is the Python conformance app for the shared e2e suite. It shows the ASGI wiring (`registry.http_handler`, `ENDPOINT_PATH`) and `[tool.vercel] entrypoint` plus `[[tool.vercel.workflows]]`.
- [vercel-labs/ai-python `durable_agent_workflows`](https://github.com/vercel-labs/ai-python/tree/main/examples/apps/durable_agent_workflows) is the closest official analogue. A third-party agent loop (AI SDK for Python's `ai.Agent`) runs **inside a workflow body**, with LLM calls and tools as `@workflow.step` and `SandboxPolicy(passthrough_modules={"ai"})`. This demo copies that pattern.
- Vercel Python builder source: [`packages/python/src/workflows.ts`](https://github.com/vercel/vercel/blob/main/packages/python/src/workflows.ts) parses `[[tool.vercel.workflows]]` and emits `_py_workflows/<name>`. [`sdk-detection.ts`](https://github.com/vercel/vercel/blob/main/packages/python/src/sdk-detection.ts) uses queue serving only when `vercel-workflow>=0.9.0` or `vercel>=0.8.0` is a **direct** dependency. The [CHANGELOG](https://github.com/vercel/vercel/blob/main/packages/python/CHANGELOG.md) shows when this was added (6.50.0), moved to vercel-queue (6.54.0), and taught to recognize `vercel-workflow` (6.57.1).
- [Vercel Python SDK beta changelog](https://vercel.com/changelog/vercel-python-sdk-in-beta) announced the `vercel` package (seen in search results).

**LangGraph side**

- [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/durable-execution) (the old "durable execution" URL now serves this page): LangGraph's own durability needs a checkpointer plus a `thread_id`. `InMemorySaver` doesn't survive restarts, so production needs Postgres or SQLite savers.
- [LangGraph interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts): human-in-the-loop with `interrupt()` needs a checkpointer. On resume, "the node restarts from the beginning", so LangGraph's own model is replay-like too.

**Durable LangGraph elsewhere (prior art, not Vercel)**

- [Temporal LangGraph integration](https://docs.temporal.io/develop/python/integrations/langgraph) (Public Preview) and its [blog post](https://temporal.io/blog/temporal-langgraph-plugin-durable-execution). The graph runs in a Temporal workflow and nodes run as activities. It documents the same limitation found here: sync conditional edges call `run_in_executor`, which the sandbox forbids. It supports only `InMemorySaver`, because Temporal provides durability.
- [ZenML/Kitaru "LangGraph durable runtime"](https://www.zenml.io/blog/langgraph-durable-runtime) (seen in search results) wraps a LangGraph graph in another durable Python runtime.
- The Workflow SDK's [comparison table](https://workflow-sdk.dev/docs/comparisons/workflow-sdk-vs-aws-agentcore) mentions LangGraph only as something AgentCore hosts. Code search of vercel/workflow, vercel/vercel-py, vercel/vercel, and vercel-labs/ai-python found no other LangGraph references.

**Models and auth**

- [AI Gateway Python (OpenAI SDK)](https://vercel.com/docs/ai-gateway/sdks-and-apis/python): `base_url="https://ai-gateway.vercel.sh/v1"`. Gateway docs use `AI_GATEWAY_API_KEY` or the OIDC token ([auth](https://vercel.com/docs/ai-gateway/authentication-and-byok), [OIDC](https://vercel.com/docs/ai-gateway/authentication-and-byok/oidc)). The [AI SDK for Python](https://vercel.com/docs/ai-gateway/sdks-and-apis/ai-sdk-python) is the other official route. The model list comes from `https://ai-gateway.vercel.sh/v1/models`. This demo defaults to `openai/gpt-5.4-nano`.
- The OIDC token is available in Python at runtime through `vercel.oidc.aio.get_vercel_oidc_token()` (package `vercel-oidc`). It reads the `x-vercel-oidc-token` request header (registered through `vercel.headers`), then `VERCEL_OIDC_TOKEN`, then refreshes from a linked `.vercel/` folder with the CLI login. The Workflow `VercelWorld` itself authenticates with this function, so it's available in workflow and step invocations.

## How it works on Vercel

1. **Two functions from one `pyproject.toml`.** `[tool.vercel] entrypoint = "main:app"` is the FastAPI function. `[[tool.vercel.workflows]] entrypoint = "agent:wf"` makes the builder import the registry at build time, read its queue subscriptions (here `__wkf_workflow_*`), and emit a second function with a queue trigger.
2. **`workflow.start(run_agent, topic=...)`** writes `run_created` and enqueues the run, then returns a `Run` right away. `workflow.get_run(id).status()` returns `pending|running|completed|failed|cancelled`. `return_value()` polls until the run is terminal. `get_hook_by_token()` returns an open hook, including its `metadata`.
3. **Workflow body (replayed).** Each wake-up re-executes `run_agent` from the top, inside a **Python-level sandbox** with a private `sys.modules` and on a custom `WorkflowLoop`. Calls to steps, hooks, and sleeps get correlation IDs from a PRNG seeded with the run ID. When one is already in the event log, the recorded result comes back right away. Otherwise the run suspends, and the runtime writes `step_created` / `hook_created` and enqueues the work.
4. **Steps** run in the regular interpreter as separate queue deliveries. They're retried 3 times by default (`@wf.step(max_retries=...)`, `FatalError`, `RetryableError`), and their inputs and outputs are serialized (and encrypted on Vercel) into the event log.
5. **Hooks:** `Approval.wait(token=..., metadata=...)` suspends the run without using compute. `Approval(...).resume(token)` from any server code writes `hook_received` and re-enqueues the run. Disposing a hook (`async with`) releases its token right away, so the next `review` can reuse it.
6. **Locally:** without `VERCEL_DEPLOYMENT_ID` (or with `WORKFLOW_TARGET_WORLD=local`), the **Local World** writes JSON under `.workflow-data/` and runs an embedded in-process queue, so plain `uvicorn` works. `python -m vercel.workflow manifest --stdout` prints the registry manifest the build introspects.

Event log observed for one run with one rejection, then an approval: `run_created, run_started, step_*×3, hook_created, hook_received, hook_disposed, step_*×3, hook_created, hook_received, run_completed`. After a server restart in the middle of a run, the replay didn't re-run the completed step.

## Gotchas

- **Determinism and replay.** The body (and therefore every graph node and router) re-runs on each wake-up. Anything non-deterministic must sit in a step: LLM calls, I/O, `datetime.now()`, `random`. Control flow may depend only on graph input, step results, and hook payloads.
- **The sandbox blocks LangGraph's executor paths.** `WorkflowLoop` forbids `run_in_executor` and `call_soon_threadsafe`. Verified: a sync node or a sync conditional-edge router fails with `SandboxRestrictionError: Cannot call loop.run_in_executor()`. `astream(stream_mode="custom")` fails on `call_soon_threadsafe()`. `ainvoke()` and the `values`/`updates` modes work. Use `async def` everywhere. LangGraph's sync `invoke()` can't await steps anyway.
- **`passthrough_modules` is mandatory for LangChain.** Without it, the sandbox re-imports `langchain_core`/`langsmith` and fails because `ssl` is blocked (`'function' object has no attribute 'startswith'` in urllib3). The working set is `{"langgraph", "langchain_core", "langchain_openai", "langsmith"}`, and dropping `langsmith` breaks it. Passthrough code isn't checked for nondeterminism, which is acceptable because LangGraph's uuids and timestamps don't affect step order.
- **SDK bug (vercel-workflow 0.11.0. The `py_sandbox.py` code is identical in 0.11.1 and vercel-py `main`).** Passthrough imports use `spec_from_loader(name, _PreloadedLoader(host_module))`, and importlib then overwrites the **host** module's `__spec__` (`langchain_core.callbacks.__spec__.parent` becomes `"langchain_core"`). LangChain's lazy `__getattr__` imports use `__spec__.parent`, so any LangChain import *inside a step* fails after the first workflow replay in that process (`ImportError: module ''langchain_core'.'config'' not found`). Workaround: import LangChain at module top, so the attributes resolve before any sandbox exists. This is worth reporting upstream to vercel-py.
- **Serialization.** Step arguments and results go through the Workflow serde. `AIMessage` and even `AIMessage.text` (a `str` subclass, `TextAccessor`) fail with "Register ... with @serializable". Return plain `str`, `dict`, or `list`, or register classes with `workflow.serializable`. Graph *state* never crosses a boundary in this design. Only step I/O and hook payloads do.
- **No checkpointer, no `interrupt()`.** `interrupt()` needs a checkpointer, and an `InMemorySaver` dies with the function instance. In this design the Workflow event log provides persistence, and a Workflow hook replaces `interrupt()`. The tradeoff is that LangGraph time travel and `get_state()` aren't available.
- **Replay cost grows with history.** Each wake-up replays the whole graph. That's cheap here (milliseconds per superstep), but long agent loops replay every earlier superstep, the same caveat LangGraph gives for `interrupt()` loops. The default `recursion_limit` (25 supersteps) still applies.
- **`share_sandboxes=True`** compiles the graph once per process, but module globals are shared across concurrent runs, so don't mutate them.
- **Beta SDK.** APIs may change. Python runs use event-log spec 5. The JS docs note Python lags behind newer spec features (sealed logs and hook takeover).

## Approach chosen for this demo

**Run the LangGraph graph inside the workflow body, with side effects as `@wf.step` calls from the nodes and human approval as a Workflow hook inside a node.**

Why:
- Every LLM call is individually durable and retried, and a crash or redeploy at any point resumes at the last completed node. That's per-node durability, which is the point of combining the two.
- Human-in-the-loop waits as long as needed without compute or a database. The alternative needs `interrupt()` plus a Postgres checkpointer from the Marketplace.
- It matches the official pattern for third-party agent loops on Workflow (ai-python `durable_agent_workflows`) and Temporal's design for LangGraph.
- It uses only documented SDK APIs. Nothing is invented, and the only workaround is import placement for the bug above.

Alternatives considered:
- **The whole graph in one step.** Simplest, but no durability between nodes (a retry re-runs the whole graph), and human-in-the-loop would still need a persistent checkpointer.
- **A Workflow-backed `BaseCheckpointSaver`.** It doesn't exist. Workflow exposes no general key-value read API to build one on, so it would mean inventing an integration.
- **`interrupt()` plus a Postgres checkpointer, with the Workflow only waiting between invocations.** It works, but adds infrastructure and duplicates what the event log already provides.
