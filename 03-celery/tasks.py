"""The Celery app and its tasks. Imported by the web app (to publish) and by the worker (to run)."""

import os
import time
import uuid
from datetime import datetime, timezone

from celery import Celery

# Created once per process, at import. The web function and the worker function
# each import this module in their own instances, so each gets its own id.
# Comparing the two ids shows which function ran which step.
INSTANCE_ID = uuid.uuid4().hex[:8]
REGION = os.environ.get("VERCEL_REGION", "local")

app = Celery(
    "celery-on-vercel",
    # vercel:// = Vercel Queues. Vercel injects the adapter that registers this
    # transport at build time (and in `vercel dev`), so there is no broker to
    # provision and no credentials: auth is the deployment's OIDC token.
    broker="vercel://",
    # Task state and return values go to Vercel Runtime Cache (regional, ephemeral).
    backend="vercel-runtime-cache://",
)


def utc_iso(moment: datetime | None = None) -> str:
    moment = moment or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).isoformat(timespec="milliseconds")


@app.task
def add(x: int, y: int) -> dict:
    started_at = utc_iso()
    time.sleep(2)  # simulate slow work so you can watch PENDING -> SUCCESS
    # Return the sum plus where and when it ran, so callers can see that the
    # task ran in the worker function, not in the web function that enqueued it.
    return {
        "sum": x + y,
        "worker": {
            "instance_id": INSTANCE_ID,
            "region": REGION,
            "started_at": started_at,
            "finished_at": utc_iso(),
        },
    }
