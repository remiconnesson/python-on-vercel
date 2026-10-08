import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse

# import tasks from `tasks`, never from `worker`
from tasks import INSTANCE_ID, REGION, add, app as celery, utc_iso

app = FastAPI(title="Celery on Vercel")
INDEX_HTML = (Path(__file__).parent / "index.html").read_text()

# This web function's own identity. The worker reports its own in the task result.
WEB = {"instance_id": INSTANCE_ID, "region": REGION}
# The vercel-celery adapter names each topic celery-<app name>-<queue>.
QUEUE_TOPIC = f"celery-{celery.main}-{celery.conf.task_default_queue}"


@app.get("/")
def index(request: Request):
    # Browsers get the visual explainer (index.html); curl and scripts get JSON.
    if "text/html" in request.headers.get("accept", ""):
        return HTMLResponse(INDEX_HTML)
    return {
        "demo": "Celery on Vercel: tasks go through Vercel Queues to a private worker function",
        "web": WEB,
        "queue_topic": QUEUE_TOPIC,
        "endpoints": {
            "POST /tasks?x=2&y=3": "enqueue add(x, y); returns the task id",
            "GET /tasks/{task_id}": "task status and result (read from Runtime Cache)",
        },
    }


@app.post("/tasks", status_code=202)
def enqueue(x: int, y: int):
    started = time.perf_counter()
    try:
        task = add.delay(x, y)  # publishes one message to Vercel Queues
    except Exception as exc:
        # Typical cause: running outside Vercel / `vercel dev`, where vercel:// isn't registered.
        raise HTTPException(503, f"Could not publish the task to the Celery broker: {exc!r}")
    return {
        "task_id": task.id,
        "status_url": f"/tasks/{task.id}",
        "enqueued_at": utc_iso(),
        "publish_ms": round((time.perf_counter() - started) * 1000, 1),
        "web": WEB,
    }


@app.get("/tasks/{task_id}")
def status(task_id: str):
    try:
        result = celery.AsyncResult(task_id)  # unknown or expired ids read as PENDING
        state = result.state
        value = result.result if state == "SUCCESS" else None
        stored_at = result.date_done if state == "SUCCESS" else None
    except Exception as exc:
        # Typical cause: Runtime Cache doesn't exist locally (see README "Run locally").
        raise HTTPException(503, f"Could not read the Celery result backend: {exc!r}")
    # add() returns {"sum": ..., "worker": {...}}. Keep `result` as the sum.
    worker = None
    if isinstance(value, dict):
        worker, value = value.get("worker"), value.get("sum")
    return {
        "task_id": task_id,
        "status": state,
        "result": value,
        "worker": worker,
        "stored_at": utc_iso(stored_at) if stored_at else None,
        "read_at": utc_iso(),
        "web": WEB,
    }
