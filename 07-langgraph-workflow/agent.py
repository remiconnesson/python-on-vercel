"""A LangGraph graph that runs inside a durable Vercel Workflow.

The workflow body (`run_agent`) runs the graph. Graph nodes call `@wf.step`
functions for side effects (the LLM call) and wait on a Workflow hook for human
approval. Workflow records every step result and hook payload in its event log.
To resume, it replays the body (and therefore the graph) from the start: steps
that already ran return their recorded result instead of running again.
"""

import os
from typing import TypedDict

import pydantic

# Keep LangChain imports at module top, never inside a step: with
# vercel-workflow 0.11, lazy `langchain_core` imports in a step fail once a
# workflow body has run in the same process (see README "Gotchas").
from langchain_core.language_models import FakeListChatModel
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from vercel import workflow
from vercel.oidc import VercelOidcTokenError
from vercel.oidc.aio import get_vercel_oidc_token

MODEL = os.getenv("AI_GATEWAY_MODEL", "openai/gpt-5.4-nano")

wf = workflow.Workflows(
    sandbox_policy=workflow.SandboxPolicy(
        # Workflow bodies run in a sandbox that re-imports their modules and
        # blocks non-deterministic calls (clock, random, threads, sockets).
        # Serve these libraries from the regular interpreter instead: they
        # import network libraries the sandbox blocks, and their internals
        # (uuids, timestamps) never change which steps run or in what order.
        passthrough_modules=frozenset({"langgraph", "langchain_core", "langchain_openai", "langsmith"}),
        # Reuse one sandbox across runs, so the graph is compiled once.
        share_sandboxes=True,
    )
)


# --- Steps run in the regular interpreter, get retried, and are recorded ----


async def chat_model():
    if os.getenv("FAKE_LLM"):  # Local testing without credentials.
        return FakeListChatModel(responses=["(fake LLM) A three-sentence draft."])

    api_key = os.getenv("AI_GATEWAY_API_KEY")
    if not api_key:
        try:  # On Vercel, the function's OIDC token authenticates to AI Gateway.
            api_key = await get_vercel_oidc_token()
        except VercelOidcTokenError as error:
            # FatalError: fail the run now instead of retrying the step.
            raise workflow.FatalError(
                "No AI Gateway credential: set AI_GATEWAY_API_KEY locally "
                "(or FAKE_LLM=1), or deploy to Vercel to use its OIDC token."
            ) from error
    return ChatOpenAI(model=MODEL, base_url="https://ai-gateway.vercel.sh/v1", api_key=api_key)


@wf.step
async def generate(prompt: str) -> str:
    model = await chat_model()
    message = await model.ainvoke(prompt)
    return str(message.text)  # Step results are recorded: return plain data.


# --- The graph: write -> review (human) -> END, or back to write ------------


class State(TypedDict):
    topic: str
    draft: str
    feedback: str
    approved: bool


class Approval(pydantic.BaseModel, workflow.BaseHook):
    """The payload a human sends to POST /api/runs/{run_id}/approve."""

    approved: bool
    feedback: str = ""


def approval_token(run_id: str) -> str:
    return f"approval-{run_id}"


async def write(state: State) -> dict:
    prompt = f"Write a three-sentence product blurb about: {state['topic']}"
    if state["feedback"]:
        prompt += f"\n\nRevise this draft:\n{state['draft']}\n\nFeedback: {state['feedback']}"
    return {"draft": await generate(prompt)}  # A durable step, not a plain call.


async def review(state: State) -> dict:
    token = approval_token(workflow.get_workflow_metadata().run_id)
    # The run suspends here without using compute until the hook is resumed.
    # The metadata lets GET /api/runs/{run_id} show the draft that awaits review.
    async with Approval.wait(token=token, metadata={"draft": state["draft"]}) as hook:
        decision = await hook
    return {"approved": decision.approved, "feedback": decision.feedback}


# Nodes and routers are all `async def`: LangGraph runs sync callables in a
# thread pool, and the workflow event loop rejects run_in_executor().
async def after_review(state: State) -> str:
    return END if state["approved"] else "write"


builder = StateGraph(State)
builder.add_node("write", write)
builder.add_node("review", review)
builder.add_edge(START, "write")
builder.add_edge("write", "review")
builder.add_conditional_edges("review", after_review)
graph = builder.compile()  # No checkpointer: the Workflow event log is the persistence.


@wf.workflow
async def run_agent(*, topic: str) -> dict:
    state = await graph.ainvoke({"topic": topic, "draft": "", "feedback": "", "approved": False})
    return {"topic": topic, "draft": state["draft"]}
