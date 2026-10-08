# Research: Celery on Vercel (October 2026)

**Short answer:** Vercel has official, first-class Celery support, announced 2026-07-31. Vercel Queues acts as the Celery broker (`vercel://`), and Vercel Runtime Cache is the default result backend (`vercel-runtime-cache://`). Celery workers declared in `pyproject.toml` are compiled into private, queue-triggered Vercel Functions. You don't run a long-lived `celery worker` and you don't provision Redis.

## What's available

**Official Vercel sources**

- [Docs: Run background tasks with Celery on Vercel](https://vercel.com/docs/frameworks/backend/celery). The canonical guide (last updated 2026-08-14). It covers the `tasks.py` / `worker.py` / `main.py` layout, `[[tool.vercel.subscribers]]`, broker transport options, the retry and `task_acks_late` semantics, the Runtime Cache result backend, splitting queues across functions, and limitations.
- [Changelog: Run background tasks with Celery on Vercel](https://vercel.com/changelog/run-background-tasks-with-celery-on-vercel) (2026-07-31). The launch post: tasks run as Vercel Functions on Fluid compute with Active CPU pricing, and `vercel://` is installed automatically.
- [Template: Python Celery Starter](https://vercel.com/templates/backend/python-celery-starter). One-click deploy of a FastAPI job dashboard with Celery workers on Vercel Queues.
- [github.com/vercel/examples/tree/main/python/celery](https://github.com/vercel/examples/tree/main/python/celery). The template's source. It sets `broker=os.getenv("CELERY_BROKER_URL", "vercel://")` and `task_ignore_result=True`, and keeps job state itself through `vercel.cache.RuntimeCache` instead of a Celery result backend. Its `pyproject.toml` declares `[[tool.vercel.subscribers]] entrypoint = "worker.run:app"` and depends on `vercel>=0.6.0`. Last changed 2026-08-21.
- [Docs: Vercel Queues concepts](https://vercel.com/docs/queues/concepts). Topics, consumer groups, push vs. poll, at-least-once delivery, 60 s default visibility timeout, retries, deployment pinning. Notes that Python projects declare consumers in `pyproject.toml`.
- [Docs: Vercel Queues Python SDK](https://vercel.com/docs/queues/python-sdk). Install with `pip install vercel` (or the slimmer `vercel-queue`). Covers `send`, `@subscribe`, `Topic[T]`, `QueueClient`, `poll_and_handle`, `accept_and_handle`, push subscribers via `[[tool.vercel.subscribers]]`, and local testing with `embedded_queue_service` / `python -m vercel.queue.devserver`. Env vars: `VERCEL_QUEUE_TOKEN`, `VERCEL_QUEUE_BASE_URL`, `VERCEL_REGION`, `VERCEL_DEPLOYMENT_ID`.
- [Docs: Queues poll mode](https://vercel.com/docs/queues/poll-mode). How to consume from outside Vercel. The Celery docs point to `vercel-poll://` for running a regular `celery worker` elsewhere.
- [Docs: Queues pricing and limits](https://vercel.com/docs/queues/pricing). Billed per operation in 4 KiB chunks. Messages up to 100 MB, retention from 60 s to 7 days (default 24 h), visibility timeout up to 60 min. Push invocations are billed as normal function compute.
- [Changelog: Vercel Python Queues SDK is now available in beta](https://vercel.com/changelog/vercel-python-queues-sdk-is-now-available-in-beta) (2026-08-19). Also in search results: [Python Queue Subscribers Starter](https://vercel.com/templates/python/python-queue-subscribers-starter) and [Vercel Queues now in public beta](https://vercel.com/changelog/vercel-queues-now-in-public-beta).
- [Docs: Runtime Cache](https://vercel.com/docs/caching/runtime-cache). Regional, ephemeral, LRU-evicted, 2 MB per item, available on all plans. Preview and production are isolated, and all projects in a Hobby team share one cache.
- [Docs: Python runtime](https://vercel.com/docs/functions/runtimes/python) and [Python version](https://vercel.com/docs/functions/runtimes/python/python-version). Covers `tool.vercel.entrypoint`, the 3.12 default (3.13 and 3.14 also available), and `pyproject.toml` + `uv.lock` support.
- [KB: Run a Docker monolith with workers on Vercel](https://vercel.com/kb/guide/docker-monolith-workers-vercel). Recommends moving Celery and Dramatiq workers into a Python service using these integrations, not keeping them inside the container.

**Packages (PyPI, checked 2026-10-08)**

- [`vercel-celery`](https://pypi.org/project/vercel-celery/) 0.7.8 (2026-10-06): "Celery integration for Vercel Queue and Runtime Cache". Requires `celery>=5.3,<6`, `vercel-queue`, `vercel-cache`, `httpx2`. A `vercel-celery-bundle` variant with vendored dependencies also exists.
- `vercel` 0.11.6 (the full Python SDK), `vercel-queue` 0.9.1, `vercel-runtime` 0.23.2, `celery` 5.6.3 (5.7.0b1 in pre-release), `fastapi` 0.143.0.

**Platform source (github.com/vercel/vercel, `packages/python/src`)**

- `conditional-vendoring.ts` maps the upstream `celery` dependency to the adapter `vercel-celery-bundle`, or to `vercel-celery` when `vercel-queue` is a direct dependency. It also sets the integration `vercel.integrations.celery:install_vercel_celery_integration`. The adapter is only bootstrapped when the project declares `[[tool.vercel.subscribers]]`. A self-declared adapter isn't injected but is still activated.
- `subscribers.ts` handles build-time introspection of subscriber entrypoints and generates private functions under `_py_subscribers/` with `queue/v2beta` triggers. `start-dev-server.ts` runs subscribers as `vercel dev` "sidecars".

**Non-Vercel alternative**

- [Upstash: Celery with Upstash Redis](https://upstash.com/docs/redis/integrations/celery). Uses `rediss://:{password}@{host}:{port}?ssl_cert_reqs=required` as both broker and backend, with the worker started by `celery -A tasks worker`. It says nothing about where the worker runs, and recommends fixed plans because Celery's polling inflates command counts.
- [Celery docs](https://docs.celeryq.dev/).

## How it works on Vercel

1. **Build.** If `celery` is in `[project].dependencies` and `pyproject.toml` has `[[tool.vercel.subscribers]]`, the Python builder installs the adapter, unless you declared it yourself. It then sets `VERCEL_QUEUE_INTEGRATIONS=vercel.integrations.celery:install_vercel_celery_integration` for the functions.
2. **Activation.** The `vercel_runtime` bootstrap (`workers.install_queue_integrations`) calls the installer before your code is imported. The installer registers the kombu transports `vercel://` (auto), `vercel-push://` and `vercel-poll://`, plus the Celery result backend `vercel-runtime-cache://`. The web function is activated publish-only (`register_queues=False`). The worker function also registers push consumption.
3. **Subscriber compilation.** The build imports `worker:app` and reads the queues the Celery app declares (`task_default_queue` and `task_queues`, but not queues that only appear in `task_routes`). Each queue maps to a topic named `celery-<app name>-<queue>` (sanitized). The build then generates a private function with a queue trigger. You don't need `vercel.json`. Optional `topics` filters split queues across functions.
4. **Runtime.** `.delay()` publishes to the topic over HTTPS, authenticated with the deployment's OIDC token and pinned to the deployment. Queues pushes the message to the worker function on Fluid compute, which hands it to an in-process Celery worker: one task per invocation, and parallelism comes from Queues. The task's result is written to Runtime Cache, and `AsyncResult` reads it from the web function.
5. **Mode selection.** `vercel://` uses push when the `VERCEL` env var is truthy and poll otherwise. `vercel-poll://` forces polling, for a regular worker off-Vercel.
6. **Local dev.** `vercel dev` (CLI 58.9.0 or later) starts the web app and the subscriber sidecar against a local queue.

**Can a classic Celery worker run on Vercel?** Not as a long-lived `celery worker` process. The supported model is the generated queue-triggered function above. To run a classic worker, host it elsewhere and use either `vercel-poll://` (Vercel Queues) or your own broker.

## Gotchas

- **Result backend.** Runtime Cache is regional and ephemeral, and Celery reads a missing entry as `PENDING`. The adapter's backend is strict, so it raises outside Vercel. `vercel dev` doesn't provide Runtime Cache, which I verified (the error is `Runtime Cache unavailable: no request cache context or runtime cache environment`). Use Redis or Postgres for results you need to keep.
- **Acks and retries.** With Celery's default early ack, a task that raises or times out isn't redelivered. `task_acks_late=True` makes crashes and timeouts redeliver, and a task that raises is still acked, so use `self.retry`. Delivery is at least once, so tasks must be idempotent.
- **Delays.** Queues doesn't defer `countdown` or `eta`. The worker invocation holds the message in memory until it's due.
- **What's missing.** No `celery beat` (use Vercel Cron Jobs to enqueue), no worker control commands, and every Vercel Functions limit applies, including max duration.
- **Deployment pinning.** Messages are consumed by the deployment that published them. Old deployments keep processing, and retrying, until their messages drain or expire. Deleting the deployment stops them.
- **Env vars override code.** Celery's `Settings.broker_url` and `Settings.result_backend` read `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` before the code config, as I verified in `celery/app/utils.py`. That's useful locally, but setting them on Vercel by accident would bypass Queues.
- **Stale template description.** The template page still says projects "automatically set `CELERY_BROKER_URL` to `vercel://`", and one search snippet described a Redis-backed variant. The current mechanism sets Celery's *default* broker through the adapter, and the current repo uses Runtime Cache.
- **Bundle bug I hit locally.** With only `celery` and `fastapi` as dependencies (the docs' minimal setup), `vercel dev` injected `vercel-celery-bundle` 0.7.7, and on retry 0.7.8 with `vercel-internal-shared-vendored-deps` 0.1.4. Worker startup then failed with `PackageNotFoundError: No package metadata was found for httpx2`, because the vendored `httpx2/__version__.py` calls `importlib.metadata.version("httpx2")`. Declaring the unbundled `vercel-celery`, which depends on the real `httpx2`, fixed it. I don't know whether deployed builds hit the same bug. The official template avoids it either way, because it depends on `vercel` and so pulls in `httpx2`.
- **Local uv policy.** This machine's uv config sets `exclude-newer = "2 days"`, so `uv.lock` resolves `vercel-celery` 0.7.7 (0.7.8 is two days old) and `fastapi` 0.142.2.

## Approach chosen for this demo

I followed the official docs layout almost line for line, since it's the most Vercel-native option:

- `tasks.py` sets `broker="vercel://"` and `backend="vercel-runtime-cache://"` explicitly, as the docs recommend.
- `worker.py` re-exports the app, and `pyproject.toml` declares `[tool.vercel] entrypoint = "main:app"` plus `[[tool.vercel.subscribers]] entrypoint = "worker:app"`.
- `main.py` has `POST /tasks` (`.delay()`) and `GET /tasks/{id}` (`AsyncResult`).

The demo deviates from the docs in two places:

1. **`vercel-celery` is declared explicitly.** This works around the bundle import bug above, and it pins the adapter in `uv.lock`. The platform source explicitly supports a self-declared adapter.
2. **Both endpoints catch broker and backend errors.** They return a 503 with the underlying error, so running outside Vercel fails clearly instead of with a bare 500.

There's no `vercel.json`, no env vars and no external resources. For local results, the README uses Celery's built-in `file://` result backend via `CELERY_RESULT_BACKEND`, so the code doesn't change.
