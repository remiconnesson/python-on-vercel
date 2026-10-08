"""LangGraph on Vercel: a tiny tool-calling agent served by FastAPI.

Vercel finds the FastAPI `app` in main.py (zero config) and runs the whole app
as one Vercel Function. The model is called through Vercel AI Gateway's
OpenAI-compatible endpoint, authenticated with an API key or the Vercel OIDC token.
"""

import os
import time
import uuid
from collections.abc import AsyncIterable
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.sse import EventSourceResponse, ServerSentEvent
from langchain_core.messages import AIMessageChunk, BaseMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from pydantic import BaseModel
from vercel.oidc import VercelOidcTokenError
from vercel.oidc.aio import get_vercel_oidc_token

AI_GATEWAY_URL = "https://ai-gateway.vercel.sh/v1"
MODEL = os.getenv("AI_GATEWAY_MODEL", "openai/gpt-5.4-nano")

# Created once per function instance (at cold start). Responses include it so you
# can tell whether two requests reached the same instance, and so the same memory.
INSTANCE_ID = uuid.uuid4().hex[:8]
STARTED_AT = time.time()
# The explainer page, read once at import (restart the server after editing it).
INDEX_HTML = (Path(__file__).parent / "index.html").read_text()


# --- Credentials -------------------------------------------------------------


class MissingCredentials(Exception):
    pass


async def gateway_api_key() -> str:
    """Return an AI Gateway credential. ChatOpenAI calls this before every request.

    1. AI_GATEWAY_API_KEY, if set.
    2. Otherwise the Vercel OIDC token. On Vercel, the Python runtime adds an
       `x-vercel-oidc-token` header to every request and registers it with
       `vercel.headers`, which is where `vercel.oidc` reads it from. Locally it
       falls back to VERCEL_OIDC_TOKEN (from `vercel env pull`).
    """
    if key := os.getenv("AI_GATEWAY_API_KEY"):
        return key
    try:
        return await get_vercel_oidc_token()
    except VercelOidcTokenError as e:
        raise MissingCredentials(
            "No AI Gateway credential. Set AI_GATEWAY_API_KEY, or run "
            "`vercel link && vercel env pull` and start the app with "
            "`--env-file .env.local` to use VERCEL_OIDC_TOKEN. "
            "Deployed on Vercel, the OIDC token is provided automatically."
        ) from e


async def credential_source() -> str:
    """Name the credential gateway_api_key() would use, without returning it."""
    try:
        await gateway_api_key()
    except MissingCredentials:
        return "none"
    return "api_key" if os.getenv("AI_GATEWAY_API_KEY") else "oidc"


# --- The graph: agent <-> tools loop -----------------------------------------


@tool
def multiply(a: float, b: float) -> float:
    """Multiply two numbers."""
    return a * b


tools = [multiply]
llm = ChatOpenAI(model=MODEL, base_url=AI_GATEWAY_URL, api_key=gateway_api_key).bind_tools(tools)


async def agent(state: MessagesState):
    return {"messages": [await llm.ainvoke(state["messages"])]}


builder = StateGraph(MessagesState)
builder.add_node("agent", agent)
builder.add_node("tools", ToolNode(tools))
builder.add_edge(START, "agent")
builder.add_conditional_edges("agent", tools_condition)  # tool calls -> "tools", else END
builder.add_edge("tools", "agent")

# InMemorySaver keeps each thread's messages in this process's RAM. Fluid compute
# reuses instances, so a thread_id often survives between requests, but a cold
# start, a redeploy, or a request routed to another instance starts from scratch.
# Use a Postgres or Redis checkpointer for durable conversations.
graph = builder.compile(checkpointer=InMemorySaver())


# --- HTTP API ----------------------------------------------------------------

app = FastAPI(title="LangGraph on Vercel")


class ChatRequest(BaseModel):
    message: str
    thread_id: str | None = None  # pass it back to continue a conversation


