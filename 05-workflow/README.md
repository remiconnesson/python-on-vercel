# 05 · Vercel Workflow with Python

A durable workflow written with the official Python SDK, [`vercel-workflow`](https://pypi.org/project/vercel-workflow/) (beta). It has three steps: the second one fails on its first attempt and gets retried automatically, and a durable `workflow.sleep()` sits between the second and third. A FastAPI app starts runs and reports their status and result.
On Vercel, `[[tool.vercel.workflows]]` in `pyproject.toml` is the only extra config. The builder deploys the workflow registry as its own function, and Vercel Queues trigger it. You don't need `vercel.json` or any env vars.

```
05-workflow/
├── main.py          # FastAPI app: GET /, POST /api/runs (start), GET /api/runs/{id} (status/result)
├── index.html       # the visual explainer served at `/` to browsers
├── workflows.py     # Workflows registry + 3 steps + process_order workflow with a durable sleep
├── pyproject.toml   # deps + [[tool.vercel.workflows]] entrypoint = "workflows:wf"
├── uv.lock          # locked deps (uv lock)
├── .gitignore       # ignores .venv and .workflow-data (local run storage)
└── RESEARCH.md      # what exists for Python Workflow on Vercel, mechanics, gotchas
```

## Run locally

```bash
uv sync
uv run uvicorn main:app --port 8000
```

You don't need a Vercel account or `vercel dev`. Without `VERCEL_DEPLOYMENT_ID`, the SDK uses its **Local World**: it writes runs, steps, and events as JSON under `.workflow-data/`, and it uses an in-process queue for steps and sleeps.

Local-only caveat: that queue lives in memory. If you restart the server while a run is sleeping, the wake-up is lost and the run stays `running`. Avoid `--reload` for this reason. On Vercel, Vercel Queues stores the wake-up durably.

## Endpoints (curl)

```bash
BASE=http://localhost:8000   # or https://<your-deployment>.vercel.app

curl $BASE/                                                          # endpoint listing + "world": "local" or "vercel"
curl -X POST "$BASE/api/runs?order_id=order_42&delay_seconds=10"     # -> {"run_id": "wrun_...", "status_url": ...}
curl $BASE/api/runs/wrun_XXXXXXXX                                    # -> {"status": "running"} ... then:
# {"run_id":"wrun_...","status":"completed","result":{
#   "steps":[{"name":"reserve_inventory","result":"reserved items for order_42","attempt":1,"first_attempt_at":"...","ran_at":"..."},
#            {"name":"charge_card","result":"charged card for order_42","attempt":2,"first_attempt_at":"...","ran_at":"..."},
#            {"name":"send_receipt","result":"receipt for order_42 sent","attempt":1,"first_attempt_at":"...","ran_at":"..."}],
#   "started_at":"...","slept_at":"...","woke_at":"...","delay_seconds":10}}
```

Each step reports its own `attempt` (from `workflow.get_step_metadata()`), when its first attempt began, and when the attempt that succeeded ran. `charge_card` shows `attempt: 2`, about a second after its first attempt. `slept_at` and `woke_at` come from `workflow.now()`, the time of the latest event in the run's log, and should be about `delay_seconds` apart.

Open the app in a browser for a live explainer. It starts a run, polls its status, and draws the steps, the retry and the sleep on a real time axis from these timestamps. It also shows how each wake-up replays the workflow body. If you reload the page mid-sleep, it picks the run up again. `curl` on `/` still gets JSON.

## Deploy notes

- **Vercel project settings:** Framework Preset **FastAPI** (auto-detected from `main.py`), Root Directory `05-workflow`. Leave the Build, Install, and Output commands at their defaults.
- **Env vars:** none. The SDK authenticates with the deployment's built-in OIDC token and system env vars (`VERCEL_DEPLOYMENT_ID`, `VERCEL_PROJECT_ID`, ...).
- **External resources:** none to provision. Vercel Workflows (state and event log) and Vercel Queues (step and sleep dispatch) are managed. Their usage is billed as Workflow Events/Data and Queues usage. Runs appear under **Observability → Workflows** in the dashboard.
- **What the build does:** `@vercel/python` reads `[[tool.vercel.workflows]]`. At build time it imports `workflows:wf` to find its queue topics (`__wkf_workflow_*`). Next to the FastAPI function, it emits a second function (`_py_workflows/...`) with a `queue/v2beta` trigger. `vercel-workflow` has to be a direct dependency, or the builder falls back to a legacy serving mode.
- **Retention:** run data is kept for 1 day after completion on Hobby, 7 days on Pro, and 30 on Enterprise. After that, `GET /api/runs/{id}` returns 404.
