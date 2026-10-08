from fastapi import FastAPI, HTTPException

from tasks import add, app as celery  # import tasks from `tasks`, never from `worker`

app = FastAPI(title="Celery on Vercel")


@app.get("/")
def index():
    return {
        "demo": "Celery on Vercel: tasks go through Vercel Queues to a private worker function",
        "endpoints": {
            "POST /tasks?x=2&y=3": "enqueue add(x, y); returns the task id",
            "GET /tasks/{task_id}": "task status and result (read from Runtime Cache)",
        },
    }


@app.post("/tasks", status_code=202)
def enqueue(x: int, y: int):
    try:
        task = add.delay(x, y)  # publishes one message to Vercel Queues
    except Exception as exc:
        # Typical cause: running outside Vercel / `vercel dev`, where vercel:// isn't registered.
        raise HTTPException(503, f"Could not publish the task to the Celery broker: {exc!r}")
    return {"task_id": task.id, "status_url": f"/tasks/{task.id}"}


@app.get("/tasks/{task_id}")
def status(task_id: str):
    try:
        result = celery.AsyncResult(task_id)  # unknown or expired ids read as PENDING
        return {
            "task_id": task_id,
            "status": result.status,
            "result": result.result if result.successful() else None,
        }
    except Exception as exc:
        # Typical cause: Runtime Cache doesn't exist locally (see README "Run locally").
        raise HTTPException(503, f"Could not read the Celery result backend: {exc!r}")