@app.exception_handler(MissingCredentials)
async def missing_credentials(_, exc: MissingCredentials):
    return JSONResponse(status_code=500, content={"error": str(exc)})


def summarize(message: BaseMessage) -> dict:
    out = {"type": message.type, "content": message.text}
    if tool_calls := getattr(message, "tool_calls", None):
        out["tool_calls"] = [{"name": c["name"], "args": c["args"]} for c in tool_calls]
    return out


def run(req: ChatRequest) -> tuple[dict, dict]:
    thread_id = req.thread_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    return {"messages": [{"role": "user", "content": req.message}]}, config


async def prior_messages(config: dict) -> int:
    # Messages this instance already holds for the thread: 0 for a new thread, or
    # for a known one whose memory lives on another instance (or was lost).
    state = await graph.aget_state(config)
    return len(state.values.get("messages", []))


@app.get("/")
async def index(request: Request):
    # Browsers get the visual explainer (index.html); curl and scripts get JSON.
    if "text/html" in request.headers.get("accept", ""):
        return HTMLResponse(INDEX_HTML)
    return {
        "demo": "LangGraph agent (agent <-> tools) on Vercel, model via AI Gateway",
        "model": MODEL,
        "credential": await credential_source(),
        "region": os.environ.get("VERCEL_REGION", "local"),
        "instance_id": INSTANCE_ID,
        "instance_uptime_s": round(time.time() - STARTED_AT, 1),
        "endpoints": {
            "POST /invoke": "run the graph to the end, return the answer as JSON",
            "POST /stream": "run the graph, stream tokens and node updates as SSE",
        },
        "body": {"message": "What is 12.5 times 4?", "thread_id": "optional"},
        "memory": "InMemorySaver: threads live in one function instance's RAM only",
    }


@app.post("/invoke", dependencies=[Depends(gateway_api_key)])
async def invoke(req: ChatRequest):
    inputs, config = run(req)
    prior = await prior_messages(config)
    try:
        state = await graph.ainvoke(inputs, config)
    except Exception as e:  # e.g. AI Gateway rejected the credential or the model id
        return JSONResponse(status_code=502, content={"error": f"{type(e).__name__}: {e}"})
    return {
        "thread_id": config["configurable"]["thread_id"],
        "instance_id": INSTANCE_ID,
        "prior_messages": prior,
        "answer": state["messages"][-1].text,
        "messages": [summarize(m) for m in state["messages"]],
    }


# The credential check runs as a dependency, before the 200 + SSE headers are sent.
@app.post("/stream", response_class=EventSourceResponse, dependencies=[Depends(gateway_api_key)])
async def stream(req: ChatRequest) -> AsyncIterable[ServerSentEvent]:
    inputs, config = run(req)
    yield ServerSentEvent(
        event="thread",
        data={
            "thread_id": config["configurable"]["thread_id"],
            "instance_id": INSTANCE_ID,
            "prior_messages": await prior_messages(config),
        },
    )
    try:
        async for part in graph.astream(
            inputs,
            config,
            stream_mode=["messages", "updates"],
            version="v2",  # every part is {"type": <mode>, "ns": ..., "data": ...}
        ):
            if part["type"] == "messages":  # LLM tokens, as they arrive
                chunk, meta = part["data"]
                if isinstance(chunk, AIMessageChunk) and chunk.text:
                    yield ServerSentEvent(
                        event="token", data={"node": meta["langgraph_node"], "text": chunk.text}
                    )
            elif part["type"] == "updates":  # one event per finished node
                for node, update in part["data"].items():
                    messages = [summarize(m) for m in (update or {}).get("messages", [])]
                    yield ServerSentEvent(event="update", data={"node": node, "messages": messages})
    except Exception as e:  # the 200 is already sent, so report failures in-band
        yield ServerSentEvent(event="error", data={"error": f"{type(e).__name__}: {e}"})
        return
    yield ServerSentEvent(event="done", data={})
