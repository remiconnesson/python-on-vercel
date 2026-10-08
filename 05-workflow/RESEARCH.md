# Research: Vercel Workflow with Python (October 2026)

**Summary:** there is an official Python SDK for Vercel Workflow. It's in **beta**, published on PyPI as **`vercel-workflow`** (import path `vercel.workflow`), and the umbrella `vercel` package pulls it in too. The Vercel Python builder deploys it natively through `[[tool.vercel.workflows]]` in `pyproject.toml`. Vercel Workflows itself has been GA since April 2026.

## What's available

| Source | What it shows |
| --- | --- |
| [workflow-sdk.dev/docs/getting-started/python](https://workflow-sdk.dev/docs/getting-started/python) ([.md](https://workflow-sdk.dev/docs/getting-started/python.md)) | **The canonical Python guide.** `vercel.com/docs/workflows/python` 307-redirects here. Covers the `pyproject.toml` setup, `Workflows()`, `@wf.workflow`, `@wf.step` (incl. `cancellable=True`), `workflow.start()` / `Run`, `sleep()` duration forms, deterministic helpers, hooks, and typed streams. Marked beta. |
| [vercel.com/docs/workflows](https://vercel.com/docs/workflows) | Product overview. Functions run workflow and step code, Vercel Queues dispatch it, and managed persistence holds the event log. Also covers multi-region pinning and observability (dashboard → Observability → Workflows), and links the Python guide. |
| [vercel.com/docs/workflows/pricing](https://vercel.com/docs/workflows/pricing) | Billing: Workflow Events, Data Written, and Data Retained, plus Queues usage. Retention after completion is 1 day on Hobby, 7 on Pro, 30 on Enterprise. |
| [pypi.org/project/vercel-workflow](https://pypi.org/project/vercel-workflow/) | The SDK. Latest is 0.11.1 (2026-10-06); 0.11.0 was released 2026-09-23. Depends on `vercel-queue`, `vercel-oidc`, `pydantic`, `cbor2`, `cryptography`. |
| [pypi.org/project/vercel](https://pypi.org/project/vercel/) | Umbrella SDK (0.11.6). Depends on `vercel-workflow>=0.11.1`, `vercel-queue`, `vercel-sandbox`, and others. |
| [github.com/vercel/vercel-py](https://github.com/vercel/vercel-py) → `src/vercel-workflow/README.md`, `CHANGELOG.md` | Source plus a fuller README than the docs: retries (`max_retries`, `FatalError`, `RetryableError`), `get_step_metadata()`, run attributes, queue namespaces, hooks (dataclass/pydantic, tokens, metadata), stream semantics, custom serializers. The changelog shows a fast-moving beta with breaking changes in 0.10. |
| [vercel-py release vercel-workflow-v0.11.0](https://github.com/vercel/vercel-py/releases/tag/vercel-workflow-v0.11.0) | Adds `Run.terminate()` and `get_run(run_id, type=...)`, and makes `Run.status()` and `return_value()` durable inside workflows. |
| [vercel/vercel `packages/python/src/workflows.ts`](https://github.com/vercel/vercel/blob/main/packages/python/src/workflows.ts) (+ `index.ts`, `sdk-detection.ts`, `subscribers.ts`) | **The real deployment mechanics**, summarized in "How it works on Vercel" below. |
| [@vercel/python 6.50.0 notes (releases.sh)](https://releases.sh/release/rel_komZRuMDU-Xaw9FujXf6d) | July 2026: "Support declaring workflow entrypoints through `tool.vercel.workflows` in pyproject.toml." |
| [Vercel CLI 56.3.0 notes (releases.sh)](https://releases.sh/release/rel_SO5sX_0A6bpmMRQM6A6lT-python-services-in-vercel-dev-domain-alias-team-scope-fixed) | `vercel dev` runs Python workflow "sidecars" declared in `pyproject.toml`. |
| [github.com/vercel/workflow → `workbench/python`](https://github.com/vercel/workflow/tree/main/workbench/python) | Official Python conformance app (`app.py`, `workflows/99_e2e.py`). Uses `[tool.vercel] entrypoint` + `[[tool.vercel.workflows]]`, mounts `registry.http_handler` on bare ASGI for local cross-language tests, and exercises many API shapes (sleep, hooks, streams, retries). |
| [Blog: A new programming model for durable execution](https://vercel.com/blog/a-new-programming-model-for-durable-execution) | April 16, 2026: Vercel Workflows is GA and the Workflow Python SDK is in beta. |
| [Changelog: extended step durations](https://vercel.com/changelog/workflow-steps-now-support-extended-function-durations) | July 2026: steps can run up to 1800 s on Pro/Enterprise with `VERCEL_ENABLE_WORKFLOW_EXTENDED_DURATION=1` + Fluid compute. Node.js or Python. |
| [Changelog: Vercel Python SDK beta](https://vercel.com/changelog/vercel-python-sdk-in-beta) | Oct 2025 launch of the `vercel` Python package (Sandbox, Blob, Runtime Cache). Predates workflow support. |
| [vercel.com/docs/queues](https://vercel.com/docs/queues), [queues/python-sdk](https://vercel.com/docs/queues/python-sdk) | Vercel Queues (beta) runs underneath Workflow. Includes `vercel.queue` with `subscribe` and the embedded local queue service. |
| [workflow-sdk.dev/llms.txt](https://workflow-sdk.dev/llms.txt) | Full docs dump. Comparison tables list the SDK's languages as "TypeScript (Python beta)" and note that Python runs use an older spec version (no sealed-log features). |
| [github.com/vercel/examples `python/`](https://github.com/vercel/examples) | Has no Python workflow example. Closest are `python/queue-subscribers` and `python/celery`. I found no official Vercel template for Python Workflow. |

## How it works on Vercel

1. **Declare.** Add `[[tool.vercel.workflows]] entrypoint = "module:object"` pointing at a `vercel.workflow.Workflows()` instance. Workflows only attach to Python *framework* builds (preset `fastapi`, `flask`, `django`, `python`, or `fasthtml`) or to an explicit `"entrypoint": "pyproject.toml"` service. Bare `api/*.py` functions don't get them.
2. **Build.** `@vercel/python` checks that `vercel-workflow>=0.9.0` (or `vercel>=0.8.0`) is a **declared** dependency, which selects "queue" serving mode. It then imports the entrypoint module with `VERCEL=1 VERCEL_DEPLOYMENT_ID=dpl_introspection` and reads `vercel.queue.get_subscriptions()`. For this demo that returns topic `__wkf_workflow_*`, consumer group `default` (I verified this locally with the same script). Finally it emits an extra Lambda `_py_workflows/<name>` with `experimentalTriggers: [{type: "queue/v2beta", topic, consumer}]` alongside the web Lambda.
3. **Run.** In the web function, `await workflow.start(fn, ...)` sees `VERCEL_DEPLOYMENT_ID` and selects the Vercel World. It writes `run_created` to Vercel's workflow backend (authenticated with the per-request OIDC token), enqueues an invoke message on `__wkf_workflow_<workflow_id>`, and returns a `Run` immediately.
4. **Orchestrate.** Queues deliver that message to the workflow Lambda. The SDK replays the workflow body from the event log inside a deterministic Python sandbox. At each new step it enqueues a step message, which the same Lambda picks up. The step runs as normal Python, its result or error is recorded, and the workflow is re-invoked. `sleep()` records `wait_created` and schedules a delayed queue message (capped at 23 h per hop and chained for longer sleeps). No compute runs while a run waits.
5. **Observe.** `Run.status()` reads `pending|running|completed|failed|cancelled`, and `Run.return_value()` polls until the run reaches a terminal state. Runs and their events also show up in dashboard → Observability → Workflows.
6. **Local.** Without `VERCEL_DEPLOYMENT_ID` the SDK uses `LocalWorld`, which stores JSON files under `.workflow-data/` (override with `WORKFLOW_LOCAL_DATA_DIR`). It uses an in-process embedded queue, unless `VERCEL_QUEUE_BASE_URL` points at an external one. A plain `uvicorn main:app` runs the whole thing. `vercel dev` (CLI ≥ 56.3) can also run the workflow as a sidecar, but it needs a linked project.

## Gotchas

- **Beta API, fast churn.** 0.10 enforced type annotations on workflow and step args (pydantic), changed numeric sleeps from ms to seconds, and changed hook return semantics. Pin a lower bound and read the CHANGELOG before upgrading.
- **The docs disagree on the package.** The Vercel docs snippet says `dependencies = ["vercel"]`, while the current guide says `"vercel-workflow"`. Both provide `vercel.workflow`. Whichever you pick must be a **direct** dependency, or the builder falls back to the legacy `vercel-workers` mode.
- **The builder imports your workflow module at build time.** That import must succeed with no secrets or network and no side effects.
- **Workflow bodies are sandboxed and replayed.** The module is re-imported per run, and `time.time`, `random`, and similar raise `SandboxRestrictionError`. Use `workflow.now()`, `workflow.random()`, and `workflow.time_ns()`, and keep I/O in steps. Keep the workflow module separate from the web app. `sleep()` inside a step raises `RuntimeError`.
- **Steps retry.** By default a step gets 3 retries, about 1 s apart. Side effects repeat on each retry, so use `get_step_metadata().step_id` as an idempotency key. `FatalError` stops retrying and `RetryableError(retry_after=...)` sets the delay.
- **The local queue is in memory.** I verified that killing the server mid-sleep leaves the run `running` forever after restart, even though the event log survived on disk. Don't use `uvicorn --reload` while a run is sleeping.
- **Streams are never auto-closed.** Close them from the last step, or readers hang until the run expires.
- **Retention is short on Hobby** (1 day after completion). Status lookups for old runs fail.
- **Step duration** caps at 300 s on Hobby. Pro allows 800 s, or 1800 s with `VERCEL_ENABLE_WORKFLOW_EXTENDED_DURATION=1` + Fluid.
- **Multiple registries** in one project each need a distinct `Workflows(namespace=...)`, or the build fails.
- **Local tooling note.** This machine's uv config has `exclude-newer = "2 days"`, so the lock resolves `vercel-workflow` **0.11.0** (0.11.1 is 2 days old) and records `exclude-newer` in `uv.lock`. Vercel installs user lockfiles with `uv sync --frozen`, so that's harmless there. `uv lock --check --no-config` will report the lock as stale, though.

## Approach chosen for this demo

I used the **official SDK as documented**, with no custom HTTP handlers, no `vercel.json`, and no internal APIs:

- **FastAPI zero-config** (`main.py`, `app = FastAPI()`) for the web endpoints. The FastAPI preset is a Python framework build, so `[[tool.vercel.workflows]]` is honored.
- **`workflows.py`** holds the `Workflows()` registry, 3 `@wf.step`s, and one `@wf.workflow`. It sits in its own module because the sandbox re-imports it. The second step fails its first attempt to show retries, and `workflow.sleep(delay_seconds)` sits between steps 2 and 3. The result includes `workflow.now()` before and after the sleep to make the durable wait visible.
- `POST /api/runs` → `workflow.start()`. `GET /api/runs/{id}` → `workflow.get_run(id).status()` plus `return_value()` once the run is completed.
- The local run uses the SDK's Local World, so nothing is needed beyond `uv run uvicorn`.

Rationale: this is the smallest setup that exercises every moving part on Vercel: the web function starts a run, the queue-triggered workflow function runs it, and the durable sleep and retry play out in between. All of it uses only documented APIs and pyproject-only config.
