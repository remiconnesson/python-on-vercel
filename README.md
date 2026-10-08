# Python on Vercel: demos

Minimal demos that show how Python runs on Vercel. Each directory is a standalone
uv project and its own Vercel project, and each has a `README.md` (how to run and
call it) and a `RESEARCH.md` (what Vercel and the community offer for that topic,
with links, gotchas, and why the demo is built the way it is).

| # | Demo | What it shows | Live |
|---|------|---------------|------|
| 1 | [`01-fastapi`](01-fastapi) | Zero-config FastAPI: routing, Pydantic validation, streaming, lifespan, Python 3.14 | [link](https://python-on-vercel-fastapi.vercel.zone) |
| 2 | [`02-django`](02-django) | Zero-config Django: template + JSON views, admin, `collectstatic` served from the CDN, optional Postgres | [link](https://python-on-vercel-django.vercel.zone) |
| 3 | [`03-celery`](03-celery) | Celery with the `vercel://` broker (Vercel Queues) and a queue-triggered worker function, results in Runtime Cache | [link](https://python-on-vercel-celery.vercel.zone) |
| 4 | [`04-ai-sdk`](04-ai-sdk) | AI SDK for Python (`ai` package): generate, text stream, and an agent with a tool streaming the AI SDK UI protocol (`useChat`) | [link](https://python-on-vercel-ai-sdk.vercel.zone) |
| 5 | [`05-workflow`](05-workflow) | Vercel Workflow Python SDK: steps, automatic retry, durable sleep, run status | [link](https://python-on-vercel-workflow.vercel.zone) |
| 6 | [`06-langgraph`](06-langgraph) | LangGraph agent (agent ↔ tools) behind FastAPI, SSE token streaming, AI Gateway via OIDC | [link](https://python-on-vercel-langgraph.vercel.zone) |
| 7 | [`07-langgraph-workflow`](07-langgraph-workflow) | A LangGraph graph inside a durable Workflow: LLM calls as steps, human approval via a Workflow hook | [link](https://python-on-vercel-langgraph-workflow.vercel.zone) |
| 8 | [`08-containers`](08-containers) | Container Images for Vercel Functions: `Dockerfile.vercel` with an apt package, served on Fluid compute | [link](https://python-on-vercel-containers.vercel.zone) |

## How the repo deploys

- One Vercel project per directory (team `vercel-fieldeng`), all connected to this
  repo, each with **Root Directory** set to its folder. Pushing to `main` deploys
  to production.
- Every project uses the ignored build step
  `git diff --quiet ${VERCEL_GIT_PREVIOUS_SHA:-HEAD^} HEAD -- .`, so a push only
  rebuilds the demos whose folder changed.
- Nothing needs provisioning. The AI demos call AI Gateway with the deployment's
  OIDC token (no API key). `03-celery` and Workflow use Vercel Queues, and Celery
  results go to Runtime Cache, all authenticated by OIDC. The only env var set is
  `DJANGO_SECRET_KEY` on the Django project.
- No demo needs a `vercel.json` except `08-containers`, which pins
  `"framework": "container"`. Other config lives in `pyproject.toml`
  (`[tool.vercel]`, `[[tool.vercel.workflows]]`, `[[tool.vercel.subscribers]]`).

## Run a demo locally

```bash
cd 01-fastapi
uv run uvicorn main:app --reload
```

Each demo's README has its exact command (Django uses `manage.py`, Celery needs
`vercel dev` for the `vercel://` broker). For the AI demos, run
`vercel link && vercel env pull` in the demo folder to get an OIDC token, or set
`AI_GATEWAY_API_KEY`.

## Adding a demo

1. Create `NN-name/` with its own `pyproject.toml` and `uv.lock` (no uv workspace:
   Vercel reads both files from the Root Directory).
2. Create a Vercel project with Root Directory `NN-name` and the same ignored build step.
3. Push.
