# Celery on Vercel

A FastAPI endpoint enqueues a Celery task with `.delay()`, and the task runs on Vercel with no Redis, no RabbitMQ and no long-running `celery worker`. Vercel's `vercel://` broker publishes tasks to **Vercel Queues**. The Celery app declared under `[[tool.vercel.subscribers]]` is compiled into a **private, queue-triggered Vercel Function** that runs one task per invocation, and Queues scales it out. Results are stored in **Vercel Runtime Cache** (`vercel-runtime-cache://`), and you read them back with `AsyncResult`.

```
POST /tasks ──.delay()──▶ Vercel Queues topic ──push──▶ worker function (private) ──▶ Runtime Cache
GET /tasks/{id} ◀──────────────── AsyncResult ◀──────────────────────────────────────┘
```

## Files

```
03-celery/
├── main.py         FastAPI web app: GET / (index), POST /tasks (enqueue), GET /tasks/{id} (status + result)
├── index.html      Visual explainer served at / to browsers: traces a live task from web function to worker and back
├── tasks.py        Celery app (broker vercel://, backend vercel-runtime-cache://), the add(x, y) task, per-instance id
├── worker.py       Subscriber entrypoint that re-exports the Celery app; becomes the private worker function
├── pyproject.toml  Dependencies, [tool.vercel] web entrypoint, [[tool.vercel.subscribers]] worker
├── uv.lock         Locked dependencies
├── RESEARCH.md     Sources, how it works, gotchas, why this approach
└── .gitignore
```

There's no `vercel.json`. The web app and the worker are both declared in `pyproject.toml`, and Vercel generates the queue trigger at build time.

## Run locally

You need Vercel CLI 58.9.0 or later. `vercel dev` runs the web app plus a "development sidecar" for the Celery worker, with a local queue.

```bash
uv sync
# Runtime Cache only exists on Vercel. For local runs, point Celery's result backend at its
# built-in filesystem backend. Celery reads CELERY_RESULT_BACKEND before the value in tasks.py.
mkdir -p /tmp/celery-results
CELERY_RESULT_BACKEND=file:///tmp/celery-results vercel dev --local --listen 3000
```

