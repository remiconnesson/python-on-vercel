# FastMCP on Vercel

A Python MCP server built with [FastMCP](https://gofastmcp.com) 4, deployed to
Vercel as one zero-config function. Cursor, Claude Code or any MCP client can
connect to `/mcp` and call its tools. It runs in stateless mode, so any function
instance can answer any request and no sticky sessions are needed.

Open the deployment in a browser for a live explainer: the page is itself an MCP
client. It connects, lists the tools, resources and prompts, calls tools while
you watch the response stream, and shows how to connect your own agent. `curl`
on `/` still gets a JSON summary.

## Files

```
09-fastmcp/
├── main.py          # the FastMCP server, mounted in a FastAPI app (Vercel auto-detects `app`)
├── catalog.json     # snapshot of the Python on Vercel catalog that find_demo searches
├── index.html       # the visual explainer served at `/` to browsers
├── pyproject.toml   # fastmcp + fastapi
├── uv.lock
└── .python-version
```

## What the server exposes

| Name | Kind | What it does |
|---|---|---|
| `find_demo(question, limit)` | Tool, read-only | Searches the Python on Vercel catalog for a customer question, such as "we run Celery" |
| `server_info()` | Tool, read-only | Returns the Vercel region and function instance that answered |
| `count_to(n)` | Tool, read-only | Counts to `n`, reporting progress every 0.5 s, to show streaming |
| `demo://{slug}` | Resource template | One catalog entry by slug |
| `pick_demo(customer_says)` | Prompt | Asks the model to pick a demo to show first and next |

## How it works on Vercel

- `mcp.http_app(path="/mcp", stateless_http=True)` builds the MCP ASGI app.
  FastAPI owns `/` (this page) and mounts the MCP app at the root, after its own
  routes. Mounting it under `/mcp` instead makes `POST /mcp` redirect to `/mcp/`,
  which some clients don't follow.
- FastAPI is given the MCP app's lifespan (`FastAPI(lifespan=mcp_app.lifespan)`).
  FastMCP needs it to start its session manager, even in stateless mode.
- Responses are server-sent events, so progress notifications stream to the
  client while a tool runs.
- FastMCP 4 serves both MCP protocol versions from one endpoint: the
  handshake-era protocol (`2025-11-25`, used by this page) and the sessionless
  `2026-07-28` protocol that newer clients, including FastMCP's own, negotiate.
- No `vercel.json` and no environment variables.

## Connect a client

```bash
claude mcp add --transport http python-on-vercel https://python-on-vercel-fastmcp.vercel.zone/mcp
```

Cursor (`~/.cursor/mcp.json`):

```json
{ "mcpServers": { "python-on-vercel": { "url": "https://python-on-vercel-fastmcp.vercel.zone/mcp" } } }
```

Python:

```python
import asyncio
from fastmcp import Client

async def main():
    async with Client("https://python-on-vercel-fastmcp.vercel.zone/mcp") as client:
        print((await client.call_tool("find_demo", {"question": "we run Celery"})).data)

asyncio.run(main())
```

## Run locally

```bash
uv run uvicorn main:app --reload
```

The MCP endpoint is `http://127.0.0.1:8000/mcp`.

## Deploy

- Vercel project with Root Directory `09-fastmcp`, framework FastAPI. Defaults
  for everything else.
- This demo has no authentication, so all its tools are read-only. For real
  tools, add one of FastMCP's
  [authentication options](https://gofastmcp.com/servers/auth/authentication)
  (bearer tokens, OAuth) before connecting agents.

## Try it with curl

```bash
URL=https://python-on-vercel-fastmcp.vercel.zone   # or http://127.0.0.1:8000

curl $URL/   # JSON summary
curl -X POST $URL/mcp -H 'content-type: application/json' \
  -H 'accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"find_demo","arguments":{"question":"we have Docker images"}}}'
```
