"""FastMCP on Vercel: an MCP server that Cursor, Claude and other MCP clients can call.

Vercel finds `app` in main.py (zero-config FastAPI) and runs it as one Vercel Function.
FastMCP serves MCP at /mcp over Streamable HTTP in stateless mode: every request stands
alone, so any function instance can answer it, with no sticky sessions.
"""

import asyncio
import json
import os
import platform
import re
import time
import uuid
from pathlib import Path
from typing import Annotated

import fastmcp
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastmcp import Context, FastMCP
from fastmcp.exceptions import ResourceError
from pydantic import Field

HERE = Path(__file__).parent
# A snapshot of the Python on Vercel catalog (python-on-vercel-catalog.vercel.zone).
CATALOG = json.loads((HERE / "catalog.json").read_text())
ENTRIES = {entry["slug"]: entry for entry in CATALOG["entries"]}
INDEX_HTML = (HERE / "index.html").read_text()

# Set once per function instance. Fluid compute reuses an instance for many requests.
INSTANCE_ID = uuid.uuid4().hex[:8]
STARTED_AT = time.time()

mcp = FastMCP(
    "Python on Vercel",
    instructions=(
        "Find Python on Vercel demos and templates for what a customer runs or asks. "
        "Start with find_demo; read demo://{slug} for one entry."
    ),
)

STOPWORDS = {"a", "an", "and", "are", "can", "do", "for", "how", "i", "in", "is", "it", "my", "of",
             "on", "or", "our", "run", "the", "to", "us", "vercel", "we", "with", "you", "your"}
# Customer wording that doesn't appear in the catalog text.
SYNONYMS = {"docker": "container", "dockerfile": "container", "jobs": "celery", "background": "celery",
            "worker": "celery", "workers": "celery", "llm": "ai", "chat": "ai", "agent": "agents",
            "mcp": "fastmcp", "realtime": "websocket", "websockets": "websocket", "durable": "workflow"}


def words(text: str) -> set[str]:
    tokens = {t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in STOPWORDS}
    return tokens | {SYNONYMS[t] for t in tokens if t in SYNONYMS}


def summary(entry: dict) -> dict:
    return {key: entry[key] for key in ("slug", "name", "kind", "capability", "what", "links")}


@mcp.tool(annotations={"readOnlyHint": True})
def find_demo(
    question: Annotated[str, Field(description='What the customer runs or asks, e.g. "we run Celery"')],
    limit: Annotated[int, Field(ge=1, le=10)] = 5,
) -> list[dict]:
    """Find Python on Vercel demos and templates that answer a customer's question,
    such as "can you host our FastAPI app?" or "we have Docker images". Returns the
    best matches, explainer demos first on ties, each with its live and code links."""
    query = words(question)
    scored = []
    for entry in CATALOG["entries"]:
        text = words(" ".join([entry["name"], entry["what"], entry["capability"], entry["kind"]]))
        score = len(query & text) + (0.5 if entry["kind"] == "Explainer demo" else 0)
        if score >= 1:
            scored.append((score, entry))
    scored.sort(key=lambda pair: -pair[0])
    return [summary(entry) for _, entry in scored[:limit]]


@mcp.tool(annotations={"readOnlyHint": True})
def server_info() -> dict:
    """Where this call ran: the Vercel region, the function instance, and the
    Python and FastMCP versions. The same instance answering several calls shows
    Fluid compute reusing it."""
    return {
        "region": os.environ.get("VERCEL_REGION", "local"),
        "instance_id": INSTANCE_ID,
        "instance_uptime_s": round(time.time() - STARTED_AT, 1),
        "python": platform.python_version(),
        "fastmcp": fastmcp.__version__,
    }


@mcp.tool(annotations={"readOnlyHint": True})
async def count_to(n: Annotated[int, Field(ge=1, le=10)], ctx: Context) -> str:
    """Count to n, one number every 0.5 seconds, reporting progress after each one.
    The progress notifications stream to the client while the tool is still running."""
    for i in range(1, n + 1):
        await asyncio.sleep(0.5)
        await ctx.report_progress(i, n, f"Counted {i} of {n}")
    return f"Counted to {n} in {n * 0.5:.1f} seconds"


@mcp.resource("demo://{slug}", mime_type="application/json")
def demo(slug: str) -> dict:
    """One Python on Vercel catalog entry, by slug (find_demo returns slugs)."""
    if slug not in ENTRIES:
        raise ResourceError(f"No demo with slug {slug!r}. Use find_demo to search.")
    return summary(ENTRIES[slug])


@mcp.prompt
def pick_demo(customer_says: str) -> str:
    """Pick the demo to open in a meeting, given what the customer said."""
    return (
        f'A customer said: "{customer_says}".\n'
        "Use find_demo to search the Python on Vercel catalog, then recommend one demo to "
        "open first and one to show next. Give their links and one sentence on why each fits."
    )


# MCP lives at /mcp. The MCP app is mounted at the root, after the FastAPI routes below,
# so those match first; mounting it under /mcp instead would redirect POST /mcp to /mcp/.
mcp_app = mcp.http_app(path="/mcp", stateless_http=True)
app = FastAPI(title="FastMCP on Vercel", lifespan=mcp_app.lifespan)


@app.get("/")
def index(request: Request):
    # Browsers get the visual explainer (index.html); curl and scripts get JSON.
    if "text/html" in request.headers.get("accept", ""):
        return HTMLResponse(INDEX_HTML)
    return {
        "server": "Python on Vercel (FastMCP)",
        "mcp_endpoint": "/mcp",
        "transport": "Streamable HTTP, stateless",
        "tools": ["find_demo", "server_info", "count_to"],
        "resources": ["demo://{slug}"],
        "prompts": ["pick_demo"],
        "catalog_entries": len(ENTRIES),
    }


app.mount("/", mcp_app)
