# Research: FastMCP on Vercel

Researched 2026-10-08.

## What's available

- [FastMCP docs, full text](https://gofastmcp.com/llms-full.txt): the source for
  everything below. FastMCP is a Python framework for MCP servers and clients,
  maintained by Prefect.
- [HTTP deployment](https://gofastmcp.com/deployment/http): `mcp.http_app()`
  returns an ASGI app serving MCP at `/mcp`; it covers custom paths, host and
  origin protection, health checks with `@mcp.custom_route`, mounting into
  FastAPI, and stateless mode. It lists Vercel among the platforms that can host
  a FastMCP server.
- [Authentication](https://gofastmcp.com/servers/auth/authentication): bearer
  tokens, JWT and OAuth providers. The docs recommend authentication for any
  remote server, and note that some clients refuse unauthenticated ones.
- FastMCP 4 release notes (in the full text): v4 serves the sessionless
  `2026-07-28` MCP protocol and the earlier handshake protocol from one server,
  negotiating per connection.
- [fastmcp on PyPI](https://pypi.org/project/fastmcp/): 4.0.11 was the latest
  release when this demo was built; requires Python 3.10 or newer.
- Vercel's MCP templates are all TypeScript:
  [MCP with Next.js](https://vercel.com/templates/next.js/model-context-protocol-mcp-with-next-js),
  [Hono MCP remote server](https://vercel.com/templates/hono/hono-mcp-remote-server),
  [xmcp boilerplate](https://vercel.com/templates/other/xmcp-boilerplate) and three
  more Next.js variants. None of them uses FastMCP or Python.

## How it works on Vercel

- Vercel's FastAPI support detects `app` in `main.py` and runs it as one
  function. A FastMCP ASGI app mounted into FastAPI is served like any other
  route.
- **Stateless mode is required on serverless.** By default FastMCP keeps
  sessions in each instance's memory. The docs explain that sticky sessions
  don't help, because Cursor and Claude Code don't forward the cookies a load
  balancer would need. `stateless_http=True` gives each request a fresh
  transport context, so any instance can answer.
- Streamable HTTP answers with server-sent events, and Python functions on
  Vercel stream by default, so progress notifications reach the client while a
  tool runs.

## Gotchas

- **Mount at the root, not at `/mcp`.** With `http_app(path="/")` mounted at
  `/mcp`, Starlette answers `POST /mcp` with a 307 redirect to `/mcp/`. Some
  clients don't follow a redirect on POST, and behind a proxy the redirect can
  point at the wrong scheme. This demo uses `http_app(path="/mcp")` mounted at
  `/` after the FastAPI routes.
- **Pass the MCP app's lifespan to FastAPI.** The docs warn that without it the
  session manager doesn't start and requests fail.
- **Server-initiated requests need care.** On the `2026-07-28` protocol a tool
  can't send requests to the client mid-call; FastMCP 4 replaces that with a
  pattern where the tool returns a request for input. Notifications such as
  progress and logging still stream on every protocol version.
- **Tools run inside one function request,** so a single call is bounded by
  the function's maximum duration (300 seconds by default).

## Approach chosen for this demo

- FastAPI serves the explainer page at `/` and FastMCP serves MCP at `/mcp`,
  from one zero-config function.
- Three read-only tools: `find_demo` searches a bundled snapshot of the Python
  on Vercel catalog, so the server is useful from Cursor or Claude; `server_info`
  shows which region and instance answered; `count_to` streams progress. Plus a
  resource template and a prompt, so all three MCP primitives are shown.
- The explainer page speaks MCP itself, over plain `fetch`, so the page proves
  the endpoint works the way an agent would use it.
- No authentication, because every tool is read-only and harmless. The README
  and the page say to add FastMCP authentication for real tools.
- Tested locally with FastMCP's client on both protocol versions (`2026-07-28`
  by default, `2025-11-25` in legacy mode): listing, every tool, the resource,
  the prompt, argument validation, and progress notifications arriving 0.5
  seconds apart.