`--local` skips project linking. A plain `vercel dev` in a linked project works too. Without the `CELERY_RESULT_BACKEND` override, tasks still run (you'll see `Task tasks.add[...] succeeded` in the worker logs), but `GET /tasks/{id}` returns a 503 that explains Runtime Cache is unavailable. Under plain `uvicorn`, which has no Vercel runtime, `POST /tasks` returns a 503 with `No such transport: vercel`, and the explainer page shows that error.

Locally the region reads `dev1`, and one sidecar process stands in for the worker function, so a burst of tasks runs one at a time. `main.py` reads `index.html` once at import, so restart `vercel dev` after editing the page.

`vercel dev` (CLI 59.4.0) stops the Python web server when two requests to it overlap, and every later request returns 500 `FUNCTION_INVOCATION_FAILED` until you restart it. The explainer page keeps one request in flight at a time, but reloading it in the middle of a poll can still trigger this. Deployed functions aren't affected.

## Deploy

- **Vercel project**: Root Directory `03-celery`. Leave the framework preset, build command and install command at their defaults. Vercel detects FastAPI from `pyproject.toml`.
- **Environment variables**: none. Don't set `CELERY_BROKER_URL` or `CELERY_RESULT_BACKEND` on Vercel, because they override `tasks.py`.
- **External resources**: none to provision. Vercel Queues (beta, all plans) and Runtime Cache (all plans) are used automatically, and deployed functions authenticate to Queues through Vercel OIDC.
- After the build you should see two functions: the public web app and a private subscriber function. The queue topic is `celery-celery-on-vercel-celery`, built as `celery-<app name>-<queue>`.

## Try it

Open the app in a browser for a live explainer. It enqueues `add(2, 3)` when it loads, then draws the task's path from the web function through Vercel Queues to the worker function and back, with real timestamps, the instance ID and region of each function, and a burst of five tasks to show how the worker scales. `curl` on `/` still gets JSON.

Each instance gives itself a random 8-character ID when it starts (`INSTANCE_ID` in `tasks.py`). The web function returns its own ID as `web`, and `add()` returns the worker's ID with the sum, so you can see the task ran in a different function.

```bash
BASE=http://localhost:3000   # or https://<your-deployment>.vercel.app

curl -s $BASE/
# {"demo": "...", "web": {"instance_id": "29349ee9", "region": "iad1"},
#  "queue_topic": "celery-celery-on-vercel-celery", "endpoints": {...}}

curl -s -X POST "$BASE/tasks?x=2&y=3"
# {"task_id": "86a8d154-...", "status_url": "/tasks/86a8d154-...",
#  "enqueued_at": "2026-10-08T14:28:02.585+00:00", "publish_ms": 122.9,
#  "web": {"instance_id": "29349ee9", "region": "iad1"}}

curl -s $BASE/tasks/<task_id>
# During the task's 2 s of "work":
# {"task_id": "86a8d154-...", "status": "PENDING", "result": null, "worker": null,
#  "stored_at": null, "read_at": "...", "web": {...}}
# Then:
# {"task_id": "86a8d154-...", "status": "SUCCESS", "result": 5,
#  "worker": {"instance_id": "1842a29f", "region": "iad1",
#             "started_at": "2026-10-08T14:28:02.611+00:00", "finished_at": "2026-10-08T14:28:04.615+00:00"},
#  "stored_at": "2026-10-08T14:28:04.618+00:00", "read_at": "...", "web": {"instance_id": "29349ee9", ...}}
```

`result` is still the sum. `worker` comes from the task's return value, `stored_at` is Celery's `date_done` (when the worker wrote the result), and `read_at` is when the web function read it. All times are UTC from each function's own clock. An unknown or expired task id reads as `PENDING`. That's Celery's behavior when the result backend has no entry.

## Gotchas

- **Results are ephemeral.** Runtime Cache is regional and can evict entries early, so treat results as short-lived status only. For durable results, set a Redis or Postgres result backend in `tasks.py` and add the matching Celery extra.
- **Retries.** By default Celery acks a message as soon as the task starts, so a task that crashes or hits the function timeout isn't redelivered. Set `app.conf.task_acks_late = True` and keep tasks idempotent, because Queues delivers at least once. Queues doesn't defer `countdown` or `eta`: the invocation holds the task in memory until it's due, so keep delays short.
- **No `celery beat`, and no worker control commands.** For periodic tasks, use Vercel Cron Jobs to call an endpoint that enqueues. Each task must also finish within the function's maximum duration.
- **Deployment pinning.** Each message is consumed by the deployment that published it, and old deployments keep draining their own messages.
- **Why `vercel-celery` is in `dependencies`.** The docs say it's optional, because the build injects a bundled copy when it's absent. Locally, that bundled copy (`vercel-celery-bundle` 0.7.7 and 0.7.8) crashed `vercel dev` at import with `PackageNotFoundError: httpx2`: its vendored httpx2 looks up its own package metadata. Declaring the unbundled adapter avoids that and pins its version in `uv.lock`. A self-declared adapter is still activated by the build.

## Alternative: bring your own broker (worker runs elsewhere)

A classic, long-running `celery worker` can't run inside Vercel Functions. If you want Celery with Redis instead of Vercel Queues, for example Upstash Redis from the Vercel Marketplace, you don't change any code:

1. Add `celery[redis]` to `dependencies`.
2. Remove the `[[tool.vercel.subscribers]]` block.
3. On Vercel, set `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND`. For Upstash, use `rediss://:<password>@<host>:<port>?ssl_cert_reqs=required`.
4. Run `celery -A tasks worker` on a long-running host with the same env vars.

The web app on Vercel is then only a producer. To keep Vercel Queues but run a regular worker off-Vercel, the docs point to `vercel-poll://` ([poll mode](https://vercel.com/docs/queues/poll-mode)). This demo doesn't test that path.
