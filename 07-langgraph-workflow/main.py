from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from vercel import workflow

from agent import Approval, approval_token, run_agent

app = FastAPI(title="LangGraph on Vercel Workflow")
INDEX_HTML = (Path(__file__).parent / "index.html").read_text()


class StartRun(BaseModel):
    topic: str


def paused_since(hook: workflow.Hook) -> datetime:
    created = hook.created_at  # Set by Workflow when the run suspended on the hook.
    return created if created.tzinfo else created.replace(tzinfo=UTC)


@app.get("/")
def index(request: Request):
    # Browsers get the visual explainer (index.html); curl and scripts get JSON.
    if "text/html" in request.headers.get("accept", ""):
        return HTMLResponse(INDEX_HTML)
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
            # metadata = {"draft", "draft_number"}, set by the review node.
            response["awaiting_approval"] = {
                **hook.metadata,
                "paused_at": paused_since(hook).isoformat(),
            }
        except workflow.HookNotFoundError:
            pass
    return response


@app.post("/api/runs/{run_id}/approve")
async def approve(run_id: str, approval: Approval):
    try:
        hook = await approval.resume(approval_token(run_id))
    except workflow.HookNotFoundError:
        raise HTTPException(409, "This run is not waiting for approval") from None
    # How long the run sat suspended on this hook, measured on the server.
    paused_s = (datetime.now(UTC) - paused_since(hook)).total_seconds()
    return {"ok": True, "paused_s": round(paused_s, 3)}
