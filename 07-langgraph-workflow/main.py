from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from vercel import workflow

from agent import Approval, approval_token, run_agent

app = FastAPI(title="LangGraph on Vercel Workflow")


class StartRun(BaseModel):
    topic: str


@app.get("/")
def index():
    return {
        "demo": "A LangGraph graph (write -> human review -> revise) running as a durable Vercel Workflow",
        "endpoints": {
            "POST /api/runs": 'Start a run. Body: {"topic": "..."}',
            "GET /api/runs/{run_id}": "Status, the draft awaiting review, or the final result",
            "POST /api/runs/{run_id}/approve": 'Resume the run. Body: {"approved": true} or {"approved": false, "feedback": "..."}',
        },
    }


@app.post("/api/runs")
async def start_run(body: StartRun):
    # Creates and queues the run, then returns. The graph runs in the background.
    run = await workflow.start(run_agent, topic=body.topic)
    return {"run_id": run.run_id}


@app.get("/api/runs/{run_id}")
async def get_run(run_id: str):
    run = workflow.get_run(run_id)  # A handle from the id; nothing is fetched yet.
    status = await run.status()  # pending | running | completed | failed | cancelled
    response: dict = {"run_id": run_id, "status": status}
    if status == "completed":
        response["result"] = await run.return_value()
    elif status == "failed":
        try:
            await run.return_value()
        except workflow.WorkflowRunFailedError as error:
            response["error"] = str(error)
    elif status == "running":
        try:  # A hook only exists while the graph is paused in `review`.
            hook = await workflow.get_hook_by_token(approval_token(run_id))
            response["awaiting_approval"] = hook.metadata
        except workflow.HookNotFoundError:
            pass
    return response


@app.post("/api/runs/{run_id}/approve")
async def approve(run_id: str, approval: Approval):
    try:
        await approval.resume(approval_token(run_id))
    except workflow.HookNotFoundError:
        raise HTTPException(409, "This run is not waiting for approval") from None
    return {"ok": True}
