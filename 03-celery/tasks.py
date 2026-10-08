"""The Celery app and its tasks. Imported by the web app (to publish) and by the worker (to run)."""

import time

from celery import Celery

app = Celery(
    "celery-on-vercel",
    # vercel:// = Vercel Queues. Vercel injects the adapter that registers this
    # transport at build time (and in `vercel dev`), so there is no broker to
    # provision and no credentials: auth is the deployment's OIDC token.
    broker="vercel://",
    # Task state and return values go to Vercel Runtime Cache (regional, ephemeral).
    backend="vercel-runtime-cache://",
)


@app.task
def add(x: int, y: int) -> int:
    time.sleep(2)  # simulate slow work so you can watch PENDING -> SUCCESS
    return x + y
