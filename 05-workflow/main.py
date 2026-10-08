from fastapi import FastAPI, HTTPException
from vercel import workflow

from workflows import process_order

app = FastAPI(title="Vercel Workflow (Python) demo")


@app.get("/")
def index():
    return {
        "demo": "Vercel Workflow with the Python SDK (vercel-workflow)",
        "workflow": "process_order: reserve_inventory -> charge_card (retried once) "
        "-> durable sleep -> send_receipt",
        "endpoints": {
            "POST /api/runs?order_id=order_123&delay_seconds=10": "start a run",
            "GET /api/runs/{run_id}": "run status, plus the result once completed",
        },
    }


@app.post("/api/runs")
async def start_run(order_id: str = "order_123", delay_seconds: int = 10):
    # start() records the run and enqueues it, then returns right away.
    # The workflow itself runs in the background (on Vercel: its own function).
    run = await workflow.start(process_order, order_id, delay_seconds=delay_seconds)
    return {"run_id": run.run_id, "status_url": f"/api/runs/{run.run_id}"}


@app.get("/api/runs/{run_id}")
async def get_run(run_id: str):
    run = workflow.get_run(run_id)
    try:
        status = await run.status()  # pending | running | completed | failed | cancelled
    except Exception as error:  # unknown or expired run id; keep the reason visible
        raise HTTPException(404, f"run {run_id}: {error}")
    body = {"run_id": run_id, "status": status}
    if status == "completed":
        body["result"] = await run.return_value()
    return body
